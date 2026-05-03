import os
import re
import json
import time
import pandas as pd
from openai import OpenAI
from tavily import TavilyClient


def _tag_profile(df: pd.DataFrame) -> str:
    """Build a short text block summarising milk/style/country from tagged rows."""
    parts = []
    for col, label in [("Milk Type", "Milk breakdown"), ("Style", "Styles tried"), ("Country", "Origins")]:
        if col not in df.columns:
            continue
        counts = df[col].dropna().str.strip().replace("", pd.NA).dropna().value_counts()
        if counts.empty:
            continue
        if col == "Milk Type":
            parts.append(f"{label}: {', '.join(f'{v}× {k}' for k, v in counts.items())}")
        else:
            parts.append(f"{label}: {', '.join(counts.head(6).index)}")
    if not parts:
        return ""
    return "\nMY CHEESE PROFILE (from tagged entries):\n" + "\n".join(f"- {p}" for p in parts) + "\n"


_STORE_TIERS = """\
TIER 1 — check these first (most convenient, list if available):
- Aldi (South Orange NJ, or nearest NJ location)
- Trader Joe's (South Orange NJ, or nearest NJ location)

TIER 2 — include if Tier 1 doesn't carry it:
- Whole Foods (nearest South Orange NJ / Millburn NJ location)
- Lidl (nearest South Orange NJ location)

TIER 3 — specialty stores, only if not available at Tier 1 or 2 (use South Orange NJ or Manhattan as location):
- Murray's Cheese (Grand Central Terminal, NYC or Bleecker St, NYC)
- Eataly (Flatiron, Manhattan or Palisades Center, Nanuet NJ)
- Di Palo's Fine Foods (Little Italy, Manhattan)
- Valley Shepherd Creamery (Long Valley, NJ)
- Any other relevant specialty cheesemonger near South Orange NJ or Manhattan

Always list the cheapest/most accessible option first. If a cheese is a Tier 1 staple, you do not \
need to list Tier 3 stores."""

_REC_SCHEMA = """\
Return ONLY a valid JSON array — no markdown fences, no prose. Each element:
{
  "name": "Full cheese name",
  "origin": "Country, Region",
  "type": "Category (e.g., semi-firm, washed-rind, blue, soft-ripened)",
  "milk_type": "Cow / Sheep / Goat / Mixed",
  "flavor_profile": "Vivid 2-3 sentence tasting description",
  "why_youll_love_it": "Start with 'Because you gave [specific cheese from MY COLLECTION] X/10 for [exact quality]…' then explain what shared trait makes this recommendation a match. Always cite a real cheese name and score from the list above.",
  "tasting_notes": ["note1", "note2", "note3", "note4"],
  "price_range": "~$X/lb or ~$X each",
  "confidence": 9.2,
  "stores": [
    {
      "name": "Store name",
      "location": "Address or City, State",
      "notes": "Availability or purchasing tip"
    }
  ],
  "pairs_with": ["item1", "item2", "item3"]
}"""


def _build_prompt(df: pd.DataFrame, num_recs: int, already_pinned: list[str] | None = None) -> str:
    top = df[df["Score"] >= 8].sort_values("Score", ascending=False)
    disliked = df[df["Score"] < 6]

    top_str = top[["Cheese Type", "Score", "Tasting Notes", "From Where"]].to_string(index=False)
    disliked_str = (
        disliked[["Cheese Type", "Score", "Tasting Notes"]].to_string(index=False)
        if not disliked.empty
        else "None"
    )

    pinned_section = ""
    if already_pinned:
        bullet_list = "\n".join(f"- {name}" for name in already_pinned)
        pinned_section = f"""
ALREADY SAVED TO MY WISHLIST (do NOT recommend any of these again):
{bullet_list}
"""

    tag_section = _tag_profile(df)

    return f"""I'm a cheese enthusiast who has tried and scored these cheeses:

TOP RATED (8+/10):
{top_str}

LESS ENJOYED (below 6/10):
{disliked_str}

OVERALL AVERAGE SCORE: {df["Score"].mean():.1f}/10
{tag_section}{pinned_section}
Based on this history, my flavor preferences are clearly: bold/distinctive flavors, creamy or meltable \
textures, fruity or tangy notes, and well-salted cheeses. I dislike bland/flavorless cheeses with no wow factor.

Please recommend {num_recs} cheeses I have NOT tried yet that I would love. For each cheese list \
the specific physical stores where I can buy it, using this strict priority order:

{_STORE_TIERS}

{_REC_SCHEMA}"""


