"""Google Sheets ingestion using gspread (service account).
Provide either GOOGLE_APPLICATION_CREDENTIALS path env var or a JSON blob via GOOGLE_SERVICE_ACCOUNT_JSON.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from .io_excel import resolve_columns, to_bool, to_pct

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_credentials() -> Credentials:
    blob = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if blob:
        info = json.loads(blob)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    if path and os.path.exists(path):
        return Credentials.from_service_account_file(path, scopes=SCOPES)
    raise RuntimeError(
        "Google credentials not provided. Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_SERVICE_ACCOUNT_JSON.")


def load_gsheet(gsheet_url: Optional[str], gdrive_id: Optional[str], sheet: str, row_start: int, overrides: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    creds = _get_credentials()
    gc = gspread.authorize(creds)

    if gsheet_url:
        sh = gc.open_by_url(gsheet_url)
    elif gdrive_id:
        sh = gc.open_by_key(gdrive_id)
    else:
        raise ValueError("Either gsheet_url or gdrive_id must be provided")

    ws = sh.worksheet(sheet)
    data = ws.get_all_values()  # list of rows
    if not data:
        return []
    # First row assumed headers; create DataFrame
    headers, rows = data[0], data[1:]
    df = pd.DataFrame(rows, columns=headers)
    if row_start > 1:
        # because our df starts after header
        df = df.iloc[row_start-2:].reset_index(drop=True)
    cols = resolve_columns(df, overrides)

    out: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        url = r.get(cols["url"]) if cols["url"] else None
        if url is None or str(url).strip() == "":
            continue
        hold = to_bool(r.get(cols["hold"]) if cols["hold"] else None)
        holding = to_pct(r.get(cols["holding"]) if cols["holding"] else None)
        out.append({"url": str(url).strip(),
                   "hold": hold, "holding_pct": holding})
    # de-duplicate
    seen = set()
    dedup = []
    for row in out:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        dedup.append(row)
    return dedup
