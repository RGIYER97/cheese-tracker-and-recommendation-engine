# 🧀 Cheese Tracker & Discovery Engine

A personal Streamlit dashboard for logging cheese tastings, enriching your collection with web data, and getting AI-powered recommendations — all backed by a Google Sheet you already own.

## Features

### 📊 Dashboard
- Score distribution histogram
- Average score by store (bar chart)
- Top flavor keywords across all tasting notes
- Score over time with a smoothed trend line
- **Taste Fingerprint** — a radar chart showing your weighted flavor profile (Tangy, Creamy, Funky, Fruity, Nutty, Sharp, Salty, Smoky) across your entire collection

### 🧀 My Collection
- Sortable table of every cheese with color-coded scores
- **Enrich All Cheeses** — one click fetches official store links, estimated prices, an inline image formula, professional tasting notes (via cheese.com + LLM fallback), and nutrition data from Open Food Facts, writing everything back to your sheet
- **Compare Cheeses** — pick 2–3 cheeses for a side-by-side score and flavor radar overlay

### ➕ Add Entry
- Log a new cheese directly to your Google Sheet
- **Auto-fill details** — type a cheese name and click the button to have an LLM infer milk type, style, and country of origin; fields are pre-filled but fully editable
- New `Milk Type`, `Style`, and `Country` columns are created in the sheet automatically on first use

### ✨ Recommendations
- AI recommendations personalised to your highest-rated cheeses, tasting notes, and tagged profile (milk type, style, country breakdown)
- Each recommendation includes: flavor profile, *"Because you gave X a Y/10 for Z…"* reasoning, tasting note tags, price range, store locations (Aldi/Trader Joe's first → Whole Foods/Lidl → specialty shops near South Orange NJ / Manhattan), and pairing suggestions
- **Pin to Wishlist** — saves to a dedicated *Cheese Recommendation* tab in your sheet with tasting notes, price, store link, and an inline image
- **Mark as Tried** — pre-fills the Add Entry form from a wishlist card with one click
- **Find Me Something Like X** — pick any cheese from your collection and get 3 close alternatives
- Local disk cache so recommendations persist across browser refreshes

## Setup

### Prerequisites
- Python 3.11+
- A Google Sheet with a cheese tasting log (see [Sheet format](#sheet-format) below)
- A [Google Cloud service account](https://console.cloud.google.com/) with Sheets + Drive APIs enabled
- An [OpenRouter API key](https://openrouter.ai/keys)
- A [Tavily API key](https://app.tavily.com/) *(optional but recommended for enrichment and images)*

### Installation

```bash
git clone <repo>
cd "Cheese Tracker"

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-...           # optional
OPENROUTER_MODEL=openai/gpt-4.1-mini   # optional, see below
```

Share your Google Sheet with the service account email (give it **Editor** access).

### Running

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

## Sheet format

The app looks for a tab whose first column header is `Cheese Type`. It scans all tabs automatically, so the cheese table can share a tab with other data (e.g. an apple log).

Minimum columns needed to start:

| Cheese Type | Date | From Where | Score | Tasting Notes |
|---|---|---|---|---|
| Manchego | May 2025 | Trader Joe's | 9 | Nutty, firm, slightly salty |

The app will add enrichment columns (`Link`, `Est. Price`, `Image`, `Prof. Tasting Notes`, `Nutrition`) and auto-tag columns (`Milk Type`, `Style`, `Country`) as needed — you don't need to create them manually.

## Model selection

Set `OPENROUTER_MODEL` in `.env` to any model available on OpenRouter:

| Use case | Suggested model |
|---|---|
| Best quality | `anthropic/claude-sonnet-4` |
| Balanced (default) | `openai/gpt-4.1-mini` |
| Lower cost | `meta-llama/llama-3.3-70b-instruct` |

The same model handles recommendations, similar-cheese search, auto-tagging, and tasting note extraction.

## Project structure

```
Cheese Tracker/
├── app.py                  # Streamlit UI
├── sheets.py               # Google Sheets I/O
├── enrichment.py           # Tavily enrichment + Open Food Facts + LLM notes
├── recommendations.py      # OpenRouter recommendations & tagging
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── config.toml         # Light theme config (required for correct rendering)
└── recommendations_cache.json   # Auto-created; safe to delete
```

## API usage notes

| Action | APIs called |
|---|---|
| Load data | Google Sheets only |
| Enrich All Cheeses | Tavily (per cheese: 1–3 searches) + Open Food Facts (1 request) + OpenRouter (LLM fallback for tasting notes, only when needed) |
| Generate Recommendations | OpenRouter (1 call) + Tavily (1 image search per recommendation) |
| Find Similar | OpenRouter (1 call) + Tavily (image searches) |
| Auto-fill details | OpenRouter (1 call, max 120 tokens) |
| Pin to Wishlist | Google Sheets only |
