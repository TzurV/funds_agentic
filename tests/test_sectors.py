import pytest
from playwright.sync_api import sync_playwright
from funds_agentic.collection import paginate_sectors, validate_sectors
from funds_agentic.models import Config, SectorRecord
from funds_agentic.parsing import ExtractionError

@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()

def test_empty_and_duplicate_sectors_rejected():
    row = SectorRecord(name="IA Global", performance={p: 0 for p in ("1m", "3m", "6m", "1y", "3y", "5y")})
    for rows in ([], [row, row]):
        with pytest.raises(ExtractionError): validate_sectors(rows)

@pytest.mark.parametrize("stuck", [False, True])
def test_pagination_ignores_decoy_and_waits_for_real_data(browser, stuck):
    page = browser.new_page()
    try:
        page.set_content('''<a class="set-page" onclick="window.decoy=true">2</a>
            <span class="sectors-count">2</span>
            <div id="sector-perf-table-pills-cumula-perf"><div class="table-responsive"><table>
            <thead><tr><th>Name</th><th>1 m (%)</th><th>3 m (%)</th><th>6 m (%)</th><th>1 y (%)</th><th>3 y (%)</th><th>5 y (%)</th></tr></thead>
            <tbody><tr><td>IA Global</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td></tr></tbody></table>
            <a class="set-page">1</a><a class="set-page" id="next">2</a></div></div>''')
        if not stuck:
            page.evaluate('''() => document.querySelector('#next').onclick = () => setTimeout(() =>
                document.querySelector('tbody td').textContent = 'IA Volatility Managed', 150)''')
        cfg = Config(input_path="unused", output_dir="unused", nav_timeout_sec=1)
        if stuck:
            with pytest.raises(AssertionError): paginate_sectors(page, cfg)
        else:
            rows = paginate_sectors(page, cfg)
            assert [r.name for r in rows] == ["IA Global", "IA Volatility Managed"]
            assert rows[1].performance["5y"] == 6
            assert page.evaluate("window.decoy") is None
    finally:
        page.close()

def test_incomplete_sector_total_is_rejected():
    with pytest.raises(ExtractionError, match="expected 55"):
        validate_sectors([SectorRecord(name="IA Global", performance={p: 0 for p in ("1m", "3m", "6m", "1y", "3y", "5y")})], 55)


@pytest.mark.parametrize("title", ["Unit Information", "Unit Details"])
def test_delayed_unit_grid_preserves_merged_price_columns_and_date(browser, title):
    from funds_agentic.collection import collect_fund
    from funds_agentic.models import InputFund
    context = browser.new_context()
    html = '''<h1>Fund I</h1><a href="/fund/sectors?sector=O:G">IA Global</a>
    <table><tr><th>Key</th><th>3 m</th><th>6 m</th><th>1 y</th><th>3 y</th><th>5 y</th></tr>
    <tr><td>Fund I</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr></table>
    <section class="component" style="display:none"><h2>__TITLE__</h2><table>
    <thead><tr><th>Name</th><th>Currency</th><th>Bid</th><th>Offer</th><th>Date</th></tr></thead>
    <tbody id="units"></tbody></table></section>
    <script>setTimeout(() => document.querySelector('#units').innerHTML =
    '<tr><td>Fund I</td><td>GBX</td><td colspan="2">118.1700p</td><td>06/11/2026</td></tr>', 150)</script>'''
    html = html.replace("__TITLE__", title)
    context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
    try:
        record = collect_fund(context, InputFund(url="https://www.trustnet.com/factsheets/o/test/fund"),
                              Config(input_path="unused", output_dir="unused", nav_timeout_sec=2))
        assert record.price == "118.1700" and record.price_date == "06/11/2026"
        assert not context.pages
    finally:
        context.close()


def test_duplicate_share_class_names_use_factsheet_links_and_citicode(browser):
    from funds_agentic.collection import collect_fund
    from funds_agentic.models import InputFund
    context = browser.new_context()
    html = '''<h1>Fund I</h1><a href="/fund/sectors?sector=O:G">IA Global</a>
    <table><tr><th>Key</th><th>3 m</th><th>6 m</th><th>1 y</th><th>3 y</th><th>5 y</th></tr>
    <tr><td>Fund I</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr></table>
    <section class="component" style="display:none"><h2>Unit Details</h2>
    <table><tr><th>Name</th><th>Currency</th><th>Bid</th><th>Offer</th><th>Date</th></tr>
    <tr><td><a href="/factsheets/E/AZFEE/other">Fund I</a></td><td>GBP</td><td colspan="2">589.7800p</td><td>06/11/2026</td></tr>
    <tr><td><a>Fund I</a></td><td>GBP</td><td colspan="2">755.9100p</td><td>06/11/2026</td></tr></table>
    <table><tr><th>Name</th><th>Citicode</th></tr>
    <tr><td><a href="/factsheets/E/AZFEE/other">Fund I</a></td><td>AZFEE</td></tr>
    <tr><td>Fund I</td><td>RO0H</td></tr></table></section>'''
    context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
    try:
        record = collect_fund(context, InputFund(url="https://www.trustnet.com/factsheets/E/RO0H/fund"),
                              Config(input_path="unused", output_dir="unused", nav_timeout_sec=2))
        assert record.price == "755.9100"
    finally:
        context.close()