def _build_similar_prompt(
    cheese_name: str,
    df: pd.DataFrame,
    num_recs: int,
    already_pinned: list[str] | None = None,
) -> str:
    match = df[df["Cheese Type"].str.strip().str.lower() == cheese_name.lower()]
    if not match.empty:
        row = match.iloc[0]
        score = row.get("Score", "?")
        notes = str(row.get("Tasting Notes") or "")
        extras = ", ".join(
            v for v in [
                str(row.get("Milk Type") or ""),
                str(row.get("Style") or ""),
                str(row.get("Country") or ""),
            ] if v.strip()
        )
        cheese_desc = f'"{cheese_name}" ({score}/10)'
        if notes:
            cheese_desc += f" — {notes}"
        if extras:
            cheese_desc += f" [{extras}]"
    else:
        cheese_desc = f'"{cheese_name}"'

    pinned_section = ""
    if already_pinned:
        bullet_list = "\n".join(f"- {name}" for name in already_pinned)
        pinned_section = f"""
Do NOT recommend any of these (already in my wishlist):
{bullet_list}
"""

    schema = _REC_SCHEMA.replace(
        '"why_youll_love_it": "Start with \'Because you gave [specific cheese from MY COLLECTION] X/10 for [exact quality]…\' then explain what shared trait makes this recommendation a match. Always cite a real cheese name and score from the list above."',
        f'"why_youll_love_it": "Explain precisely what flavour or texture trait this cheese shares with {cheese_name}, and why that makes it a great follow-on."',
    )

    return f"""I'm a cheese enthusiast. I love {cheese_desc} and want to find similar cheeses I haven't tried.
{pinned_section}
Please recommend {num_recs} cheeses that are similar to "{cheese_name}" and that I would enjoy.

For each cheese list specific stores using this priority:
{_STORE_TIERS}

{schema}"""


def get_recommendations(
    df: pd.DataFrame,
    num_recs: int = 6,
    already_pinned: list[str] | None = None,
) -> list[dict]:
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    prompt = _build_prompt(df, num_recs, already_pinned=already_pinned or [])
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cheese recommendation assistant. Return strict JSON only "
                    "with no markdown fences."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def get_similar_recommendations(
    cheese_name: str,
    df: pd.DataFrame,
    num_recs: int = 3,
    already_pinned: list[str] | None = None,
) -> list[dict]:
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    prompt = _build_similar_prompt(cheese_name, df, num_recs, already_pinned=already_pinned or [])
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[
            {
                "role": "system",
                "content": "You are a cheese recommendation assistant. Return strict JSON only with no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _fetch_image_url(tavily: TavilyClient, name: str) -> str:
    """Fallback chain: cheese.com → Wikipedia → general search."""
    for query in [
        f"{name} cheese site:cheese.com",
        f"{name} cheese site:en.wikipedia.org",
        f"{name} cheese",
    ]:
        try:
            resp = tavily.search(query, search_depth="basic", max_results=3, include_images=True)
            images = resp.get("images", [])
            if images:
                return images[0]
        except Exception as exc:
            print(f"[recommendations] image fallback failed for {name}: {exc}")
        time.sleep(0.3)
    return ""


def add_images(recommendations: list[dict]) -> list[dict]:
    """Enrich each recommendation with a picture URL and reference link via Tavily."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        for rec in recommendations:
            rec.setdefault("picture_url", "")
            rec.setdefault("link", "")
        return recommendations

    tavily = TavilyClient(api_key=key)
    for rec in recommendations:
        try:
            resp = tavily.search(
                f"{rec['name']} cheese",
                search_depth="basic",
                max_results=3,
                include_images=True,
            )
            results = resp.get("results", [])
            rec["link"] = results[0]["url"] if results else ""
            images = resp.get("images", [])
            if images:
                rec["picture_url"] = images[0]
            else:
                rec["picture_url"] = _fetch_image_url(tavily, rec["name"])
        except Exception as exc:
            print(f"[recommendations] search failed for {rec['name']}: {exc}")
            rec.setdefault("link", "")
            rec["picture_url"] = _fetch_image_url(tavily, rec["name"])
        time.sleep(0.4)

    return recommendations


def tag_cheese(name: str) -> dict:
    """
    Infer milk type, style, and country of origin for a cheese name.
    Returns {"milk_type": str, "style": str, "country": str}.
    """
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=120,
        messages=[
            {
                "role": "system",
                "content": "You are a cheese expert. Return strict JSON only, no markdown.",
            },
            {
                "role": "user",
                "content": (
                    f'What are the milk type, style, and country of origin for "{name}" cheese?\n'
                    'Return exactly: {"milk_type": "Cow|Sheep|Goat|Mixed", '
                    '"style": "e.g. Semi-firm, Soft-ripened, Blue, Washed-rind, Hard, Fresh, Aged", '
                    '"country": "Country name"}\n'
                    "If unknown, use an empty string."
                ),
            },
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
        return {
            "milk_type": result.get("milk_type", ""),
            "style":     result.get("style", ""),
            "country":   result.get("country", ""),
        }
    except Exception:
        return {"milk_type": "", "style": "", "country": ""}
