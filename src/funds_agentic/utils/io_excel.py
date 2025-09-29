"""Excel ingestion with flexible column mapping and row start handling."""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

CANON = {
    "url": ["url", "fund_url", "link"],
    "hold": ["hold", "held", "in_portfolio", "own", "have"],
    "holding": ["holding%", "holding_pct", "holding", "weight", "allocation"],
}


def _norm_header(h: str) -> str:
    return "".join(h.lower().strip().split())


def resolve_columns(df: pd.DataFrame, overrides: Dict[str, Optional[str]]) -> Dict[str, str]:
    headers = {_norm_header(c): c for c in df.columns}

    def find(name: str) -> Optional[str]:
        if overrides.get(name):
            return overrides[name]
        for syn in CANON[name]:
            key = _norm_header(syn)
            if key in headers:
                return headers[key]
        return None

    col_url = find("url")
    col_hold = find("hold")
    col_holding = find("holding")
    return {"url": col_url, "hold": col_hold, "holding": col_holding}


TRUTHY = {"hold", "yes", "y", "true", "1", "t"}
FALSY = {"no", "n", "false", "0", "f", ""}


def to_bool(v) -> bool:
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    if s in TRUTHY:
        return True
    if s in FALSY:
        return False
    # default: any non-empty treated as True only if equals literal "hold"
    return s == "hold"


def to_pct(v) -> float | None:
    if pd.isna(v):
        return None
    s = str(v).strip().replace("%", "")
    if s == "":
        return None
    try:
        # If value seems like 0.125 but intended 12.5, keep as-is (we assume input semantics)
        return float(s)
    except Exception:
        return None


def load_excel(path: str, sheet: str, row_start: int, overrides: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    # "header=None" would treat first row as data; we want to preserve headers, so read normally
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    # Drop rows before row_start (1-based indexing)
    if row_start > 1:
        df = df.iloc[row_start-1:].reset_index(drop=True)
    cols = resolve_columns(df, overrides)

    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        url = r.get(cols["url"]) if cols["url"] else None
        if pd.isna(url) or not str(url).strip():
            continue
        hold = to_bool(r.get(cols["hold"]) if cols["hold"] else None)
        holding = to_pct(r.get(cols["holding"]) if cols["holding"] else None)
        rows.append({"url": str(url).strip(),
                    "hold": hold, "holding_pct": holding})
    # de-duplicate exact URLs, keep first occurrence
    seen = set()
    dedup = []
    for row in rows:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        dedup.append(row)
    return dedup
