# Cheese Tracker — Claude Code Instructions

## Running the app

```bash
source .venv/bin/activate       # or: python -m venv .venv && pip install -r requirements.txt
streamlit run app.py
```

The app hot-reloads on save. Restart fully when changing `.streamlit/config.toml` or `.env`.

## Environment variables

Stored in `.env` (copy from `.env.example`). Never commit `.env`.

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes | Path to Google service account key file |
| `OPENROUTER_API_KEY` | Yes | Recommendations, auto-tagging, tasting note extraction |
| `TAVILY_API_KEY` | Recommended | Web enrichment (links, prices, images) |
| `CHEESE_SHEET_NAME` | No | Sheet tab name, defaults to `"cheese"` |
| `OPENROUTER_MODEL` | No | Model slug, defaults to `"openai/gpt-4.1-mini"` |

## File map

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — all tabs, charts, session state, CSS |
| `sheets.py` | All Google Sheets I/O (read, enrich, append, recommendations sheet) |
| `enrichment.py` | Tavily web enrichment + Open Food Facts nutrition + LLM tasting note extraction |
| `recommendations.py` | OpenRouter recommendation prompts, similar-cheese search, image fallback, auto-tag |
| `.streamlit/config.toml` | Forces light theme — must exist or dark-mode systems break readability |
| `recommendations_cache.json` | Local disk cache for recommendation results (auto-created) |

## Google Sheets layout

Spreadsheet ID: `18CJ8MrQQw7y6K1rL6Uqa95CEF-X_2fqwUX_RnrZlyiI`

The workbook has two sheets:
- **cheese** (or `CHEESE_SHEET_NAME`) — main tasting log. Can contain multiple tables on the same tab; `_find_cheese_header()` scans rows to locate the `"Cheese Type"` header rather than assuming row 1.
- **Cheese Recommendation** — wishlist, auto-created on first pin.

### Cheese sheet columns

Core: `Cheese Type`, `Date` (Month YYYY), `From Where`, `Score`, `Tasting Notes`

Enrichment (added by the app): `Link`, `Est. Price`, `Image` (=IMAGE formula), `Prof. Tasting Notes`, `Nutrition`

Auto-tag (added by Add Entry form): `Milk Type`, `Style`, `Country`

## Key architecture patterns

### Enrichment skip logic
`enrich_dataframe()` checks each field individually — `needs_link`, `needs_price`, `needs_image`, `needs_notes`, `needs_nutrition` — and only fetches/writes fields that are currently empty. Re-running enrichment on an already-enriched sheet is safe and fast.

### Tasting note quality gate
`_fetch_tasting_notes()` runs a two-stage pipeline:
1. Fast path: regex extraction + `_looks_like_tasting_notes()` (requires ≥3 tasting-vocab words)
2. LLM fallback: passes raw snippets to the model when the fast path produces non-tasting content (blog titles, navigation menus, etc.)

### Recommendation prompt
`_build_prompt()` injects a `MY CHEESE PROFILE` block from the `Milk Type`, `Style`, and `Country` columns when they exist. The `why_youll_love_it` field always cites a specific cheese name and score from the collection.

### Session state keys (app.py)

| Key | Type | Purpose |
|---|---|---|
| `recommendations` | `list[dict]` | Current main recommendation set (seeded from disk cache) |
| `similar_recs` | `list[dict]` | Results from "Find me something like X" |
| `similar_to` | `str` | Base cheese name for similar recs display |
| `pinned_names` | `set[str]` | Names already in the Recommendation sheet |
| `add_auto_name` | `str` | Cheese name typed in the auto-tag lookup input |
| `add_tags` | `dict` | `{milk_type, style, country}` from last auto-tag call |
| `prefill_from_rec` | `dict` | Full rec dict set by "Mark as Tried"; consumed by Add Entry tab on next render |
| `_prefill_source` | `str` | Cheese name shown in the Add Entry pre-fill banner; cleared after successful submit |

## Design tokens (app.py top of file)

```
BG_APP      = "#F7F3EE"   warm off-white
BG_CARD     = "#FFFFFF"   widget/card backgrounds
BG_SIDEBAR  = "#1E0D07"   deep mahogany
ACCENT      = "#C8860A"   warm amber (primary buttons, chart highlights)
ACCENT_DARK = "#8A5C06"   hover/pressed state
TEXT_MAIN   = "#1A1208"   near-black body text
TEXT_MUTED  = "#6B5B4E"   captions, secondary labels
GRID        = "#EDE5DA"   chart gridlines, borders
```

All Plotly charts use `PLOT_LAYOUT` for consistent background and font.

## Common tasks

**Add a new enrichment column**
1. Add the column name to `ENRICHMENT_COLS` in `sheets.py`
2. Add a `needs_X` check and fetch call in `enrich_dataframe()` in `enrichment.py`
3. Add the column to the `update_enrichment()` batch loop in `sheets.py`

**Change the recommendation model**
Set `OPENROUTER_MODEL` in `.env`. The same model is used for recommendations, similar-cheese search, auto-tagging, and tasting note LLM extraction.

**Clear stale recommendation cache**
Delete `recommendations_cache.json` or use the "🗑 Clear Cache" button in the Recommendations tab.
