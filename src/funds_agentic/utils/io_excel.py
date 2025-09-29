"""Excel ingestion with flexible column mapping and row start handling."""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

from funds_agentic.utils.logging_setup import setup_logger

logger = setup_logger()


CANON = {
    "url": ["url", "fund_url", "link", "fundurl"],
    "hold": ["hold", "held", "in_portfolio", "own", "have"],
    "holding": ["holding%", "holding_pct", "holding", "weight", "allocation", "holding%"],
}


def _norm_header(h: str) -> str:
    return "".join(h.lower().strip().split())


def resolve_columns(df: pd.DataFrame, overrides: Dict[str, Optional[str]]) -> Dict[str, str]:
    headers = {_norm_header(c): c for c in df.columns}

    def find(name: str) -> Optional[str]:
        # First check explicit override
        if overrides.get(name):
            return overrides[name]
        # Then try canonical synonyms
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
        return float(s)
    except Exception:
        return None


def load_excel(path: str, sheet: str, row_start: int, overrides: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    # Read Excel with openpyxl, treating row_start as the header row
    # row_start is 1-based (Excel convention), so row 3 means skip first 2 rows
    df = pd.read_excel(path, sheet_name=sheet,
                       header=row_start - 1, engine="openpyxl")

    # If columns are unnamed (like "Unnamed: 5"), use positional indices
    # Legacy code used columns F, G, H (0-indexed: 5, 6, 7)
    # But first try to resolve by name
    cols = resolve_columns(df, overrides)

    # Fallback: if no columns resolved, try positional (F=5, G=6, H=7 in 0-indexed)
    if not cols["url"] and len(df.columns) > 5:
        # Assume legacy layout: F=url, G=hold, H=holding%
        cols["url"] = df.columns[5]  # Column F
        if len(df.columns) > 6:
            cols["hold"] = df.columns[6]  # Column G
        if len(df.columns) > 7:
            cols["holding"] = df.columns[7]  # Column H

    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        url = r.get(cols["url"]) if cols["url"] else None
        if pd.isna(url) or not str(url).strip():
            continue
        hold = to_bool(r.get(cols["hold"]) if cols["hold"] else None)
        holding = to_pct(r.get(cols["holding"]) if cols["holding"] else None)
        rows.append({"url": str(url).strip(),
                    "hold": hold, "holding_pct": holding})

    # De-duplicate exact URLs, keep first occurrence
    seen = set()
    dedup = []
    for index, row in enumerate(rows):
        # Limit the number of URL's for testing
        # if index > 3:
        #     logger.debug(f"BREAK after First {index} rows for debug")
        #     break
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        dedup.append(row)

    return dedup

