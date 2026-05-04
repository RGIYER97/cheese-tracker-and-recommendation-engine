import os
import re
import json
from pathlib import Path
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = Path(__file__).parent / "recommendations_cache.json"


def _load_rec_cache() -> list[dict]:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_rec_cache(recs: list[dict]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cheese Tracker",
    page_icon="🧀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ──────────────────────────────────────────────────────────────
# Palette: white main area · mahogany sidebar · amber accent · near-black text
BG_APP      = "#F7F3EE"   # warm off-white – easy on the eyes
BG_CARD     = "#FFFFFF"   # pure white cards
BG_PLOT     = "#FFFFFF"   # chart canvas
BG_PAPER    = "#F7F3EE"   # chart surround matches page
BG_SIDEBAR  = "#1E0D07"   # deep mahogany
ACCENT      = "#C8860A"   # warm amber
ACCENT_DARK = "#8A5C06"   # darker amber for hover/pressed
TEXT_MAIN   = "#1A1208"   # near-black
TEXT_MUTED  = "#6B5B4E"   # muted brown-grey
GRID        = "#EDE5DA"   # subtle warm grid

st.markdown(
    f"""
    <style>

    /* ═══════════════════════════════════════════════════════════
       APP SHELL
    ═══════════════════════════════════════════════════════════ */
    .stApp {{ background: {BG_APP} !important; }}
    [data-testid="stHeader"] {{ background: {BG_APP} !important; border-bottom: 1px solid {GRID}; }}
    .block-container {{ padding-top: 1.4rem; max-width: 1200px; }}

    /* ═══════════════════════════════════════════════════════════
       GLOBAL TEXT — force dark text on every element in main area
    ═══════════════════════════════════════════════════════════ */
    .stApp, .stApp p, .stApp span, .stApp div, .stApp label,
    .stApp li, .stApp td, .stApp th, .stApp small,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] * {{
        color: {TEXT_MAIN};
    }}
    h1 {{ color: {TEXT_MAIN} !important; font-weight: 700; letter-spacing: -0.5px; }}
    h2, h3 {{ color: {TEXT_MAIN} !important; font-weight: 600; }}
    p, li {{ color: {TEXT_MAIN} !important; }}
    a {{ color: {ACCENT_DARK} !important; }}

    /* captions / muted helpers */
    [data-testid="stCaptionContainer"] p,
    [data-testid="stCaptionContainer"] span,
    .stCaption, small {{
        color: {TEXT_MUTED} !important;
    }}

    /* markdown */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SIDEBAR
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSidebar"] {{
        background: {BG_SIDEBAR} !important;
    }}
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] small {{
        color: #F0E4D4 !important;
    }}
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{ color: #FFD9A0 !important; }}
    [data-testid="stSidebar"] hr {{ border-color: #4A2810 !important; }}
    [data-testid="stSidebar"] a {{ color: #FFD9A0 !important; }}
    [data-testid="stSidebar"] .stButton > button {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: {ACCENT_DARK} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       WIDGET LABELS
    ═══════════════════════════════════════════════════════════ */
    label, [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       TEXT INPUTS & TEXT AREAS
    ═══════════════════════════════════════════════════════════ */
    input, textarea {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border-color: #C8A878 !important;
    }}
    input::placeholder, textarea::placeholder {{
        color: {TEXT_MUTED} !important;
    }}
    [data-baseweb="input"],
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"],
    [data-baseweb="textarea"] > div {{
        background: {BG_CARD} !important;
        border-color: #C8A878 !important;
    }}
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SELECT / DROPDOWN
    ═══════════════════════════════════════════════════════════ */
    [data-baseweb="select"] > div {{
        background: {BG_CARD} !important;
        border-color: #C8A878 !important;
    }}
    [data-baseweb="select"] span,
    [data-baseweb="select"] div {{
        color: {TEXT_MAIN} !important;
    }}
    /* dropdown list */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="menu"] ul,
    [role="listbox"],
    [role="option"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
    }}
    [role="option"]:hover,
    [data-baseweb="menu"] li:hover {{
        background: {GRID} !important;
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       MULTISELECT
    ═══════════════════════════════════════════════════════════ */
    [data-baseweb="tag"] {{
        background: #FFF3DC !important;
        border: 1px solid #D4A84A !important;
    }}
    [data-baseweb="tag"] span {{
        color: #5C3200 !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SLIDER
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] p,
    [data-testid="stSlider"] span,
    [data-testid="stSlider"] div {{
        color: {TEXT_MAIN} !important;
    }}
    [data-testid="stTickBar"],
    [data-testid="stTickBarMin"],
    [data-testid="stTickBarMax"] {{
        color: {TEXT_MUTED} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       CHECKBOX & RADIO
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] p,
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] p {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       DATE INPUT
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stDateInput"] input {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border-color: #C8A878 !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       BUTTONS
    ═══════════════════════════════════════════════════════════ */
    .stButton > button {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border: 1px solid #C8A878 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }}
    .stButton > button:hover {{
        background: {GRID} !important;
        border-color: {ACCENT} !important;
    }}
    /* primary variant */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.45rem 1.2rem !important;
    }}
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {{
        background: {ACCENT_DARK} !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;
    }}
    /* secondary variant */
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border: 1px solid #C8A878 !important;
    }}

    /* form submit button */
    [data-testid="stFormSubmitButton"] > button {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.45rem 1.4rem !important;
    }}
    [data-testid="stFormSubmitButton"] > button:hover {{
        background: {ACCENT_DARK} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       FORMS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stForm"] {{
        background: {BG_CARD} !important;
        border: 1px solid {GRID} !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       EXPANDERS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stExpander"] {{
        background: {BG_CARD} !important;
        border: 1px solid {GRID} !important;
        border-radius: 8px !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    .streamlit-expanderHeader,
    .streamlit-expanderHeader p {{
        color: {TEXT_MAIN} !important;
        background: {BG_CARD} !important;
    }}
    .streamlit-expanderContent,
    [data-testid="stExpanderDetails"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
    }}
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] li,
    [data-testid="stExpanderDetails"] a {{
        color: {TEXT_MAIN} !important;
    }}
    [data-testid="stExpanderDetails"] a {{
        color: {ACCENT_DARK} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       ALERT BOXES (info / success / warning / error)
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stAlert"] {{
        border-radius: 8px !important;
    }}
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span,
    [data-testid="stAlert"] div {{
        color: {TEXT_MAIN} !important;
    }}
    /* info */
    [data-testid="stAlert"][kind="info"],
    div[class*="stInfo"] {{
        background: #EAF2FB !important;
        border-left-color: #2980B9 !important;
    }}
    /* success */
    [data-testid="stAlert"][kind="success"],
    div[class*="stSuccess"] {{
        background: #EAFAF1 !important;
        border-left-color: #27AE60 !important;
    }}
    /* warning */
    [data-testid="stAlert"][kind="warning"],
    div[class*="stWarning"] {{
        background: #FEF9E7 !important;
        border-left-color: #E67E22 !important;
    }}
    /* error */
    [data-testid="stAlert"][kind="error"],
    div[class*="stError"] {{
        background: #FDEDEC !important;
        border-left-color: #C0392B !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       METRIC CARDS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stMetric"] {{
        background: {BG_CARD} !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        border: 1px solid {GRID} !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    }}
    [data-testid="stMetricValue"] {{ color: {TEXT_MAIN} !important; font-weight: 700 !important; }}
    [data-testid="stMetricLabel"] {{ color: {TEXT_MUTED} !important; font-size: 0.85rem !important; }}
    [data-testid="stMetricDelta"] {{ font-size: 0.82rem !important; }}

    /* ═══════════════════════════════════════════════════════════
       TABS
    ═══════════════════════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {{
        background: {GRID} !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {TEXT_MUTED} !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        padding: 6px 18px !important;
        background: transparent !important;
    }}
    .stTabs [aria-selected="true"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.10) !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       DATAFRAME / TABLE
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stDataFrame"] {{ border-radius: 10px !important; overflow: hidden !important; }}
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] td {{
        color: {TEXT_MAIN} !important;
        background: {BG_CARD} !important;
    }}
    [data-testid="stDataFrame"] thead th {{
        background: {GRID} !important;
        color: {TEXT_MAIN} !important;
        font-weight: 600 !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       PROGRESS BAR
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stProgress"] > div {{
        background: {GRID} !important;
        border-radius: 4px !important;
    }}
    [data-testid="stProgress"] > div > div {{
        background: {ACCENT} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SPINNER
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSpinner"] p,
    [data-testid="stSpinner"] span {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       TOAST NOTIFICATIONS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="toastContainer"] div,
    [data-testid="toastContainer"] p {{
        color: {TEXT_MAIN} !important;
        background: {BG_CARD} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       DIVIDERS
    ═══════════════════════════════════════════════════════════ */
    hr {{ border-color: {GRID} !important; }}

    /* ═══════════════════════════════════════════════════════════
       CUSTOM COMPONENTS
    ═══════════════════════════════════════════════════════════ */
    /* Recommendation card */
    .cheese-card {{
        background: {BG_CARD};
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        border-left: 5px solid {ACCENT};
    }}
    .cheese-card h3 {{ margin: 0 0 4px 0; color: {TEXT_MAIN} !important; }}
    .cheese-card small {{ color: {TEXT_MUTED} !important; }}

    /* Flavor tags */
    .tag {{
        background: #FFF3DC;
        border: 1px solid #D4A84A;
        color: #5C3200 !important;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.79em;
        margin: 3px 2px;
        display: inline-block;
    }}

    </style>
    """,
    unsafe_allow_html=True,
)

# ── Constants ──────────────────────────────────────────────────────────────────
# Flavor axes for radar charts — keywords that indicate presence of each axis
FLAVOR_AXES: dict[str, list[str]] = {
    "Tangy":   ["tangy", "tang", "tart", "acidic", "acetic", "zesty", "lactic"],
    "Creamy":  ["creamy", "cream", "smooth", "buttery", "butter", "rich", "fatty", "velvety", "silky", "triple"],
    "Funky":   ["funky", "funk", "pungent", "earthy", "mushroom", "umami", "barnyard", "washed", "alpiny"],
    "Fruity":  ["fruity", "fruit", "sweet", "apple", "pear", "apricot", "blueberry", "tropical", "citrus", "honey", "lemon", "cherry", "jolly"],
    "Nutty":   ["nutty", "nut", "almond", "hazelnut", "walnut"],
    "Sharp":   ["sharp", "bite", "piquant", "spicy", "pepper", "peppery", "jalap", "chili", "kick", "heat", "spice"],
    "Salty":   ["salty", "salt", "briny", "savory"],
    "Smoky":   ["smoky", "smoke", "smoked", "applewood"],
}

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "and", "but", "or", "for", "in", "on", "at", "to",
    "from", "by", "of", "with", "as", "it", "its", "this", "that", "very",
    "quite", "really", "super", "much", "more", "less", "not", "no", "good",
    "great", "like", "similar", "equivalent", "than", "some", "bit", "hint",
    "hints", "slightly", "light", "heavy", "texture", "textured", "flavor",
    "taste", "tastes", "tasting", "notes", "cheese", "cheeses", "real",
    "nice", "end", "kick", "big", "when", "melted", "well", "also",
}

