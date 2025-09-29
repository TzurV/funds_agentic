from __future__ import annotations
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.sync_api import TimeoutError as PWTimeout
from ..state import State
from ..utils.logging_setup import setup_logger
from ..selectors import SECTORS_URL, SECTORS_TABLE_CONTAINER, SECTORS_HEADER_TOKEN, PAGINATION_BUTTONS

logger = setup_logger()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=8))
def _load_page(ctx, url: str, timeout_ms: int):
    page = ctx.new_page()
    page.goto(url, timeout=timeout_ms * 1000)
    return page


def _extract_table_rows(page) -> List[dict]:
    # Find the table container that includes the header token "Name"
    containers = page.locator(SECTORS_TABLE_CONTAINER)
    target = None
    for i in range(containers.count()):
        el = containers.nth(i)
        if SECTORS_HEADER_TOKEN in el.inner_text():
            target = el
            break
    if target is None:
        return []
    # Extract rows from <tr>
    rows: List[dict] = []
    trs = target.locator("tbody tr")
    for i in range(trs.count()):
        tds = trs.nth(i).locator("td")
        if tds.count() < 7:
            continue
        sector = tds.nth(0).inner_text().strip()
        vals = [tds.nth(j).inner_text().strip().replace("%", "")
                for j in range(1, 7)]
        rows.append({
            "sectorName": sector,
            "1m": _float_or_none(vals[0]),
            "3m": _float_or_none(vals[1]),
            "6m": _float_or_none(vals[2]),
            "1y": _float_or_none(vals[3]),
            "3y": _float_or_none(vals[4]),
            "5y": _float_or_none(vals[5]),
        })
    return rows


def _float_or_none(s: str):
    try:
        return float(s)
    except Exception:
        return None


def sectors_node(state: Dict[str, Any]) -> Dict[str, Any]:
    st = State.model_validate(state["state"])  # hydrate
    ctx = st.browser_ctx
    page = _load_page(ctx, SECTORS_URL, st.config.nav_timeout_sec)

    all_rows: List[dict] = []
    # Page 1
    all_rows.extend(_extract_table_rows(page))

    # Try pagination buttons with class .set-page
    try:
        buttons = page.locator(PAGINATION_BUTTONS)
        pages = buttons.count()
        for i in range(pages):
            btn = buttons.nth(i)
            label = btn.inner_text().strip()
            # Skip current/disabled
            if "disabled" in btn.get_attribute("class") or label == "1":
                continue
            try:
                btn.click()
                page.wait_for_timeout(500)  # brief wait
                all_rows.extend(_extract_table_rows(page))
            except Exception:
                logger.warning("Pagination click failed", extra={
                               "kv": {"step": "sectors_node", "page": label}})
    except Exception:
        pass

    # Attach timestamp to each row
    for r in all_rows:
        r["date"] = st.meta.timestamp

    st.sector_rows_raw = all_rows
    logger.info("Sectors scraped", extra={
                "kv": {"step": "sectors_node", "rows": len(all_rows)}})
    return {"state": st.model_dump()}
