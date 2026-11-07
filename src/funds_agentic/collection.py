"""Trustnet browser adapters with explicit resource ownership and bounded retries."""
from __future__ import annotations
from contextlib import contextmanager
from collections.abc import Iterator
import re
from urllib.parse import urljoin
from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout, expect, sync_playwright
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from .models import Config, FundRecord, InputFund, SectorRecord, FUND_PERIODS, SECTOR_PERIODS
from .parsing import MISSING, ExtractionError, clean, header_map, labeled_row, number, performance, ranking
from .selectors import SECTORS_URL, SECTORS_TABLE_CONTAINER, COOKIE_ALLOW_ALL, INVESTOR_LABEL, AGREE_BUTTON
from .utils.logging_setup import setup_logger

logger = setup_logger()
class TransientSourceError(RuntimeError):
    pass

def attempts(cfg: Config) -> Retrying:
    return Retrying(stop=stop_after_attempt(cfg.retries_per_url),
        wait=wait_exponential(multiplier=0.5, max=4), reraise=True,
        retry=retry_if_exception_type((PWTimeout, TransientSourceError)))

def dismiss_consent(page: Page, *, wait: bool = False) -> None:
    cookie = page.locator(COOKIE_ALLOW_ALL)
    if wait:
        try:
            cookie.wait_for(state="visible", timeout=2000)
        except PWTimeout:
            pass
    if cookie.is_visible():
        cookie.click(timeout=10000)
    modal = page.locator("#termsAndConditions")
    if wait:
        try:
            modal.wait_for(state="visible", timeout=2000)
        except PWTimeout:
            pass
    if modal.is_visible():
        page.locator(INVESTOR_LABEL).click(timeout=10000)
        page.locator(AGREE_BUTTON).click(timeout=10000)
        modal.wait_for(state="hidden", timeout=10000)

@contextmanager
def opened_page(ctx: BrowserContext, url: str, cfg: Config) -> Iterator[Page]:
    page = ctx.new_page()
    page.set_default_timeout(cfg.nav_timeout_sec * 1000)
    try:
        response = page.goto(url, wait_until="load", timeout=cfg.nav_timeout_sec * 1000)
        if response and response.status >= 500:
            raise TransientSourceError(f"Source returned HTTP {response.status}")
        if response and response.status >= 400:
            raise ExtractionError(f"Source returned HTTP {response.status}")
        dismiss_consent(page)
        yield page
    finally:
        page.close()

@contextmanager
def browser_session(cfg: Config) -> Iterator[BrowserContext]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=cfg.headless)
        try:
            context = browser.new_context()
            try:
                for attempt in attempts(cfg):
                    with attempt, opened_page(context, "https://www.trustnet.com/", cfg) as page:
                        dismiss_consent(page, wait=True)
                yield context
            finally:
                context.close()
        finally:
            browser.close()

TABLE_ROWS = """el => Array.from(el.rows).map(r => Array.from(r.cells).flatMap(c => Array(c.colSpan || 1).fill(c.textContent.trim())))"""

def unit_tables_for_page(units, name: str, url: str) -> list[list[list[str]]]:
    identity = re.search(r"/factsheets/([^/]+)/([^/]+)", url, re.I)
    key = ":".join(identity.groups()).upper() if identity else None
    # Other share classes have explicit factsheet links. The current class is
    # rendered without a link; its identity is checked against the Citicode grid.
    tables = units.locator("table").evaluate_all(r"""(els, key) => els.map(t =>
        Array.from(t.rows).filter(r => {
            const href = r.cells[0]?.querySelector('a[href]')?.getAttribute('href');
            const match = href?.match(/\/factsheets\/([^/]+)\/([^/]+)/i);
            return !key || !match || (match[1] + ':' + match[2]).toUpperCase() === key;
        }).map(r => Array.from(r.cells).flatMap(c => Array(c.colSpan || 1).fill(c.textContent.trim()))))""", key)
    if identity:
        codes = []
        identifiers_present = False
        for rows in tables:
            for index, headers in enumerate(rows):
                labels = {clean(cell).casefold(): i for i, cell in enumerate(headers)}
                if "name" not in labels or "citicode" not in labels:
                    continue
                identifiers_present = True
                for row in rows[index+1:]:
                    if len(row) > max(labels.values()) and row[labels["citicode"]].casefold() == identity.group(2).casefold():
                        codes.append(clean(row[labels["name"]]))
        if identifiers_present and (not codes or any(value != name for value in codes)):
            raise ExtractionError("Unit Citicode does not identify the requested fund")
    return tables


