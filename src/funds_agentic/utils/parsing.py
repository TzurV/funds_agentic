"""Helpers to parse Trustnet page text into structured values."""
from __future__ import annotations
from typing import Dict, Any, Tuple
import re


def extract_perf_from_table_text(text: str) -> Dict[str, float | None]:
    """Given a block of table text that includes a header line like '3 m 6 m 1 y 3 y 5 y',
    return a dict with keys '3m','6m','1y','3y','5y'. We use a simple token approach
    to keep this resilient to minor whitespace changes.
    """
    # Normalize whitespace
    lines = [re.sub(r"\s+", " ", ln).strip()
             for ln in text.splitlines() if ln.strip()]
    # find header line index that contains tokens '3 m 6 m'
    header_idx = -1
    for i, ln in enumerate(lines):
        if re.search(r"\b3\s*m\b\s*\b6\s*m\b", ln):
            header_idx = i
            break
    out = {"3m": None, "6m": None, "1y": None, "3y": None, "5y": None}
    if header_idx == -1:
        return out
    # Next non-empty line should carry the numbers in order
    if header_idx + 1 < len(lines):
        tokens = lines[header_idx + 1].replace("%", "").split()
        # we expect at least 5 numeric-like tokens
        vals = []
        for t in tokens:
            try:
                vals.append(float(t))
            except Exception:
                # ignore non-numeric tokens (like arrows or labels)
                pass
        # map first five
        keys = ["3m", "6m", "1y", "3y", "5y"]
        for k, v in zip(keys, vals[:5]):
            out[k] = v
    return out


def find_quartile_from_text(text: str) -> int | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if "Quartile Ranking" in ln:
            # next line expected to be an integer
            if i + 1 < len(lines):
                m = re.search(r"(\d+)", lines[i+1])
                if m:
                    try:
                        return int(m.group(1))
                    except Exception:
                        return None
    return None


def clean_price_token(s: str | None) -> str | None:
    if not s:
        return None
    return s.replace("Â", "").replace("p", "").strip()
