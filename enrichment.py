import os
import re
import time
import requests
import pandas as pd
from typing import Callable, Optional
from tavily import TavilyClient

# Map normalised "From Where" values to their official domains
STORE_DOMAINS: dict[str, str] = {
    "trader joes": "traderjoes.com",
    "trader joe's": "traderjoes.com",
    "aldi": "aldi.us",
    "lidl": "lidl.com",
    "whole foods": "wholefoodsmarket.com",
    "wholefoods": "wholefoodsmarket.com",
    "murrays cheese": "murrayscheese.com",
    "murray's cheese": "murrayscheese.com",
    "walmart": "walmart.com",
    "costco": "costco.com",
}

# Sentences containing these patterns are boilerplate — skip them
_BOILERPLATE = re.compile(
    r"cookie|privacy|sign in|log in|add to cart|buy now|shop now|"
    r"free shipping|in stock|out of stock|subscribe|newsletter|"
    r"breadcrumb|click here|javascript|per lb|\$\d|\d+ reviews|"
    r"read more|see more|show more|back to",
    re.IGNORECASE,
)


def _tavily() -> TavilyClient:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise EnvironmentError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)


def _store_domain(from_where: str) -> str:
    key = from_where.lower().strip()
    for store_key, domain in STORE_DOMAINS.items():
        if store_key in key:
            return domain
    return ""


# Prefer prices explicitly marked per-lb / per-pound over bare dollar amounts
_PRICE_PATTERNS = [
    re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*/\s*(?:lb|pound)", re.IGNORECASE),
    re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*per\s*(?:lb|pound)", re.IGNORECASE),
    re.compile(r"\$[\d,]+(?:\.\d{1,2})?(?:\s*/\s*(?:oz|each))?", re.IGNORECASE),
]


def _extract_price(texts: list[str]) -> str:
    for pattern in _PRICE_PATTERNS:
        for text in texts:
            m = pattern.search(text)
            if m:
                return m.group(0).strip()
    return ""


def _extract_notes(content: str) -> str:
    """Pull the first 1–3 substantive, boilerplate-free sentences from a snippet."""
    if not content or len(content) < 20:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    clean: list[str] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 30:
            continue
        if _BOILERPLATE.search(s):
            continue
        clean.append(s)
        if len(clean) == 3:
            break
    return " ".join(clean)


_TASTING_VOCAB = {
    "flavor", "flavour", "taste", "aroma", "texture", "nutty", "creamy",
    "sharp", "mild", "tangy", "salty", "sweet", "bitter", "earthy", "pungent",
    "buttery", "fruity", "smoky", "aged", "firm", "soft", "rind", "paste",
    "notes", "finish", "palate", "crumbly", "melt", "melts", "rich", "complex",
    "caramel", "grassy", "floral", "herbal", "acidic", "lactic", "yeasty",
    "washed", "bloomy", "alpine", "cave", "cellar", "aftertaste", "mouth",
}


def _looks_like_tasting_notes(text: str) -> bool:
    """Return True only if the text contains genuine tasting language."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    return len(words & _TASTING_VOCAB) >= 3


def _llm_extract_notes(cheese_name: str, snippets: list[str]) -> str:
    """
    Ask the LLM to extract or synthesise professional tasting notes from raw
    search snippets. Only called when the fast-path regex extraction fails the
    quality check.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return ""
    try:
        from openai import OpenAI
        llm = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
        combined = "\n\n---\n\n".join(snippets[:4])
        response = llm.chat.completions.create(
            model=model,
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cheese expert. Extract or write 1–3 sentences of professional "
                        "tasting notes (flavor, texture, aroma) for the named cheese using the "
                        "provided search snippets. Return ONLY the tasting notes — no preamble, "
                        "no source attribution. If the snippets contain no useful tasting "
                        "information, return an empty string."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'Professional tasting notes for "{cheese_name}" cheese:\n\n{combined}'
                    ),
                },
            ],
        )
        result = (response.choices[0].message.content or "").strip()
        if len(result) < 20 or result.lower() in ("", "none", "n/a", "not found", "unknown"):
            return ""
        return result
    except Exception as exc:
        print(f"[enrichment/llm-notes] {cheese_name}: {exc}")
        return ""


def _fetch_tasting_notes(client: TavilyClient, cheese_name: str) -> str:
    """
    Fetch professional tasting notes for a cheese.

    Stage 1 — fast path: search cheese.com, then a general tasting-notes query.
              Return immediately if the extracted text looks like real tasting notes.
    Stage 2 — LLM fallback: if all snippets fail the quality check, pass the raw
              content to an LLM to extract or synthesise clean notes.
    """
    queries = [
        f"{cheese_name} site:cheese.com",
        f'"{cheese_name}" cheese tasting notes flavor',
        f"{cheese_name} cheese tasting notes flavor description",
    ]
    raw_snippets: list[str] = []

    for query in queries:
        try:
            resp = client.search(query, search_depth="basic", max_results=3)
            for r in resp.get("results", []):
                content = r.get("content", "")
                if not content:
                    continue
                notes = _extract_notes(content)
                if notes and _looks_like_tasting_notes(notes):
                    return notes
                if content:
                    raw_snippets.append(content)
        except Exception as exc:
            print(f"[enrichment/notes] {cheese_name}: {exc}")
        time.sleep(0.25)

    # Fast path found nothing useful — fall back to LLM
    return _llm_extract_notes(cheese_name, raw_snippets)


