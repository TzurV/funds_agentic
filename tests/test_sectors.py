import importlib

import pytest
from playwright.sync_api import sync_playwright
from funds_agentic.state import State, Config, RunMeta
from funds_agentic.nodes.normalize_write_node import _to_df_sectors

sectors = importlib.import_module('funds_agentic.nodes.sectors_node')


@pytest.mark.parametrize('rows', [[], [{'sectorName': ''}],
    [{'sectorName': 'IA Global'}, {'sectorName': 'IA Global'}]])
def test_invalid_sector_data_cannot_be_exported(rows):
    with pytest.raises(ValueError):
        _to_df_sectors(rows)


@pytest.mark.parametrize('stuck', [False, True])
def test_pagination_ignores_decoy_and_requires_changed_rows(monkeypatch, stuck):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.set_content('''
            <a class="set-page" onclick="window.decoyClicked=true">2</a>
            <div id="sector-perf-table-pills-cumula-perf"><div class="table-responsive">
            <table><thead><tr><th>Name</th></tr></thead>
            <tbody><tr><td>IA Global</td><td>1</td><td>2</td><td>3</td>
            <td>4</td><td>5</td><td>6</td></tr></tbody></table>
            <a class="set-page">1</a><a class="set-page" id="next">2</a>
            </div></div>''')
        if not stuck:
            page.evaluate('''() => document.querySelector('#next').onclick = () =>
                setTimeout(() => document.querySelector('tbody td').textContent =
                'IA Volatility Managed', 150)''')
        monkeypatch.setattr(sectors, '_load_page', lambda *args: page)
        state = State(config=Config(output_dir='workspace', nav_timeout_sec=1),
            meta=RunMeta(run_id='test', run_date='20261107', timestamp='test'),
            browser_ctx=context)
        try:
            if stuck:
                with pytest.raises(AssertionError):
                    sectors.sectors_node({'state': state.model_dump()})
            else:
                rows = sectors.sectors_node({'state': state.model_dump()})['state']['sector_rows_raw']
                assert [r['sectorName'] for r in rows] == ['IA Global', 'IA Volatility Managed']
                assert rows[0]['5y'] == 6
            assert page.is_closed()
        finally:
            browser.close()