def grid_fields(name: str, tables: list[list[list[str]]]) -> dict[str, str]:
    """Read the exact share-class row from labeled, multi-column unit grids."""
    fields: dict[str, str] = {}
    aliases = {"mid": "mid price", "mid price": "mid price", "bid": "bid price",
               "offer": "offer price", "price": "mid price", "currency": "currency",
               "fe fundinfo risk score": "fe fundinfo risk score"}
    for rows in tables:
        for index, headers in enumerate(rows):
            positions = {clean(cell).casefold().rstrip(":"): i for i, cell in enumerate(headers)}
            if "name" not in positions or not (set(positions) & set(aliases)):
                continue
            name_index = positions["name"]
            matches = [row for row in rows[index+1:] if len(row) > name_index and clean(row[name_index]) == name]
            if len(matches) != 1:
                raise ExtractionError("Missing or ambiguous share-class row in unit grid")
            row = matches[0]
            if len(row) != len(headers):
                raise ExtractionError("Unit grid cells do not align with labeled headers")
            date = row[positions["date"]] if "date" in positions else None
            for label, key in aliases.items():
                if label not in positions:
                    continue
                value = clean(row[positions[label]])
                if key.endswith("price") and value.casefold() not in MISSING and date and re.fullmatch(r"\d{2}/\d{2}/\d{4}", date) and "(" not in value:
                    value += f" ({date})"
                if key in fields and fields[key] != value:
                    raise ExtractionError(f"Conflicting {key} unit-grid fields")
                fields[key] = value
    return fields