def _fetch_off_nutrition(cheese_name: str) -> str:
    """
    Fetch a one-line nutrition summary from Open Food Facts.
    Returns a formatted string like "Fat: 28.0g | Protein: 24.0g | Salt: 1.8g | 400 kcal | Allergens: milk"
    or '' if nothing useful is found.
    """
    try:
        resp = requests.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={
                "search_terms": f"{cheese_name} cheese",
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 5,
                "fields": "product_name,nutriments,allergens_tags",
            },
            timeout=8,
        )
        for product in resp.json().get("products", []):
            n = product.get("nutriments", {})
            if not n:
                continue
            parts = []
            for label, key in [("Fat", "fat_100g"), ("Protein", "proteins_100g"), ("Salt", "salt_100g")]:
                val = n.get(key)
                if val is not None:
                    parts.append(f"{label}: {float(val):.1f}g")
            kcal = n.get("energy-kcal_100g")
            if kcal:
                parts.append(f"{int(float(kcal))} kcal")
            allergens = [a.replace("en:", "") for a in product.get("allergens_tags", [])]
            if allergens:
                parts.append("Allergens: " + ", ".join(allergens))
            if parts:
                return " | ".join(parts) + " (per 100g)"
    except Exception as exc:
        print(f"[enrichment/off] {cheese_name}: {exc}")
    return ""


def _empty(val) -> bool:
    """True when a cell value is blank or not yet set."""
    return not val or not str(val).strip()


def search_cheese_info(
    cheese_name: str,
    from_where: str = "",
    fetch_store: bool = True,
    fetch_notes: bool = True,
) -> dict:
    """
    Fetch enrichment data for one cheese.
    fetch_store  – retrieve Link, Est. Price, and Image URL
    fetch_notes  – retrieve Prof. Tasting Notes (cheese.com preferred)
    """
    client = _tavily()
    result = {"Link": "", "Est. Price": "", "Image URL": "", "Prof. Tasting Notes": ""}

    if fetch_store:
        domain      = _store_domain(from_where)
        site_clause = f" site:{domain}" if domain else f" {from_where}".rstrip()
        try:
            resp    = client.search(
                f"{cheese_name} cheese{site_clause}",
                search_depth="advanced",
                max_results=5,
                include_images=True,
            )
            results = resp.get("results", [])
            images  = resp.get("images", [])

            if results:
                result["Link"]       = results[0]["url"]
                result["Est. Price"] = _extract_price([r.get("content", "") for r in results])

            if images:
                result["Image URL"] = images[0]
            else:
                img_resp = client.search(
                    f"{cheese_name} cheese",
                    search_depth="basic",
                    max_results=3,
                    include_images=True,
                )
                result["Image URL"] = (img_resp.get("images") or [""])[0]

        except Exception as exc:
            print(f"[enrichment/store] {cheese_name}: {exc}")

    if fetch_notes:
        result["Prof. Tasting Notes"] = _fetch_tasting_notes(client, cheese_name)

    return result


def enrich_dataframe(
    df: pd.DataFrame,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> pd.DataFrame:
    df = df.copy()
    # "Image URL" is the internal working column; "Image" (formula) comes from the sheet
    if "Image URL" not in df.columns:
        df["Image URL"] = ""
    for col in ("Link", "Est. Price", "Prof. Tasting Notes", "Nutrition"):
        if col not in df.columns:
            df[col] = ""

    total = len(df)
    for i, (idx, row) in enumerate(df.iterrows()):
        name = row["Cheese Type"]

        # Determine which fields still need fetching
        # "Image" is the sheet column (holds the =IMAGE() formula once set)
        needs_link      = _empty(row.get("Link", ""))
        needs_price     = _empty(row.get("Est. Price", ""))
        needs_image     = _empty(row.get("Image", ""))
        needs_notes     = _empty(row.get("Prof. Tasting Notes", ""))
        needs_nutrition = _empty(row.get("Nutrition", ""))

        needs_store = needs_link or needs_price or needs_image

        if not needs_store and not needs_notes and not needs_nutrition:
            if progress_cb:
                progress_cb((i + 1) / total, f"{name} (skipped – already enriched)")
            continue

        if progress_cb:
            progress_cb(i / total, name)

        if needs_store or needs_notes:
            info = search_cheese_info(
                cheese_name=name,
                from_where=row.get("From Where", ""),
                fetch_store=needs_store,
                fetch_notes=needs_notes,
            )
            if needs_link  and info["Link"]:                df.at[idx, "Link"]                = info["Link"]
            if needs_price and info["Est. Price"]:          df.at[idx, "Est. Price"]          = info["Est. Price"]
            if needs_image and info["Image URL"]:           df.at[idx, "Image URL"]           = info["Image URL"]
            if needs_notes and info["Prof. Tasting Notes"]: df.at[idx, "Prof. Tasting Notes"] = info["Prof. Tasting Notes"]

        if needs_nutrition:
            nutrition = _fetch_off_nutrition(name)
            if nutrition:
                df.at[idx, "Nutrition"] = nutrition

        time.sleep(0.5)

    if progress_cb:
        progress_cb(1.0, "Done")
    return df
