from __future__ import annotations
from typing import Dict, Any, List
import os
import pandas as pd
from ..state import State
from ..utils.logging_setup import setup_logger

logger = setup_logger()

FUNDS_COLUMNS = [
    "date", "fundName", "Quartile", "FERisk",
    "3m", "6m", "1y", "3y", "5y",
    "url", "Hold", "Holding%",
    "Sector", "SectorUrl", "price",
]

SECTORS_COLUMNS = [
    "date", "sectorName", "1m", "3m", "6m", "1y", "3y", "5y"
]


def _to_df_funds(rows: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    # Ensure all columns exist and in order
    for c in FUNDS_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[FUNDS_COLUMNS]


def _to_df_sectors(rows: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in SECTORS_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[SECTORS_COLUMNS]


def _save_pair(df: pd.DataFrame, basepath: str) -> tuple[str, str]:
    csv_path = basepath + ".csv"
    parquet_path = basepath + ".parquet"
    df.to_csv(csv_path, index=True, float_format="%.2f")
    df.to_parquet(parquet_path, index=False)
    return csv_path, parquet_path


def normalize_write_node(state: Dict[str, Any]) -> Dict[str, Any]:
    st = State.model_validate(state["state"])  # hydrate

    date = st.meta.run_date
    outdir = st.config.output_dir

    funds_df = _to_df_funds(st.fund_rows_raw)
    sectors_df = _to_df_sectors(st.sector_rows_raw)

    funds_base = os.path.join(outdir, f"{date}_funds")
    sectors_base = os.path.join(outdir, f"{date}_sectors")

    try:
        funds_csv, funds_parquet = _save_pair(funds_df, funds_base)
        sectors_csv, sectors_parquet = _save_pair(sectors_df, sectors_base)
    except Exception as e:
        # fallback for funds CSV only (parquet likely also fails if perms issue)
        fallback_csv = os.path.join(outdir, f"Local_{date}_funds.csv")
        funds_df.to_csv(fallback_csv, index=False, float_format="%.2f")
        logger.error("write_failed", extra={
                     "kv": {"step": "normalize_write_node", "error": str(e)}})
        st.funds_csv_path = fallback_csv
        st.sectors_csv_path = sectors_csv if 'sectors_csv' in locals() else None
        st.funds_parquet_path = None
        st.sectors_parquet_path = sectors_parquet if 'sectors_parquet' in locals() else None
    else:
        st.funds_csv_path = funds_csv
        st.sectors_csv_path = sectors_csv
        st.funds_parquet_path = funds_parquet
        st.sectors_parquet_path = sectors_parquet
        logger.info("outputs_written", extra={"kv": {
            "step": "normalize_write_node",
            "funds_csv": funds_csv,
            "sectors_csv": sectors_csv,
        }})

    return {"state": st.model_dump()}
