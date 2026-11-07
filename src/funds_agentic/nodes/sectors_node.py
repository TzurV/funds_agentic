from __future__ import annotations
from typing import Dict, Any, List
import re
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.sync_api import expect
from ..state import State
from ..utils.logging_setup import setup_logger
from ..selectors import SECTORS_URL, SECTORS_TABLE_CONTAINER, SECTORS_HEADER_TOKEN, PAGINATION_BUTTONS

logger = setup_logger()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=8))
def _load_page(ctx, url: str, timeout_ms: int):
    page = ctx.new_page()
    try:
        page.goto(url, timeout=timeout_ms * 1000)
    except Exception:
        page.close()
        raise
    
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


def _validate_sector_rows(rows: List[dict]) -> None:
    if not rows:
        raise ValueError("Sector extraction returned no rows")
    names = [row.get("sectorName", "").strip() for row in rows]
    if any(not name for name in names):
        raise ValueError("Sector extraction returned an empty name")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate sectors: pagination did not return distinct rows")


def sectors_node(state: Dict[str, Any]) -> Dict[str, Any]:
    st = State.model_validate(state["state"])  # hydrate
    ctx = st.browser_ctx
    page = _load_page(ctx, SECTORS_URL, st.config.nav_timeout_sec)

    try:
        all_rows: List[dict] = []
        # Page 1
        expect(page.locator(SECTORS_TABLE_CONTAINER).locator(
            "tbody tr td:first-child").first).to_have_text(
                re.compile(r"IA .+"), timeout=st.config.nav_timeout_sec * 1000)
        new_rows = _extract_table_rows(page)
        _validate_sector_rows(new_rows)
        all_rows.extend(new_rows)

        # Pagination belongs to the cumulative table. Other tables have identical
        # page labels, including hidden controls that force=True can silently click.
        table = page.locator(SECTORS_TABLE_CONTAINER)
        current_page = 1
        max_pages = 100
        while True:
            _validate_sector_rows(all_rows)
            buttons = table.locator(PAGINATION_BUTTONS)
            page_numbers = [int(text) for text in buttons.all_text_contents()
                            if text.strip().isdigit()]
            if not page_numbers:
                raise RuntimeError("Sector pagination controls are missing")
            last_page = max(page_numbers)
            if current_page >= last_page:
                break
            if current_page >= max_pages:
                raise RuntimeError("Sector pagination exceeded safety limit")
            next_page = current_page + 1
            target_button = buttons.filter(has_text=re.compile(
                rf"^\s*{next_page}\s*$"))
            if target_button.count() != 1:
                raise RuntimeError(f"Missing or ambiguous sector page {next_page}")
            previous_name = new_rows[0]["sectorName"]
            target_button.click(timeout=st.config.nav_timeout_sec * 1000)
            # Wait for actual data, not a timer or the active pagination CSS class.
            first_name = table.locator("tbody tr td:first-child").first
            expect(first_name).not_to_have_text(previous_name,
                                               timeout=st.config.nav_timeout_sec * 1000)
            new_rows = _extract_table_rows(page)
            _validate_sector_rows(new_rows)
            _validate_sector_rows(all_rows + new_rows)
            all_rows.extend(new_rows)
            current_page = next_page
            logger.info("Pagination success", extra={"kv": {
                "step": "sectors_node", "page": current_page, "rows": len(new_rows)}})

        # Attach timestamp to each row
        print(f"Total sectors extracted: {len(all_rows)}")
        for r in all_rows:
            r["date"] = st.meta.timestamp

        st.sector_rows_raw = all_rows
        logger.info("Sectors scraped", extra={
                    "kv": {"step": "sectors_node", "rows": len(all_rows)}})
        return {"state": st.model_dump()}
    finally:
        page.close()
