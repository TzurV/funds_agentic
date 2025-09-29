"""
State models and constants shared across nodes.
We keep state simple (Pydantic models + plain dict) so LangGraph can pass updates.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Config(BaseModel):
    input_path: Optional[str] = None
    gsheet_url: Optional[str] = None
    gdrive_id: Optional[str] = None
    output_dir: str
    sheet: str = "TrackingList"
    row_start: int = 3
    col_url: Optional[str] = None
    col_hold: Optional[str] = None
    col_holding: Optional[str] = None
    headless: bool = True
    retries_per_url: int = 2
    nav_timeout_sec: int = 20


class RunMeta(BaseModel):
    run_id: str
    run_date: str  # YYYY-MM-DD
    timestamp: str  # DD/MM/YY HH:MM
    timezone: str = "Europe/London"


class State(BaseModel):
    # immutable meta & config
    meta: RunMeta
    config: Config

    # browser
    browser_ctx: Any | None = None  # Playwright BrowserContext
    consent_done: bool = False

    # data in-memory
    fund_rows: List[Dict[str, Any]] = Field(
        default_factory=list)  # ingested from Excel/Sheets
    sector_rows_raw: List[Dict[str, Any]] = Field(default_factory=list)
    fund_rows_raw: List[Dict[str, Any]] = Field(default_factory=list)
    failed_urls: List[str] = Field(default_factory=list)

    # outputs
    funds_csv_path: Optional[str] = None
    sectors_csv_path: Optional[str] = None
    funds_parquet_path: Optional[str] = None
    sectors_parquet_path: Optional[str] = None

    # stats / errors (for logging)
    stats: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