# Shared Plotly layout defaults
PLOT_LAYOUT = dict(
    plot_bgcolor=BG_PLOT,
    paper_bgcolor=BG_PAPER,
    font=dict(color=TEXT_MAIN, family="Segoe UI, Arial, sans-serif"),
    title_font=dict(color=TEXT_MAIN, size=17, family="Segoe UI, Arial, sans-serif"),
    title_x=0.0,
    margin=dict(l=0, r=0, t=40, b=0),
)


def apply_axes(fig, x_grid=True, y_grid=True):
    if x_grid:
        fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, tickfont=dict(color=TEXT_MAIN))
    else:
        fig.update_xaxes(showgrid=False, zerolinecolor=GRID, tickfont=dict(color=TEXT_MAIN))
    if y_grid:
        fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, tickfont=dict(color=TEXT_MAIN))
    else:
        fig.update_yaxes(showgrid=False, zerolinecolor=GRID, tickfont=dict(color=TEXT_MAIN))
    return fig


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flavor_scores(notes: str) -> dict[str, float]:
    """Score a single cheese's tasting notes against each flavor axis (0–10)."""
    text = notes.lower()
    return {
        axis: min(sum(1 for kw in keywords if kw in text) * 3.0, 10.0)
        for axis, keywords in FLAVOR_AXES.items()
    }


