import pandas as pd
import pytest
from funds_agentic.config import build_parser, load_config
from funds_agentic.inputs import rows_from_frame, sheets_frame, fund_url
from funds_agentic.models import Config, RunMeta

URL1 = "https://www.trustnet.com/factsheets/o/a/fund-a"
URL2 = "https://www.trustnet.com/factsheets/o/b/fund-b"

def test_sheets_header_row_three_keeps_first_fund():
    frame = sheets_frame([["title"], ["notes"], ["url", "hold"], [URL1, "yes"], [URL2, "no"]], 3)
    rows = rows_from_frame(frame, Config(gdrive_id="test", output_dir="unused"), excel=False)
    assert [r.url for r in rows] == [URL1, URL2]

@pytest.mark.parametrize("header", [1, 3])
def test_excel_and_sheets_offsets_match(tmp_path, header):
    from funds_agentic.inputs import load_inputs
    path = tmp_path / "funds.xlsx"
    frame = pd.DataFrame({"url": [URL1, URL2], "hold": [True, False]})
    with pd.ExcelWriter(path) as writer: frame.to_excel(writer, sheet_name="TrackingList", startrow=header-1, index=False)
    cfg = Config(input_path=path, output_dir=tmp_path, row_start=header)
    assert len(load_inputs(cfg)) == 2

@pytest.mark.parametrize("url", ["file:///C:/test", "https://evil.example/factsheets/o/a/x", "https://trustnet.com@evil.example/factsheets/o/a/x"])
def test_non_fund_urls_rejected(url):
    with pytest.raises(ValueError): fund_url(url)

def test_explicit_missing_column_does_not_fall_back():
    cfg = Config(input_path="unused", output_dir="unused", col_url="missing")
    with pytest.raises(ValueError, match="override"):
        rows_from_frame(pd.DataFrame({"url": [URL1]}), cfg, excel=True)

def test_conflicting_duplicates_rejected():
    frame = pd.DataFrame({"url": [URL1, URL1], "hold": [True, False]})
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        rows_from_frame(frame, Config(input_path="unused", output_dir="unused"), excel=True)

def test_relative_paths_do_not_depend_on_cwd(tmp_path, monkeypatch):
    config = tmp_path / "settings.toml"
    config.write_text('shared_root = "."\n[scraper]\ninput_path = "holdings.xlsx"\noutput_dir = "output"\n')
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir(); monkeypatch.chdir(elsewhere)
    args = build_parser().parse_args(["--config", str(config), "--output", "verification"])
    cfg = load_config(args)
    assert cfg.input_path == tmp_path / "holdings.xlsx"
    assert cfg.output_dir == tmp_path / "verification"

def test_cli_source_override_replaces_default_excel(tmp_path):
    config = tmp_path / "settings.toml"
    config.write_text('[scraper]\ninput_path = "holdings.xlsx"\noutput_dir = "output"\n')
    cfg = load_config(build_parser().parse_args(["--config", str(config), "--gdrive-id", "example"]))
    assert cfg.input_path is None and cfg.gdrive_id == "example"

def test_run_ids_unique_and_timestamps_aware():
    one, two = RunMeta.now(), RunMeta.now()
    assert one.run_id != two.run_id
    from datetime import datetime
    assert datetime.fromisoformat(one.retrieved_at).tzinfo is not None
