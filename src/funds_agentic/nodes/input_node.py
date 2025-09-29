from __future__ import annotations
from typing import Dict, Any, List
from ..state import State
from ..utils.logging_setup import setup_logger
from ..utils.io_excel import load_excel
from ..utils.io_gsheet import load_gsheet

logger = setup_logger()


def input_node(state: Dict[str, Any]) -> Dict[str, Any]:
    st = State.model_validate(state["state"])  # hydrate
    cfg = st.config

    overrides = {"url": cfg.col_url,
                 "hold": cfg.col_hold, "holding": cfg.col_holding}
    if cfg.input_path:
        rows = load_excel(cfg.input_path, cfg.sheet, cfg.row_start, overrides)
    else:
        rows = load_gsheet(cfg.gsheet_url, cfg.gdrive_id,
                           cfg.sheet, cfg.row_start, overrides)

    logger.info("Input loaded", extra={"kv": {
        "step": "input_node",
        "rows": len(rows),
    }})

    st.fund_rows = rows
    st.stats.update({"total_urls": len(rows)})
    return {"state": st.model_dump()}