def _user_fingerprint(df: pd.DataFrame) -> dict[str, float]:
    """Weighted-average flavor profile across all cheeses, weighted by score."""
    totals = {ax: 0.0 for ax in FLAVOR_AXES}
    weight_sum = 0.0
    for _, row in df.iterrows():
        notes = str(row.get("Tasting Notes") or "")
        w = float(row["Score"]) if pd.notna(row.get("Score")) else 5.0
        for ax, val in _flavor_scores(notes).items():
            totals[ax] += val * w
        weight_sum += w
    if weight_sum == 0:
        return {ax: 0.0 for ax in FLAVOR_AXES}
    return {ax: totals[ax] / weight_sum for ax in FLAVOR_AXES}


def _make_radar(series: dict[str, dict[str, float]], title: str = "") -> go.Figure:
    """Overlay one or more flavor-score dicts on a polar/radar chart."""
    axes = list(FLAVOR_AXES.keys())
    palette = [ACCENT, "#2E8B40", "#4A7FD9", "#9B59B6", "#E74C3C"]
    fig = go.Figure()
    for i, (label, scores) in enumerate(series.items()):
        vals = [scores.get(ax, 0) for ax in axes]
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=axes + [axes[0]],
            fill="toself",
            name=label,
            line=dict(color=color, width=2),
            fillcolor=color,
            opacity=0.22,
        ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(color=TEXT_MUTED, size=9), gridcolor=GRID),
            angularaxis=dict(tickfont=dict(color=TEXT_MAIN, size=12)),
            bgcolor=BG_PLOT,
        ),
        title=dict(text=title, font=dict(color=TEXT_MAIN, size=17)),
        paper_bgcolor=BG_PAPER,
        font=dict(color=TEXT_MAIN),
        showlegend=True,
        legend=dict(font=dict(color=TEXT_MAIN)),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def _parse_image_url(formula: str) -> str:
    """Extract the raw URL from a Sheets =IMAGE("url", 1) formula."""
    m = re.match(r'=IMAGE\("([^"]+)"', formula.strip())
    return m.group(1) if m else ""


