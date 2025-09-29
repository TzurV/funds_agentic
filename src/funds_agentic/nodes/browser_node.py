from __future__ import annotations
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.sync_api import sync_playwright, BrowserContext, TimeoutError as PWTimeout
from ..state import State
from ..utils.logging_setup import setup_logger
from ..selectors import COOKIE_ALLOW_ALL, INVESTOR_LABEL, AGREE_BUTTON

logger = setup_logger()


def _maybe_click(page, selector: str, name: str):
    try:
        el = page.locator(selector)
        if el.count() > 0:
            el.first.click(timeout=2000)
            logger.info("Clicked", extra={
                        "kv": {"step": "browser_node", "element": name}})
    except Exception:
        # if not present, ignore
        pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
def _launch_context(headless: bool) -> BrowserContext:
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    ctx = browser.new_context()
    # open a page to trustnet root to perform consent
    page = ctx.new_page()
    page.goto("https://www.trustnet.com/", timeout=30000)
    _maybe_click(page, COOKIE_ALLOW_ALL, "cookie_allow_all")
    _maybe_click(page, INVESTOR_LABEL, "investor_private")
    _maybe_click(page, AGREE_BUTTON, "agree_terms")
    return ctx


def browser_node(state: Dict[str, Any]) -> Dict[str, Any]:
    st = State.model_validate(state["state"])  # hydrate
    ctx = _launch_context(st.config.headless)
    st.browser_ctx = ctx
    st.consent_done = True
    logger.info("Browser ready", extra={"kv": {
        "step": "browser_node",
        "headless": st.config.headless,
        "consent_done": True,
    }})
    return {"state": st.model_dump()}