def parse_fund_tables(name: str, tables: list[list[list[str]]], rec: InputFund,
                      sector: str | None, sector_url: str | None,
                      unit_tables: list[list[list[str]]] | None = None) -> FundRecord:
    candidates = []
    quartiles = []
    for rows in tables:
        if not rows:
            continue
        try:
            positions = header_map(rows[0], FUND_PERIODS)
        except ExtractionError:
            continue
        row = labeled_row(rows[1:], name)
        if row is None:
            continue
        candidates.append(performance(row, positions))
        rank = labeled_row(rows[1:], "Quartile Ranking")
        # Compatibility: the historic Quartile column refers to the 3-month ranking.
        if rank:
            if len(rank) <= positions["3m"]:
                raise ExtractionError("Quartile row is shorter than its headers")
            quartiles.append(ranking(rank[positions["3m"]]))
    if not candidates:
        raise ExtractionError("Named cumulative performance row not found")
    if any(value != candidates[0] for value in candidates[1:]):
        raise ExtractionError("Conflicting cumulative performance tables")
    if quartiles and any(value != quartiles[0] for value in quartiles[1:]):
        raise ExtractionError("Conflicting quartile rows")
    fields = grid_fields(name, unit_tables if unit_tables is not None else tables)
    for rows in tables:
        for row in rows:
            if len(row) == 2:
                key = clean(row[0]).casefold().rstrip(":")
                key = {"bid": "bid price", "offer": "offer price", "mid": "mid price", "price": "mid price"}.get(key, key)
                if key in {"mid price", "bid price", "offer price", "fe fundinfo risk score", "sector", "aic sector"}:
                    value = clean(row[1])
                    if key in fields and fields[key] != value:
                        raise ExtractionError(f"Conflicting {key} fields")
                    fields[key] = value
    sector_field = fields.get("sector") or fields.get("aic sector")
    if not sector and sector_field:
        sector = re.sub(r"\s*\(View (?:more|sector)\)\s*$", "", sector_field, flags=re.I)
    warnings = []
    price, price_unit, price_date = None, None, None
    raw_price = next((fields[key] for key in ("mid price", "bid price", "offer price")
                      if key in fields and fields[key].casefold() not in MISSING), None)
    if raw_price:
        if "\ufffd" in raw_price:
            warnings.append(f"Price unavailable: source contains an undecodable currency/unit: {raw_price}")
            date = re.search(r"\((\d{2}/\d{2}/\d{4})\)", raw_price)
            price_date = date.group(1) if date else None
        else:
            match = re.fullmatch(r"([\u00a3$\u20ac]?[\d,.]+)\s*(p|c|\u00a2|GBP|GBX|USD|EUR)?(?:\s*\((\d{2}/\d{2}/\d{4})\))?", raw_price, re.I)
            if not match:
                raise ExtractionError(f"Unrecognized price field: {raw_price!r}")
            price, price_unit, price_date = match.groups()
            number(price.lstrip("\u00a3$\u20ac"))
            if price_unit and price_unit.lower() != "p":
                price += price_unit
    if price is not None and price_unit is None:
        price_unit = fields.get("currency")
    risk = number(fields["fe fundinfo risk score"]) if "fe fundinfo risk score" in fields else None
    if risk is not None and (risk < 0 or not risk.is_integer()):
        raise ExtractionError("Invalid FE risk score")
    for key, value in candidates[0].items():
        if value is None:
            warnings.append(f"Source return unavailable: {key}")
    for label, value in (("sector", sector), ("price", price), ("FE risk", risk), ("quartile", quartiles[0] if quartiles else None)):
        if value is None:
            warnings.append(f"Source field absent or unavailable: {label}")
    return FundRecord(name=name, url=rec.url, hold=rec.hold, holding_pct=rec.holding_pct,
        performance=candidates[0], sector=sector, sector_url=sector_url,
        quartile=quartiles[0] if quartiles else None, fe_risk=int(risk) if risk is not None else None,
        price=price, price_unit=price_unit, price_date=price_date, warnings=warnings)

def collect_fund(ctx: BrowserContext, rec: InputFund, cfg: Config) -> FundRecord:
    for attempt in attempts(cfg):
        with attempt, opened_page(ctx, rec.url, cfg) as page:
            try:
                expect(page.locator("h1").first).not_to_be_empty(timeout=cfg.nav_timeout_sec * 1000)
            except AssertionError as exc:
                raise TransientSourceError("Fund identity did not load") from exc
            name = clean(page.locator("h1").first.inner_text())
            # Both mobile and desktop tables can exist. Wait for the named row.
            page.wait_for_function("""name => Array.from(document.querySelectorAll('table')).some(t =>
                Array.from(t.rows).some(r => r.cells[0]?.textContent.trim() === name))""", arg=name)
            units = page.locator("section.component").filter(
                has=page.locator("h2,h3").filter(has_text=re.compile(r"^\s*Unit (?:Information|Details)\s*$")))
            for component in units.all():
                try:
                    component.locator("tbody tr").first.wait_for(state="attached", timeout=cfg.nav_timeout_sec * 1000)
                except PWTimeout:
                    if not component.get_by_text("Component failed to load", exact=True).count():
                        raise TransientSourceError("Unit information did not finish loading")
            tables = page.locator("table").evaluate_all("els => els.map(" + TABLE_ROWS + ")")
            if not any(any(row and clean(row[0]) == name for row in table) for table in tables):
                raise TransientSourceError("Trustnet fund components failed to load")
            links = page.locator('a[href*="sector="]').evaluate_all("els => els.map(e => ({name:e.textContent.trim(),url:e.getAttribute('href')}))")
            sectors = {(clean(link["name"]), urljoin(page.url, link["url"]))
                       for link in links if re.match(r"^(?:IA|IT|PN|LF|FO|ETF) ", clean(link["name"]))}
            if len(sectors) > 1:
                raise ExtractionError("Ambiguous fund sector links")
            sector, sector_url = next(iter(sectors), (None, None))
            unit_tables = unit_tables_for_page(units, name, rec.url) if units.count() else []
            record = parse_fund_tables(name, tables, rec, sector, sector_url, unit_tables)
            if page.get_by_text("Component failed to load", exact=True).count():
                record.warnings.append("One or more source components failed to load; inspect optional fields")
            return record
    raise RuntimeError("No collection attempt was made")