def flavor_keywords(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    notes = " ".join(df["Tasting Notes"].fillna("").tolist()).lower()
    tokens = re.findall(r"[a-z]+", notes)
    counts = Counter(t for t in tokens if t not in STOP_WORDS and len(t) > 2)
    rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return pd.DataFrame(rows, columns=["Keyword", "Count"])


def score_style(val):
    if pd.isna(val):
        return f"color: {TEXT_MUTED}"
    if val >= 9:
        return "color: #1B6B30; font-weight: 700"   # dark green
    if val >= 7:
        return f"color: {ACCENT_DARK}; font-weight: 700"  # amber
    return "color: #B71C1C; font-weight: 700"        # red


def _local_confidence(rec: dict, df: pd.DataFrame) -> float | None:
    """
    Score 1–10: how well a recommendation's tags (milk type, style, country)
    match the user's top-rated cheeses (score >= 7), weighted by score.
    Returns None when no tag columns exist to compare against.
    """
    top = df[df["Score"] >= 7].copy()
    if top.empty:
        return None
    total_w = float(top["Score"].sum())
    if total_w == 0:
        return None

    signals: list[float] = []

    rec_milk = (rec.get("milk_type") or "").strip().lower()
    if rec_milk and "Milk Type" in top.columns:
        mask = top["Milk Type"].fillna("").str.strip().str.lower() == rec_milk
        signals.append(float(top.loc[mask, "Score"].sum()) / total_w)

    rec_type_words = set((rec.get("type") or "").lower().split())
    if rec_type_words and "Style" in top.columns:
        mask = top["Style"].fillna("").apply(
            lambda s: bool(rec_type_words & set(s.lower().split()))
        )
        signals.append(float(top.loc[mask, "Score"].sum()) / total_w)

    rec_country = (rec.get("origin") or "").split(",")[0].strip().lower()
    if rec_country and "Country" in top.columns:
        mask = top["Country"].fillna("").str.strip().str.lower() == rec_country
        signals.append(float(top.loc[mask, "Score"].sum()) / total_w)

    if not signals:
        return None
    return round(1.0 + (sum(signals) / len(signals)) * 9.0, 1)


def render_rec_card(rec: dict, card_idx: int, is_pinned: bool = False):
    model_conf  = rec.get("confidence", "")
    local_conf  = _local_confidence(rec, df)

    conf_parts: list[str] = []
    if model_conf:
        conf_parts.append(f"Model: {model_conf}/10")
    if local_conf is not None:
        conf_parts.append(f"Your match: {local_conf}/10")
    conf_str = "  ·  " + "  ·  ".join(conf_parts) if conf_parts else ""

    st.markdown(
        f"""<div class="cheese-card">
            <h3>{rec['name']}</h3>
            <small>{rec.get('origin','')} · {rec.get('type','')} · {rec.get('milk_type','')}{conf_str}</small>
        </div>""",
        unsafe_allow_html=True,
    )

    pic = rec.get("picture_url", "")
    if pic:
        try:
            st.image(pic, width=300)
        except Exception:
            pass

    st.markdown(f"**Flavor Profile:** {rec.get('flavor_profile', '')}")
    st.markdown(f"**Why you'll love it:** _{rec.get('why_youll_love_it', '')}_")

    notes = rec.get("tasting_notes", [])
    if notes:
        st.markdown("".join(f'<span class="tag">{n}</span>' for n in notes), unsafe_allow_html=True)

    if price := rec.get("price_range", ""):
        st.markdown(f"💰 **{price}**")

    if pairs := rec.get("pairs_with", []):
        st.markdown("🍷 **Pairs with:** " + ", ".join(pairs))

    if stores := rec.get("stores", []):
        st.markdown("📍 **Where to find it:**")
        for store in stores:
            loc = store.get("location", "")
            note = store.get("notes", "")
            line = f"**{store['name']}** — {loc}"
            if note:
                line += f" · _{note}_"
            st.markdown(f"- {line}")

    if link := rec.get("link", ""):
        st.markdown(f"[Learn more / buy online ↗]({link})")

    # ── Pin / Mark as Tried buttons ───────────────────────────────────────────
    if is_pinned:
        st.markdown("✅ **Saved to your Cheese Recommendation sheet**")
        if st.button("☑️ Mark as Tried", key=f"tried_{card_idx}", help="Pre-fill the Add Entry form with this cheese"):
            st.session_state["prefill_from_rec"] = rec
            st.toast(f"Switch to the Add Entry tab to log '{rec.get('name', '')}'!")
            st.rerun()
    else:
        if st.button("📌 Save to Wishlist", key=f"pin_{card_idx}", type="secondary"):
            try:
                from sheets import pin_recommendation
                pin_recommendation(rec)
                st.session_state["pinned_names"].add(rec.get("name", ""))
                st.toast(f"'{rec.get('name', '')}' saved to your spreadsheet!")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save to sheet: {exc}")

    st.markdown("---")


# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Loading cheese data from Google Sheets…")
def load_data() -> pd.DataFrame:
    from sheets import load_cheese_data
    return load_cheese_data()


@st.cache_data(ttl=60, show_spinner="Loading wishlist…")
def load_wishlist_data() -> list[dict]:
    from sheets import load_wishlist
    return load_wishlist()


try:
    df = load_data()
except EnvironmentError:
    st.error("**Google Sheets credentials not configured.**")
    st.info(
        "Set `GOOGLE_SERVICE_ACCOUNT_JSON` in your `.env` file to the path of your "
        "service-account JSON key. See `.env.example` for details."
    )
    st.stop()
except Exception as exc:
    st.error(f"Failed to load sheet data: {exc}")
    st.stop()


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🧀 Cheese Tracker & Discovery Engine")
st.caption("Tracking preferences · Enriching data · Finding new favourites")
st.divider()

# ── Top-level metrics ──────────────────────────────────────────────────────────
best_row  = df.loc[df["Score"].idxmax()]
top_store = df.groupby("From Where")["Score"].mean().idxmax()

c1, c2, c3, c4 = st.columns(4)
c1.metric("🧀 Cheeses Tried",    len(df))
c2.metric("⭐ Average Score",     f"{df['Score'].mean():.1f} / 10")
c3.metric("🏆 Top Cheese",        best_row["Cheese Type"], f"{best_row['Score']}/10")
c4.metric("🏪 Best Source (avg)", top_store)
st.divider()

# Seed recommendation cache from disk on first run of this session
if "recommendations" not in st.session_state:
    st.session_state["recommendations"] = _load_rec_cache()


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_dash, tab_collection, tab_add, tab_recs, tab_wishlist = st.tabs(
    ["📊 Dashboard", "🧀 My Collection", "➕ Add Entry", "✨ Recommendations", "📋 Wishlist"]
)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dash:
    st.subheader("Score Distribution")
    fig_hist = px.histogram(
        df,
        x="Score",
        nbins=14,
        color_discrete_sequence=[ACCENT],
        labels={"Score": "Score (out of 10)", "count": "# Cheeses"},
        title="How I've rated my cheeses",
    )
    fig_hist.update_layout(bargap=0.12, **PLOT_LAYOUT)
    apply_axes(fig_hist, x_grid=False, y_grid=True)
    st.plotly_chart(fig_hist, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Average Score by Store")
        store_avg = (
            df.groupby("From Where")["Score"]
            .agg(["mean", "count"])
            .rename(columns={"mean": "Avg Score", "count": "Cheeses Tried"})
            .sort_values("Avg Score", ascending=True)
            .reset_index()
        )
        fig_store = px.bar(
            store_avg,
            x="Avg Score",
            y="From Where",
            orientation="h",
            color="Avg Score",
            color_continuous_scale=[[0, "#D9534F"], [0.5, "#F0AD4E"], [1, "#2E8B40"]],
            range_color=[4, 10],
            hover_data={"Cheeses Tried": True},
            title="Which shops score best?",
        )
        fig_store.update_layout(coloraxis_showscale=False, **PLOT_LAYOUT)
        apply_axes(fig_store, x_grid=True, y_grid=False)
        st.plotly_chart(fig_store, use_container_width=True)

    with col_right:
        st.subheader("Top Flavor Keywords")
        kw_df = flavor_keywords(df, top_n=18)
        fig_kw = px.bar(
            kw_df,
            x="Count",
            y="Keyword",
            orientation="h",
            color="Count",
            color_continuous_scale=[[0, "#F5D78A"], [1, ACCENT_DARK]],
            title="Most common tasting-note words",
        )
        fig_kw.update_layout(
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
            **PLOT_LAYOUT,
        )
        apply_axes(fig_kw, x_grid=True, y_grid=False)
        st.plotly_chart(fig_kw, use_container_width=True)

    df_time = df.dropna(subset=["Date"]).sort_values("Date")
    if not df_time.empty:
        st.subheader("Score Over Time")
        fig_time = px.scatter(
            df_time,
            x="Date",
            y="Score",
            hover_name="Cheese Type",
            hover_data={"Tasting Notes": True, "From Where": True},
            color="Score",
            color_continuous_scale=[[0, "#D9534F"], [0.5, "#F0AD4E"], [1, "#2E8B40"]],
            range_color=[3, 10],
            size_max=14,
            title="My cheese journey",
        )
        try:
            fig_time.add_traces(
                px.scatter(df_time, x="Date", y="Score", trendline="lowess").data[1:]
            )
            fig_time.data[-1].update(line=dict(color=ACCENT, width=2.5))
        except Exception:
            pass
        fig_time.update_layout(coloraxis_showscale=True, **PLOT_LAYOUT)
        apply_axes(fig_time)
        st.plotly_chart(fig_time, use_container_width=True)

    st.divider()
    st.subheader("Your Taste Fingerprint")
    st.caption(
        "Weighted average of all your flavor axes, scaled by score — "
        "higher-rated cheeses pull the shape more strongly."
    )
    fingerprint = _user_fingerprint(df)
    _, col_fp, _ = st.columns([1, 2, 1])
    with col_fp:
        st.plotly_chart(_make_radar({"My Palate": fingerprint}), use_container_width=True)

    if "Country" in df.columns:
        map_df = (
            df[df["Country"].str.strip() != ""]
            .groupby("Country")["Score"]
            .agg(avg_score="mean", count="count")
            .reset_index()
        )
        if not map_df.empty:
            st.divider()
            st.subheader("Origin Map")
            st.caption("Countries you've tried, shaded by average score.")
            fig_map = px.choropleth(
                map_df,
                locations="Country",
                locationmode="country names",
                color="avg_score",
                hover_name="Country",
                hover_data={"count": True, "avg_score": ":.1f"},
                color_continuous_scale=[[0, "#D9534F"], [0.5, "#F0AD4E"], [1, "#2E8B40"]],
                range_color=[4, 10],
                labels={"avg_score": "Avg Score", "count": "# Cheeses"},
                title="Average score by country of origin",
            )
            fig_map.update_layout(
                geo=dict(showframe=False, showcoastlines=True, bgcolor=BG_PAPER),
                coloraxis_colorbar=dict(title="Avg Score"),
                **PLOT_LAYOUT,
            )
            st.plotly_chart(fig_map, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — MY COLLECTION
# ─────────────────────────────────────────────────────────────────────────────
with tab_collection:
    st.subheader("All Cheeses")

    col_sort, col_order = st.columns([2, 1])
    with col_sort:
        sort_col = st.selectbox("Sort by", ["Score", "Date", "Cheese Type"], index=0)
    with col_order:
        sort_asc = st.checkbox("Ascending", value=False)

    display_df = df.sort_values(sort_col, ascending=sort_asc, na_position="last")

    def _fmt_source(v: object) -> str:
        s = str(v).strip() if v and str(v).strip() else ""
        return {"cheese.com": "✅ cheese.com", "LLM": "🤖 LLM", "web": "🌐 web"}.get(s, s)

    fmt: dict = {
        "Score": lambda v: f"{v:.1f}" if pd.notna(v) else "",
        "Date":  lambda d: d.strftime("%b %Y") if pd.notna(d) else "",
    }
    if "Notes Source" in display_df.columns:
        fmt["Notes Source"] = _fmt_source

    styled = (
        display_df.style
        .map(score_style, subset=["Score"])
        .format(fmt)
    )
    st.dataframe(styled, use_container_width=True, height=540)

    st.divider()
    st.subheader("Enrich with Links, Prices & Images")
    st.caption(
        "Searches official store sites via Tavily for each cheese and writes results "
        "back to your Google Sheet. Takes ~30 s for the full list."
    )

    if st.button("🔍 Enrich All Cheeses", type="primary"):
        if not os.environ.get("TAVILY_API_KEY"):
            st.error("TAVILY_API_KEY is not set. Add it to your .env file.")
        else:
            from enrichment import enrich_dataframe
            from sheets import update_enrichment

            pbar   = st.progress(0.0)
            status = st.empty()

            def on_progress(frac: float, name: str):
                pbar.progress(frac)
                status.text(f"Searching: {name}")

            enriched = enrich_dataframe(df, progress_cb=on_progress)
            pbar.progress(1.0)
            status.text("Writing back to Google Sheet…")
            update_enrichment(enriched)
            status.empty()
            pbar.empty()
            st.success("Done! Reload the page to see enriched columns.")
            st.cache_data.clear()

    # ── Compare ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🔍 Compare Cheeses")
    st.caption("Select 2 or 3 cheeses to compare their scores and flavor profiles side by side.")

    selected = st.multiselect(
        "Choose cheeses to compare",
        options=df["Cheese Type"].tolist(),
        max_selections=3,
        placeholder="Pick 2–3 cheeses…",
    )

    if len(selected) >= 2:
        cmp_df = (
            df[df["Cheese Type"].isin(selected)]
            .drop_duplicates("Cheese Type")
            .set_index("Cheese Type")
            .loc[selected]   # preserve multiselect order
            .reset_index()
        )

        # Side-by-side score + notes cards
        cmp_cols = st.columns(len(selected))
        for col, (_, row) in zip(cmp_cols, cmp_df.iterrows()):
            with col:
                date_val = row["Date"].strftime("%b %Y") if pd.notna(row.get("Date")) else "—"
                st.markdown(
                    f"""<div class="cheese-card">
                        <h3 style="font-size:1rem;margin-bottom:2px">{row['Cheese Type']}</h3>
                        <small>{row.get('From Where','—')} · {date_val}</small>
                    </div>""",
                    unsafe_allow_html=True,
                )
                score_val = f"{row['Score']:.1f} / 10" if pd.notna(row.get("Score")) else "—"
                st.metric("Score", score_val)
                st.markdown(f"_{row.get('Tasting Notes', '—')}_")

        # Radar overlay
        radar_series = {
            row["Cheese Type"]: _flavor_scores(str(row.get("Tasting Notes") or ""))
            for _, row in cmp_df.iterrows()
        }
        st.plotly_chart(_make_radar(radar_series, title="Flavor Comparison"), use_container_width=True)
    elif selected:
        st.caption("Select at least one more cheese to compare.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — ADD ENTRY
# ─────────────────────────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Log a New Cheese")
    st.caption("Appends a new row directly to your Google Sheet and refreshes the app.")

    # ── Handle pre-fill from wishlist ─────────────────────────────────────────
    if "prefill_from_rec" in st.session_state:
        rec_p = st.session_state.pop("prefill_from_rec")
        st.session_state["add_auto_name"] = rec_p.get("name", "")
        tags_prefill: dict = {}
        if rec_p.get("milk_type"):
            tags_prefill["milk_type"] = rec_p["milk_type"]
        if tags_prefill:
            st.session_state["add_tags"] = tags_prefill
        st.session_state["_prefill_source"] = rec_p.get("name", "")

    if prefill_source := st.session_state.get("_prefill_source"):
        st.info(f"Pre-filling from your wishlist: **{prefill_source}** — review the details below and click Add to Sheet.")

    # ── Auto-tag lookup (outside form so it can trigger a rerun) ──────────────
    tag_col_name, tag_col_btn = st.columns([3, 1])
    with tag_col_name:
        auto_name = st.text_input(
            "Cheese Name *",
            key="add_auto_name",
            placeholder="e.g. Manchego",
        )
    with tag_col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        autofill_clicked = st.button(
            "🔍 Auto-fill details",
            disabled=not auto_name.strip(),
            help="Uses AI to look up milk type, style, and country of origin",
        )

    if autofill_clicked:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.warning("OPENROUTER_API_KEY not set — auto-fill unavailable.")
        else:
            from recommendations import tag_cheese
            with st.spinner(f"Looking up details for {auto_name.strip()}…"):
                tags = tag_cheese(auto_name.strip())
            st.session_state["add_tags"] = tags
            st.rerun()

    tags: dict = st.session_state.get("add_tags", {})
    if tags:
        milk = tags.get("milk_type") or "?"
        style = tags.get("style") or "?"
        country = tags.get("country") or "?"
        st.caption(f"Auto-detected: **{milk}** milk · **{style}** · **{country}**")

    st.divider()

    # ── Entry form ────────────────────────────────────────────────────────────
    with st.form("add_cheese_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)

        with col_a:
            new_name = st.text_input(
                "Cheese Name *",
                value=st.session_state.get("add_auto_name", ""),
                placeholder="e.g. Manchego",
            )
            new_store = st.text_input("Where did you get it?", placeholder="e.g. Murray's Cheese")
            new_score = st.slider("Score", min_value=1.0, max_value=10.0, value=7.0, step=0.5)

        with col_b:
            new_date = st.date_input("Date Tried")
            new_notes = st.text_area(
                "Tasting Notes",
                placeholder="Describe the flavor, texture, aroma…",
                height=120,
            )

        st.markdown("**Details** — auto-filled from lookup, or edit manually")
        det_a, det_b, det_c = st.columns(3)

        milk_options = ["", "Cow", "Sheep", "Goat", "Mixed"]
        detected_milk = tags.get("milk_type", "")
        milk_idx = milk_options.index(detected_milk) if detected_milk in milk_options else 0

        with det_a:
            new_milk = st.selectbox("Milk Type", milk_options, index=milk_idx)
        with det_b:
            new_style = st.text_input("Style", value=tags.get("style", ""), placeholder="e.g. Semi-firm")
        with det_c:
            new_country = st.text_input("Country", value=tags.get("country", ""), placeholder="e.g. Spain")

        submitted = st.form_submit_button("➕ Add to Sheet", type="primary")

    if submitted:
        if not new_name.strip():
            st.error("Cheese name is required.")
        else:
            from sheets import append_cheese
            try:
                extra: dict[str, str] = {}
                if new_milk:
                    extra["Milk Type"] = new_milk
                if new_style.strip():
                    extra["Style"] = new_style.strip()
                if new_country.strip():
                    extra["Country"] = new_country.strip()
                append_cheese(
                    name=new_name.strip(),
                    date=new_date.strftime("%B %Y"),
                    from_where=new_store.strip(),
                    score=new_score,
                    tasting_notes=new_notes.strip(),
                    extra_fields=extra or None,
                )
                st.session_state.pop("add_tags", None)
                st.session_state.pop("_prefill_source", None)
                st.success(f"✅ **{new_name.strip()}** added! Use the sidebar refresh to reload your collection.")
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Could not save to sheet: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────
with tab_recs:
    st.subheader("AI-Powered Cheese Recommendations")
    st.caption(
        "An OpenRouter model analyses your highest-rated cheeses and tasting notes to surface "
        "cheeses you'll love, with specific shops near Harrison, NJ and Manhattan."
    )

    # Load pinned names from the sheet once per session
    if "pinned_names" not in st.session_state:
        with st.spinner("Loading your saved recommendations…"):
            try:
                from sheets import load_pinned_cheeses
                st.session_state["pinned_names"] = set(load_pinned_cheeses())
            except Exception:
                st.session_state["pinned_names"] = set()

    pinned_names: set[str] = st.session_state["pinned_names"]

    num_recs = st.slider("Number of recommendations", min_value=3, max_value=10, value=6)

    col_gen, col_clear = st.columns([3, 1])
    with col_gen:
        gen_clicked = st.button("✨ Generate New Recommendations", type="primary")
    with col_clear:
        if st.button("🗑 Clear Cache", help="Remove locally cached recommendations"):
            st.session_state["recommendations"] = []
            _save_rec_cache([])
            st.rerun()

    if gen_clicked:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.error("OPENROUTER_API_KEY is not set. Add it to your .env file.")
        else:
            from recommendations import get_recommendations, add_images

            with st.spinner("Analysing your cheese preferences…"):
                recs = get_recommendations(
                    df,
                    num_recs=num_recs,
                    already_pinned=sorted(pinned_names),
                )

            if os.environ.get("TAVILY_API_KEY"):
                with st.spinner("Fetching cheese images…"):
                    recs = add_images(recs)

            st.session_state["recommendations"] = recs
            _save_rec_cache(recs)

    recs: list[dict] = st.session_state.get("recommendations", [])

    if recs:
        n_pinned = sum(1 for r in recs if r.get("name", "") in pinned_names)
        st.markdown(f"### {len(recs)} Cheeses You Should Try  &nbsp;·&nbsp; {n_pinned} saved")
        for chunk_i in range(0, len(recs), 2):
            pair = recs[chunk_i : chunk_i + 2]
            cols = st.columns(len(pair))
            for j, (col, rec) in enumerate(zip(cols, pair)):
                with col:
                    render_rec_card(
                        rec,
                        card_idx=chunk_i + j,
                        is_pinned=rec.get("name", "") in pinned_names,
                    )
    elif not gen_clicked:
        st.info("No recommendations yet — click **Generate New Recommendations** to get started.")

    # ── Find me something like X ──────────────────────────────────────────────
    st.divider()
    st.subheader("🔎 Find Me Something Like…")
    st.caption("Pick a cheese from your collection and get 3 closely matched alternatives you haven't tried.")

    cheese_choices = sorted(df["Cheese Type"].dropna().unique().tolist())
    sim_col_a, sim_col_b = st.columns([3, 1])
    with sim_col_a:
        similar_to = st.selectbox(
            "Base cheese",
            options=[""] + cheese_choices,
            format_func=lambda x: "— choose a cheese —" if x == "" else x,
            label_visibility="collapsed",
        )
    with sim_col_b:
        find_similar_clicked = st.button(
            "Find Similar",
            type="primary",
            disabled=not similar_to,
        )

    if find_similar_clicked and similar_to:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.error("OPENROUTER_API_KEY is not set.")
        else:
            from recommendations import get_similar_recommendations, add_images as _add_images
            with st.spinner(f"Finding cheeses similar to {similar_to}…"):
                sim_recs = get_similar_recommendations(
                    similar_to,
                    df,
                    num_recs=3,
                    already_pinned=sorted(pinned_names),
                )
            if os.environ.get("TAVILY_API_KEY"):
                with st.spinner("Fetching images…"):
                    sim_recs = _add_images(sim_recs)
            st.session_state["similar_recs"] = sim_recs
            st.session_state["similar_to"] = similar_to

    sim_recs: list[dict] = st.session_state.get("similar_recs", [])
    if sim_recs:
        base = st.session_state.get("similar_to", "")
        st.markdown(f"**Cheeses similar to {base}:**")
        sim_cols = st.columns(min(len(sim_recs), 3))
        for j, (col, rec) in enumerate(zip(sim_cols, sim_recs)):
            with col:
                render_rec_card(
                    rec,
                    card_idx=1000 + j,
                    is_pinned=rec.get("name", "") in pinned_names,
                )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — WISHLIST
# ─────────────────────────────────────────────────────────────────────────────
with tab_wishlist:
    st.subheader("My Wishlist")
    st.caption("Cheeses you've pinned to try. Mark as Tried to pre-fill the Add Entry form, or remove ones you've decided against.")

    col_wl_refresh, _ = st.columns([1, 5])
    with col_wl_refresh:
        if st.button("🔄 Refresh", key="wl_refresh"):
            load_wishlist_data.clear()
            st.rerun()

    wishlist = load_wishlist_data()

    if not wishlist:
        st.info("No cheeses pinned yet — go to the **Recommendations** tab and hit **Save to Wishlist**.")
    else:
        st.caption(f"{len(wishlist)} cheese{'es' if len(wishlist) != 1 else ''} on your list")
        st.divider()

        for i in range(0, len(wishlist), 3):
            row_cols = st.columns(3)
            for j, col in enumerate(row_cols):
                idx = i + j
                if idx >= len(wishlist):
                    break
                item     = wishlist[idx]
                name     = item.get("Name", "")
                notes    = item.get("Tasting Notes", "")
                price    = item.get("Price", "")
                where    = item.get("Where to Find It", "")
                link     = item.get("Link", "")
                img_url  = _parse_image_url(item.get("Image", ""))

                with col:
                    price_line = f"<small>💰 {price}</small>" if price else ""
                    st.markdown(
                        f"""<div class="cheese-card">
                            <h3>{name}</h3>
                            {price_line}
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if img_url:
                        try:
                            st.image(img_url, width=260)
                        except Exception:
                            pass
                    if notes:
                        st.caption(notes)
                    if where:
                        st.markdown("📍 **Where to find it:**")
                        for line in where.splitlines():
                            if line.strip():
                                st.markdown(f"- {line.strip()}")
                    if link:
                        st.markdown(f"[🔗 More info]({link})")

                    btn_a, btn_b = st.columns(2)
                    with btn_a:
                        if st.button("☑️ Mark as Tried", key=f"wl_tried_{idx}", type="primary"):
                            st.session_state["prefill_from_rec"] = {"name": name}
                            st.session_state["_prefill_source"] = name
                            st.toast(f"Switch to Add Entry to log '{name}'!")
                            st.rerun()
                    with btn_b:
                        if st.button("🗑 Remove", key=f"wl_remove_{idx}"):
                            try:
                                from sheets import remove_from_wishlist
                                remove_from_wishlist(name)
                                load_wishlist_data.clear()
                                st.session_state.get("pinned_names", set()).discard(name)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not remove: {exc}")
                    st.markdown("---")


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Refresh Sheet Data"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("### API Status")
    for label, env_key in [
        ("Google Sheets",    "GOOGLE_SERVICE_ACCOUNT_JSON"),
        ("OpenRouter",       "OPENROUTER_API_KEY"),
        ("Tavily (enrich)",  "TAVILY_API_KEY"),
    ]:
        icon = "✅" if os.environ.get(env_key) else "❌"
        st.markdown(f"{icon} {label}")

    st.divider()
    st.markdown("**First run?** Copy `.env.example` → `.env` and fill in your keys.")
    with st.expander("Google Sheets setup"):
        st.markdown(
            """
1. [Google Cloud Console](https://console.cloud.google.com/) → enable **Sheets API** + **Drive API**
2. Create a **Service Account** → download JSON key
3. Set `GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/key.json` in `.env`
4. Share your spreadsheet with the service-account email (Editor role)
            """
        )
