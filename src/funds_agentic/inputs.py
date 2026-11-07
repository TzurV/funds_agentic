"""Read Excel or Sheets into the same validated fund inputs."""
from __future__ import annotations
import json
import math
import os
from urllib.parse import urlsplit, urlunsplit
import pandas as pd
from .models import Config, InputFund
from .utils.logging_setup import setup_logger

logger = setup_logger()
ALIASES = {"url": ("url", "fund_url", "link", "fundurl"),
           "hold": ("hold", "held", "in_portfolio", "own", "have"),
           "holding": ("holding%", "holding_pct", "holding", "weight", "allocation")}

def normalized(text: object) -> str:
    return "".join(str(text).lower().split())

def fund_url(value: str) -> str:
    url = urlsplit(value.strip())
    if (url.scheme not in {"http", "https"} or url.hostname not in {"trustnet.com", "www.trustnet.com"}
            or url.username or url.password or url.port not in {None, 80, 443}
            or "/factsheets/" not in url.path.lower()):
        raise ValueError("Expected a Trustnet factsheet URL")
    return urlunsplit(("https", "www.trustnet.com", url.path.rstrip("/"), url.query, ""))

def to_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    if text in {"hold", "yes", "y", "true", "1", "1.0", "t"}:
        return True
    if text in {"", "no", "n", "false", "0", "0.0", "f"}:
        return False
    raise ValueError(f"Unrecognized Hold flag: {value!r}")

def to_pct(value: object) -> float | None:
    if pd.isna(value) or not str(value).strip():
        return None
    number = float(str(value).strip().removesuffix("%"))
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError(f"Invalid holding percentage: {value!r}")
    return number

def rows_from_frame(df: pd.DataFrame, cfg: Config, *, excel: bool) -> list[InputFund]:
    headers: dict[str, object] = {}
    for header in df.columns:
        key = normalized(header)
        if key in headers and key and not key.startswith("unnamed:"):
            raise ValueError(f"Duplicate input column: {header}")
        headers[key] = header
    overrides = {"url": cfg.col_url, "hold": cfg.col_hold, "holding": cfg.col_holding}
    columns = {}
    for kind, aliases in ALIASES.items():
        if overrides[kind]:
            key = normalized(overrides[kind])
            if key not in headers:
                raise ValueError(f"Column override not found: {overrides[kind]}")
            columns[kind] = headers[key]
        else:
            columns[kind] = next((headers[normalized(a)] for a in aliases if normalized(a) in headers), None)
    if columns["url"] is None and excel and cfg.legacy_columns and len(df.columns) >= 6:
        logger.warning("Using legacy Excel F/G/H columns; configure named columns to disable this fallback")
        for index, kind in enumerate(("url", "hold", "holding"), 5):
            if columns[kind] is None and index < len(df.columns):
                columns[kind] = df.columns[index]
    if columns["url"] is None:
        raise ValueError("Input URL column not found")
    found: dict[str, InputFund] = {}
    for offset, (_, row) in enumerate(df.iterrows(), cfg.row_start + 1):
        value = row[columns["url"]]
        if pd.isna(value) or not str(value).strip():
            continue
        try:
            record = InputFund(url=fund_url(str(value)),
                hold=to_bool(row[columns["hold"]]) if columns["hold"] is not None else False,
                holding_pct=to_pct(row[columns["holding"]]) if columns["holding"] is not None else None)
            if record.url in found and found[record.url] != record:
                raise ValueError("Conflicting duplicate fund URL")
            found[record.url] = record
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Input row {offset}: {exc}") from exc
    if not found:
        raise ValueError("Input contains no usable fund URLs")
    return list(found.values())

def sheets_frame(data: list[list[str]], header_row: int) -> pd.DataFrame:
    if len(data) < header_row:
        raise ValueError("Google Sheet header row does not exist")
    headers = data[header_row - 1]
    width = len(headers)
    rows = data[header_row:]
    if any(len(row) > width and any(row[width:]) for row in rows):
        raise ValueError("Google Sheet data extends beyond the header columns")
    return pd.DataFrame([row[:width] + [""] * max(0, width-len(row)) for row in rows], columns=headers)

def load_inputs(cfg: Config) -> list[InputFund]:
    if cfg.input_path:
        frame = pd.read_excel(cfg.input_path, sheet_name=cfg.sheet, header=cfg.row_start-1, engine="openpyxl")
        return rows_from_frame(frame, cfg, excel=True)
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.readonly"]
    blob, path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if blob:
        credentials = Credentials.from_service_account_info(json.loads(blob), scopes=scopes)
    elif path:
        credentials = Credentials.from_service_account_file(path, scopes=scopes)
    else:
        raise ValueError("Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_SERVICE_ACCOUNT_JSON for Sheets")
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(cfg.gsheet_url) if cfg.gsheet_url else client.open_by_key(cfg.gdrive_id)
    frame = sheets_frame(sheet.worksheet(cfg.sheet).get_all_values(), cfg.row_start)
    return rows_from_frame(frame, cfg, excel=False)
