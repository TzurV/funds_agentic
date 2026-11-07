"""Typed configuration and data; browser resources never enter these models."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Literal, Self
from uuid import uuid4
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import math

FUND_PERIODS = ("3m", "6m", "1y", "3y", "5y")
SECTOR_PERIODS = ("1m", *FUND_PERIODS)

class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_path: Path | None = None
    gsheet_url: str | None = None
    gdrive_id: str | None = None
    output_dir: Path
    sheet: str = "TrackingList"
    row_start: int = Field(default=3, ge=1)
    col_url: str | None = None
    col_hold: str | None = None
    col_holding: str | None = None
    legacy_columns: bool = True
    headless: bool = True
    retries_per_url: int = Field(default=3, ge=1, le=10)
    nav_timeout_sec: int = Field(default=30, ge=1, le=180)
    limit: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def input_source(self) -> Self:
        if sum(bool(x) for x in (self.input_path, self.gsheet_url, self.gdrive_id)) != 1:
            raise ValueError("Choose exactly one Excel or Google Sheets input")
        return self

class InputFund(BaseModel):
    url: str
    hold: bool = False
    holding_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

def validate_performance(values: dict[str, float | None], required: tuple[str, ...]) -> dict[str, float | None]:
    if set(values) != set(required):
        raise ValueError("Performance periods do not match the required export schema")
    if any(value is not None and not math.isfinite(value) for value in values.values()):
        raise ValueError("Performance contains a non-finite number")
    return values

class SectorRecord(BaseModel):
    name: str = Field(min_length=1)
    performance: dict[str, float | None]
    source_url: str | None = None
    source_date: str | None = None

    @field_validator("performance")
    @classmethod
    def performance_schema(cls, values: dict[str, float | None]) -> dict[str, float | None]:
        return validate_performance(values, SECTOR_PERIODS)

class FundRecord(BaseModel):
    name: str = Field(min_length=1)
    url: str
    performance: dict[str, float | None]
    hold: bool = False
    holding_pct: float | None = None
    sector: str | None = None
    sector_url: str | None = None
    quartile: int | None = Field(default=None, ge=1, le=4)
    fe_risk: int | None = Field(default=None, ge=0)
    price: str | None = None
    price_unit: str | None = None
    price_date: str | None = None
    source_date: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("performance")
    @classmethod
    def performance_schema(cls, values: dict[str, float | None]) -> dict[str, float | None]:
        return validate_performance(values, FUND_PERIODS)

class RunMeta(BaseModel):
    run_id: str
    run_date: str
    timestamp: str
    retrieved_at: str

    @classmethod
    def now(cls) -> Self:
        now = datetime.now(ZoneInfo("Europe/London"))
        return cls(run_id=now.strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:10],
                   run_date=now.strftime("%Y%m%d"), timestamp=now.strftime("%d/%m/%y %H:%M"),
                   retrieved_at=now.isoformat())

class RunResult(BaseModel):
    meta: RunMeta
    status: Literal["success", "partial", "failed"] = "failed"
    requested: int = 0
    funds: list[FundRecord] = Field(default_factory=list)
    sectors: list[SectorRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duration_sec: float = 0
    snapshot_dir: str | None = None
    funds_csv: str | None = None
    sectors_csv: str | None = None