def validate_sectors(rows: list[SectorRecord], total: int | None = None) -> None:
    names = [row.name.strip() for row in rows]
    if not names or any(not name for name in names) or len(names) != len(set(names)):
        raise ExtractionError("Empty, blank, or duplicate sectors returned")
    if total is not None and len(rows) != total:
        raise ExtractionError(f"Incomplete sectors: expected {total}, got {len(rows)}")

def collect_sector_page(page: Page) -> list[SectorRecord]:
    table = page.locator(SECTORS_TABLE_CONTAINER).locator("table")
    rows = table.evaluate(TABLE_ROWS)
    if not rows:
        raise ExtractionError("Sector table is empty")
    positions = header_map(rows[0], SECTOR_PERIODS)
    data = page.locator(SECTORS_TABLE_CONTAINER).locator("tbody tr").evaluate_all(
        "els => els.map(r => ({cells:Array.from(r.cells).map(c=>c.textContent.trim()),href:r.cells[0]?.querySelector('a')?.getAttribute('href')}))")
    result = []
    for row in data:
        cells = row["cells"]
        if len(cells) < 2:  # pagination or non-data footer
            continue
        result.append(SectorRecord(name=clean(cells[0]), performance=performance(cells, positions),
            source_url=urljoin(page.url, row["href"]) if row["href"] else None))
    validate_sectors(result)
    return result

def collect_sectors(ctx: BrowserContext, cfg: Config) -> list[SectorRecord]:
    for attempt in attempts(cfg):
        with attempt, opened_page(ctx, SECTORS_URL, cfg) as page:
            try:
                return paginate_sectors(page, cfg)
            except AssertionError as exc:
                raise TransientSourceError("Sector table did not finish loading or changing") from exc
    raise RuntimeError("No collection attempt was made")

def paginate_sectors(page: Page, cfg: Config) -> list[SectorRecord]:
    table = page.locator(SECTORS_TABLE_CONTAINER)
    first = table.locator("tbody tr td:first-child").first
    expect(first).to_have_text(re.compile(r"IA .+"), timeout=cfg.nav_timeout_sec * 1000)
    total_el = page.locator(".sectors-count").first
    total = None
    if total_el.count():
        expect(total_el).to_have_text(re.compile(r"\s*\d+\s*"))
        total = int(total_el.inner_text())
    all_rows = []
    current = 1
    while True:
        rows = collect_sector_page(page)
        validate_sectors(all_rows + rows)
        all_rows.extend(rows)
        buttons = table.locator(".set-page")
        numbers = [int(text) for text in buttons.all_text_contents() if text.strip().isdigit()]
        if not numbers:
            if total is None or len(all_rows) != total:
                raise ExtractionError("Sector pagination controls are missing")
            break
        if current >= max(numbers):
            break
        if current >= 100:
            raise ExtractionError("Sector pagination exceeded safety limit")
        next_button = buttons.filter(has_text=re.compile(rf"^\s*{current + 1}\s*$"))
        if next_button.count() != 1:
            raise ExtractionError(f"Missing or ambiguous sector page {current + 1}")
        previous_name = rows[0].name
        next_button.click(timeout=cfg.nav_timeout_sec * 1000)
        expect(first).not_to_have_text(previous_name, timeout=cfg.nav_timeout_sec * 1000)
        expect(first).to_have_text(re.compile(r"IA .+"), timeout=cfg.nav_timeout_sec * 1000)
        current += 1
    validate_sectors(all_rows, total)
    logger.info("sectors_collected", extra={"kv": {"rows": len(all_rows), "pages": current}})
    return all_rows
