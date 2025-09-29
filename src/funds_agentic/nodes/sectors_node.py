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
    
    # Check if T&C modal appeared on this new page and dismiss it
    try:
        modal = page.locator("#termsAndConditions")
        if modal.count() > 0 and "show" in modal.get_attribute("class"):
            # Modal is visible, dismiss it
            page.locator("label[for='tc-check-Investor']").click()
            page.wait_for_timeout(500)
            page.locator("#tc-modal-agree").click()
            page.wait_for_timeout(1000)
            logger.info("Dismissed T&C modal on new page", extra={"kv": {"step": "sectors_node"}})
    except Exception:
        pass  # No modal or already dismissed
    
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

    # Try pagination: iterate through pages 2, 3, etc.
    current_page = 1
    max_pages = 10  # safety limit
    
    while current_page < max_pages:
        next_page = current_page + 1
        
        try:
            # Scroll to bottom first (legacy pattern)
            page.keyboard.press("End")
            page.wait_for_timeout(1000)
            
            # Find all pagination buttons
            all_buttons = page.locator(PAGINATION_BUTTONS).all()
            target_button = None
            
            # Find button with matching page number text
            for btn in all_buttons:
                text = btn.inner_text().strip()
                if text == str(next_page):
                    target_button = btn
                    break
            
            if target_button is None:
                # No more pages
                logger.info("No more pages", extra={
                    "kv": {"step": "sectors_node", "page": next_page}})
                break
            
            # Scroll the button to center of viewport (legacy pattern)
            box = target_button.bounding_box()
            if box:
                # Calculate scroll position to center the button
                viewport_height = page.viewport_size["height"]
                scroll_to_y = box["y"] + (box["height"] / 2) - (viewport_height / 2)
                page.evaluate(f"window.scrollBy(0, {scroll_to_y})")
                page.wait_for_timeout(500)
            
            # Click the button with force to bypass any overlay issues
            target_button.click(force=True)
            page.wait_for_timeout(2000)  # Wait for table to reload
            
            # Extract rows from new page
            new_rows = _extract_table_rows(page)
            if len(new_rows) == 0:
                logger.warning("No rows extracted", extra={
                    "kv": {"step": "sectors_node", "page": next_page}})
                break
            
            print(f"Page {next_page}: extracted {len(new_rows)} rows")
            all_rows.extend(new_rows)
            current_page = next_page
            logger.info("Pagination success", extra={
                "kv": {"step": "sectors_node", "page": next_page, "rows": len(new_rows)}})
            
        except Exception as e:
            logger.warning("Pagination click failed", extra={
                "kv": {"step": "sectors_node", "page": next_page, "reason": str(e)[:200]}})
            break

    # Attach timestamp to each row
    print(f"Total sectors extracted: {len(all_rows)}")
    for r in all_rows:
        r["date"] = st.meta.timestamp

    st.sector_rows_raw = all_rows
    logger.info("Sectors scraped", extra={
                "kv": {"step": "sectors_node", "rows": len(all_rows)}})
    return {"state": st.model_dump()}
