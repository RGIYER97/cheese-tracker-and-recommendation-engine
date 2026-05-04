import os
import gspread
import gspread.utils
import pandas as pd
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SPREADSHEET_ID = "18CJ8MrQQw7y6K1rL6Uqa95CEF-X_2fqwUX_RnrZlyiI"
CHEESE_SHEET = os.environ.get("CHEESE_SHEET_NAME", "cheese")
ENRICHMENT_COLS = ["Link", "Est. Price", "Image", "Prof. Tasting Notes", "Notes Source", "Nutrition"]


def _client() -> gspread.Client:
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not path:
        raise EnvironmentError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def _find_cheese_header(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "cheese type":
            return i
    raise ValueError("Could not find 'Cheese Type' header row in the sheet")


def _open_cheese_worksheet() -> gspread.Worksheet:
    sh = _client().open_by_key(SPREADSHEET_ID)

    # First try the configured worksheet/tab name for backward compatibility.
    try:
        return sh.worksheet(CHEESE_SHEET)
    except gspread.WorksheetNotFound:
        pass

    # Fall back to auto-detecting a sheet containing a "Cheese Type" header row.
    for ws in sh.worksheets():
        try:
            rows = ws.get_all_values()
            _find_cheese_header(rows)
            return ws
        except Exception:
            continue

    raise ValueError(
        "Could not find a worksheet with a 'Cheese Type' header. "
        "Set CHEESE_SHEET_NAME in .env to your exact tab name."
    )


def load_cheese_data() -> pd.DataFrame:
    ws = _open_cheese_worksheet()
    rows = ws.get_all_values()
    header_idx = _find_cheese_header(rows)
    headers = [h.strip() for h in rows[header_idx]]
    data = [r for r in rows[header_idx + 1 :] if any(c.strip() for c in r)]

    # Pad short rows to match header length
    padded = [r + [""] * (len(headers) - len(r)) for r in data]
    df = pd.DataFrame(padded, columns=headers)
    df = df[df["Cheese Type"].str.strip() != ""].copy()
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"].str.strip(), format="%B %Y", errors="coerce")
    return df.reset_index(drop=True)


def update_enrichment(df_enriched: pd.DataFrame) -> None:
    ws = _open_cheese_worksheet()
    rows = ws.get_all_values()
    header_idx = _find_cheese_header(rows)
    headers = [h.strip() for h in rows[header_idx]]

    batch: list[dict] = []

    # Add any missing enrichment header columns
    for col_name in ENRICHMENT_COLS:
        if col_name not in headers:
            col_num = len(headers) + 1
            headers.append(col_name)
            cell = gspread.utils.rowcol_to_a1(header_idx + 1, col_num)
            batch.append({"range": cell, "values": [[col_name]]})

    link_col       = headers.index("Link") + 1
    price_col      = headers.index("Est. Price") + 1
    img_col        = headers.index("Image") + 1
    notes_col      = headers.index("Prof. Tasting Notes") + 1
    source_col     = headers.index("Notes Source") + 1
    nutrition_col  = headers.index("Nutrition") + 1
    name_col       = headers.index("Cheese Type")

    for row_idx in range(header_idx + 1, len(rows)):
        row = rows[row_idx]
        if not row or not (len(row) > name_col and row[name_col].strip()):
            continue
        cheese_name = row[name_col].strip()
        match = df_enriched[df_enriched["Cheese Type"].str.strip() == cheese_name]
        if match.empty:
            continue
        m = match.iloc[0]
        sheet_row = row_idx + 1

        def _val(key: str) -> str:
            v = m.get(key, "")
            return str(v).strip() if pd.notna(v) else ""

        img_url     = _val("Image URL")
        img_formula = f'=IMAGE("{img_url}", 1)' if img_url else ""

        # Only queue cells that have new content — never blank-out an existing value
        for col_num, value in [
            (link_col,      _val("Link")),
            (price_col,     _val("Est. Price")),
            (img_col,       img_formula),
            (notes_col,     _val("Prof. Tasting Notes")),
            (source_col,    _val("Notes Source")),
            (nutrition_col, _val("Nutrition")),
        ]:
            if value:
                batch.append({"range": gspread.utils.rowcol_to_a1(sheet_row, col_num), "values": [[value]]})

    if batch:
        # USER_ENTERED so Sheets evaluates the =IMAGE() formulas
        for i in range(0, len(batch), 100):
            ws.batch_update(batch[i : i + 100], value_input_option="USER_ENTERED")


# ── Cheese Recommendation tab ──────────────────────────────────────────────────

REC_SHEET_NAME = "Cheese Recommendation"
REC_COLS = ["Name", "Tasting Notes", "Price", "Where to Find It", "Link", "Image"]

# Official store homepages — matched against store names in recommendations
_STORE_URLS: list[tuple[str, str]] = [
    ("murray",          "https://www.murrayscheese.com"),
    ("eataly",          "https://www.eataly.com"),
    ("whole foods",     "https://www.wholefoodsmarket.com"),
    ("di palo",         "https://dipalosfinefood.com"),
    ("valley shepherd", "https://valleyshepherd.com"),
    ("fairway",         "https://www.fairwaymarket.com"),
    ("trader joe",      "https://www.traderjoes.com"),
    ("aldi",            "https://www.aldi.us"),
    ("lidl",            "https://www.lidl.com"),
    ("walmart",         "https://www.walmart.com"),
    ("costco",          "https://www.costco.com"),
    ("zabar",           "https://www.zabars.com"),
    ("dean & deluca",   "https://www.deandeluca.com"),
    ("citarella",       "https://www.citarella.com"),
]


def _store_url(store_name: str) -> str:
    """Return the official homepage URL for a known store, or '' if unrecognised."""
    key = store_name.lower()
    for fragment, url in _STORE_URLS:
        if fragment in key:
            return url
    return ""


def _ensure_rec_sheet(sh: gspread.Spreadsheet) -> gspread.Worksheet:
    """Return the Cheese Recommendation worksheet, creating it with headers if absent.
    Also adds any columns present in REC_COLS that are missing from an existing sheet."""
    try:
        ws = sh.worksheet(REC_SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=REC_SHEET_NAME, rows=200, cols=len(REC_COLS))
        ws.append_row(REC_COLS, value_input_option="USER_ENTERED")
        return ws

    # Sheet exists — ensure every expected column is present
    existing_headers = ws.row_values(1)
    batch = []
    for col_name in REC_COLS:
        if col_name not in existing_headers:
            col_num = len(existing_headers) + 1
            existing_headers.append(col_name)
            batch.append({
                "range": gspread.utils.rowcol_to_a1(1, col_num),
                "values": [[col_name]],
            })
    if batch:
        ws.batch_update(batch, value_input_option="USER_ENTERED")
    return ws


def append_cheese(
    name: str,
    date: str,
    from_where: str,
    score: float,
    tasting_notes: str,
    extra_fields: dict[str, str] | None = None,
) -> None:
    """Append a new cheese tasting row to the cheese worksheet."""
    ws = _open_cheese_worksheet()
    rows = ws.get_all_values()
    header_idx = _find_cheese_header(rows)
    headers = [h.strip() for h in rows[header_idx]]

    # Auto-create any columns from extra_fields that don't exist yet
    if extra_fields:
        new_col_batch: list[dict] = []
        for col_name in extra_fields:
            if col_name not in headers:
                col_num = len(headers) + 1
                headers.append(col_name)
                cell = gspread.utils.rowcol_to_a1(header_idx + 1, col_num)
                new_col_batch.append({"range": cell, "values": [[col_name]]})
        if new_col_batch:
            ws.batch_update(new_col_batch, value_input_option="USER_ENTERED")

    col_map = {h: i for i, h in enumerate(headers)}
    row_data = [""] * len(headers)
    for col_name, val in [
        ("Cheese Type",   name),
        ("Date",          date),
        ("From Where",    from_where),
        ("Score",         str(score)),
        ("Tasting Notes", tasting_notes),
    ]:
        if col_name in col_map:
            row_data[col_map[col_name]] = val

    if extra_fields:
        for col_name, val in extra_fields.items():
            if col_name in col_map:
                row_data[col_map[col_name]] = val

    ws.append_row(row_data, value_input_option="USER_ENTERED")


def load_pinned_cheeses() -> list[str]:
    """Return all cheese names already saved in the Recommendation sheet."""
    try:
        sh = _client().open_by_key(SPREADSHEET_ID)
        ws = _ensure_rec_sheet(sh)
        rows = ws.get_all_values()
        return [r[0].strip() for r in rows[1:] if r and r[0].strip()]
    except Exception:
        return []


def pin_recommendation(rec: dict) -> None:
    """Append a recommendation to the Cheese Recommendation sheet (idempotent)."""
    sh = _client().open_by_key(SPREADSHEET_ID)
    ws = _ensure_rec_sheet(sh)

    existing_names = {r[0].strip().lower() for r in ws.get_all_values()[1:] if r}
    if rec.get("name", "").strip().lower() in existing_names:
        return

    tasting_notes = ", ".join(rec.get("tasting_notes", [])) or rec.get("flavor_profile", "")
    img_url = rec.get("picture_url", "")
    img_formula = f'=IMAGE("{img_url}", 1)' if img_url else ""

    # Build "Where to Find It" — "Store Name — Location" per store, joined by newlines
    stores = rec.get("stores", [])
    where_parts = []
    for store in stores:
        name = store.get("name", "").strip()
        loc  = store.get("location", "").strip()
        if name and loc:
            where_parts.append(f"{name} — {loc}")
        elif name:
            where_parts.append(name)
    where_to_find = "\n".join(where_parts)

    # Prefer the official homepage of the first listed store over the generic Tavily link
    link = ""
    for store in stores:
        link = _store_url(store.get("name", ""))
        if link:
            break
    if not link:
        link = rec.get("link", "")

    ws.append_row(
        [
            rec.get("name", ""),
            tasting_notes,
            rec.get("price_range", ""),
            where_to_find,
            link,
            img_formula,
        ],
        value_input_option="USER_ENTERED",
    )
