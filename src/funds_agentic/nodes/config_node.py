from __future__ import annotations
import argparse
import os
import time
from datetime import datetime
from pydantic import ValidationError
from ..state import State, Config, RunMeta
from ..utils.logging_setup import setup_logger

logger = setup_logger()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("funds-agentic")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=str, help="Path to Excel file")
    src.add_argument("--gsheet-url", type=str, help="Google Sheets share URL")
    src.add_argument("--gdrive-id", type=str,
                     help="Google Drive file id for a Sheet")
    p.add_argument("--output", type=str, required=True,
                   help="Output directory")
    p.add_argument("--sheet", type=str, default="TrackingList")
    p.add_argument("--col-url", type=str)
    p.add_argument("--col-hold", type=str)
    p.add_argument("--col-holding", type=str)
    p.add_argument("--retries-per-url", type=int, default=2)
    p.add_argument("--nav-timeout", type=int, default=20)
    p.add_argument("--row-start", type=int, default=3,
                   help="1-based row where the header row lives (e.g., 3 when headers are on row 3)")
    headless = p.add_mutually_exclusive_group()
    headless.add_argument("--headless", dest="headless",
                          action="store_true", help="Run browser headless (default)")
    headless.add_argument("--no-headless", dest="headless",
                          action="store_false", help="Run browser with a visible window")
    p.set_defaults(headless=True)
    return p


def config_node(_: dict) -> dict:
    """Create initial State with config + run metadata. Fails fast if invalid."""
    args = build_arg_parser().parse_args()

    run_date = datetime.now().strftime("%Y%m%d")
    timestamp = datetime.now().strftime("%d/%m/%y %H:%M")
    run_id = f"run-{int(time.time())}"

    cfg = Config(
        input_path=args.input,
        gsheet_url=args.gsheet_url,
        gdrive_id=args.gdrive_id,
        output_dir=os.path.abspath(args.output),
        sheet=args.sheet,
        row_start=args.row_start,
        col_url=args.col_url,
        col_hold=args.col_hold,
        col_holding=args.col_holding,
        headless=args.headless,
        retries_per_url=args.retries_per_url,
        nav_timeout_sec=args.nav_timeout,
    )
    meta = RunMeta(run_id=run_id, run_date=run_date, timestamp=timestamp)
    st = State(meta=meta, config=cfg)

    os.makedirs(cfg.output_dir, exist_ok=True)
    logger.info("Config ready", extra={"kv": {
        "step": "config_node",
        "output_dir": cfg.output_dir,
        "input_path": cfg.input_path,
        "gsheet_url": bool(cfg.gsheet_url),
        "gdrive_id": bool(cfg.gdrive_id),
        "headless": cfg.headless,
        "retries_per_url": cfg.retries_per_url,
        "nav_timeout": cfg.nav_timeout_sec,
    }})
    return {"state": st.model_dump()}
