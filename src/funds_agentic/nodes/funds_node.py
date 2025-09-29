from __future__ import annotations
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.sync_api import TimeoutError as PWTimeout
from ..state import State
from ..utils.logging_setup import setup_logger
from ..selectors import (
    TABLE_GENERIC, FUND_NAME, FE_RISK, UNIT_INFO_TABLE, SECTOR_LINK_TEXT
)
from ..utils.parsing import extract_perf_from_table_text, find_quartile_from_text, clean_price_token

logger = setup_logger()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=8))
def _open_page(ctx, url: str, timeout_ms: int):
    page = ctx.new_page()
    page.goto(url, timeout=timeout_ms * 1000)
    return page


def _scrape_one(ctx, url: str, timestamp: str, hold: bool, holding_pct, timeout_sec: int) -> Dict[str, Any] | None:
    page = _open_page(ctx, url, timeout_sec)

    # Find the performance table by scanning generic tables and picking one with header tokens
    tables = page.locator(TABLE_GENERIC)
    target_text = None
    for i in range(min(tables.count(), 6)):  # scan a few tables only
        text = tables.nth(i).inner_text()
        if "3 m" in text and "6 m" in text:
            target_text = text
            break

    if not target_text:
        raise RuntimeError("performance_table_not_found")

    perf = extract_perf_from_table_text(target_text)
    quartile = find_quartile_from_text(target_text)

    # Fund name (first occurrence is fund; second often sector)
    names = page.locator(FUND_NAME)
    fund_name = names.nth(0).inner_text(
    ).strip() if names.count() > 0 else None

    # Sector info
    sector = None
    sector_url = None
    try:
        # (View sector) link
        a = page.get_by_text(SECTOR_LINK_TEXT, exact=False)
        if a.count() > 0:
            sector_url = a.first.get_attribute("href")
        if names.count() > 1:
            sector = names.nth(1).inner_text().strip()
    except Exception:
        pass

    # FE Risk
    fe_risk = None
    try:
        risk_el = page.locator(FE_RISK)
        if risk_el.count() > 0:
            fe_risk = int(risk_el.first.inner_text().strip())
    except Exception:
        pass

    # Price best-effort from unit info table
    price = None
    try:
        unit_table = page.locator(UNIT_INFO_TABLE)
        if unit_table.count() > 0:
            # look for a number-like token in text
            tokens = unit_table.first.inner_text().replace("%", "").split()
            for t in tokens:
                if any(ch.isdigit() for ch in t):
                    price = clean_price_token(t)
                    break
    except Exception:
        pass

    row = {
        "date": timestamp,
        "fundName": fund_name,
        "Quartile": quartile,
        "FERisk": fe_risk,
        "3m": perf.get("3m"),
        "6m": perf.get("6m"),
        "1y": perf.get("1y"),
        "3y": perf.get("3y"),
        "5y": perf.get("5y"),
        "url": url,
        "Hold": hold,
        "Holding%": holding_pct,
        "Sector": sector,
        "SectorUrl": sector_url,
        "price": price,
    }
    return row


def funds_node(state: Dict[str, Any]) -> Dict[str, Any]:
    st = State.model_validate(state["state"])  # hydrate
    ctx = st.browser_ctx
    max_retries = st.config.retries_per_url

    out: List[dict] = []
    failed: List[str] = []

    for rec in st.fund_rows:
        url = rec["url"]
        success = False

        # Retry loop for each URL
        for attempt in range(1, max_retries + 1):
            try:
                row = _scrape_one(
                    ctx=ctx,
                    url=url,
                    timestamp=st.meta.timestamp,
                    hold=rec.get("hold", False),
                    holding_pct=rec.get("holding_pct"),
                    timeout_sec=st.config.nav_timeout_sec,
                )
                out.append(row)
                success = True
                logger.info("fund_scraped", extra={
                    "kv": {"step": "funds_node", "url": url, "status": "ok", "attempt": attempt}})
                break  # Success, exit retry loop

            except Exception as e:
                if attempt < max_retries:
                    # Not the last attempt, log and retry
                    logger.warning("fund_retry", extra={
                        "kv": {"step": "funds_node", "url": url, "attempt": attempt,
                               "max_retries": max_retries, "reason": str(e)[:100]}})
                else:
                    # Last attempt failed
                    logger.warning("fund_failed", extra={
                        "kv": {"step": "funds_node", "url": url, "status": "failed",
                               "attempts": max_retries, "reason": str(e)[:100]}})

        if not success:
            failed.append(url)

    st.fund_rows_raw = out
    st.failed_urls = failed
    st.stats.update({
        "scraped_ok": len(out),
        "failed": len(failed),
        "failure_rate": (len(failed) / max(1, len(out) + len(failed)))
    })
    return {"state": st.model_dump()}
