from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
import funds_agentic.publishing as publishing
import funds_agentic.service as service
from funds_agentic.models import Config, FundRecord, InputFund, RunMeta, RunResult, SectorRecord
from funds_agentic.collection import opened_page

PERF = {"3m": 1., "6m": 2., "1y": 3., "3y": 4., "5y": 5.}

def result(status="success"):
    return RunResult(meta=RunMeta.now(), status=status, requested=1,
        funds=[FundRecord(name="Fund", url="https://www.trustnet.com/factsheets/o/a/fund", sector="IA Global", performance=PERF)],
        sectors=[SectorRecord(name="IA Global", performance={"1m": 0., **PERF})])

def test_csv_only_and_latest_points_to_coherent_snapshot(tmp_path):
    cfg = Config(input_path="unused", output_dir=tmp_path)
    run = result(); publishing.publish_result(run, cfg)
    latest = json.loads((tmp_path / "latest.json").read_text())
    snapshot = tmp_path / latest["snapshot"]
    assert snapshot == Path(run.snapshot_dir)
    assert len(list(snapshot.glob("*.csv"))) == 2
    assert not list(tmp_path.rglob("*.parquet"))
    import pandas as pd
    assert list(pd.read_csv(run.funds_csv).columns)[1:] == publishing.FUNDS_COLUMNS
    assert pd.read_csv(run.sectors_csv)["sectorName"].tolist() == ["IA Global"]

@pytest.mark.parametrize("failure", ["sectors", "latest"])
def test_failed_publication_restores_previous_exports(tmp_path, monkeypatch, failure):
    cfg = Config(input_path="unused", output_dir=tmp_path)
    first = result(); publishing.publish_result(first, cfg)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    second = result(); second.funds[0].name = "Changed"
    replace = publishing.os.replace
    failed = False
    def fault(src, dst):
        nonlocal failed
        target = Path(dst)
        if not failed and ((failure == "sectors" and target.parent == tmp_path and target.name.endswith("_sectors.csv"))
                           or (failure == "latest" and target.name == "latest.json")):
            failed = True
            raise PermissionError("injected write failure")
        return replace(src, dst)
    monkeypatch.setattr(publishing.os, "replace", fault)
    with pytest.raises(PermissionError): publishing.publish_result(second, cfg)
    assert all((tmp_path / name).read_bytes() == content for name, content in original.items())
    assert Path(first.snapshot_dir).is_dir()

def test_partial_run_does_not_replace_latest(tmp_path):
    cfg = Config(input_path="unused", output_dir=tmp_path)
    publishing.publish_result(result(), cfg)
    previous = (tmp_path / "latest.json").read_bytes()
    partial = result("partial"); publishing.publish_result(partial, cfg)
    assert (tmp_path / "latest.json").read_bytes() == previous
    assert json.loads((Path(partial.snapshot_dir) / "run.json").read_text())["status"] == "partial"

def test_page_closed_when_navigation_fails():
    ctx = Mock(); page = ctx.new_page.return_value; page.goto.side_effect = RuntimeError("failure")
    with pytest.raises(RuntimeError):
        with opened_page(ctx, "test", Config(input_path="unused", output_dir="unused")): pass
    page.close.assert_called_once()

def test_service_closes_session_and_preserves_latest_on_fund_failure(tmp_path, monkeypatch):
    cfg = Config(input_path="unused", output_dir=tmp_path)
    first = result(); publishing.publish_result(first, cfg)
    previous = (tmp_path / "latest.json").read_bytes()
    closed = []
    @contextmanager
    def session(cfg):
        try: yield object()
        finally: closed.append(True)
    monkeypatch.setattr(service, "load_inputs", lambda cfg: [InputFund(url="test")])
    monkeypatch.setattr(service, "browser_session", session)
    monkeypatch.setattr(service, "collect_sectors", lambda *args: first.sectors)
    def fail(*args): raise ValueError("missing performance table")
    monkeypatch.setattr(service, "collect_fund", fail)
    actual = service.run(cfg)
    assert actual.status == "partial" and actual.errors
    assert closed == [True]
    assert (tmp_path / "latest.json").read_bytes() == previous

def test_lock_refuses_second_writer_and_cleans_up(tmp_path):
    with publishing.output_lock(tmp_path):
        with pytest.raises(RuntimeError, match="lock exists"):
            with publishing.output_lock(tmp_path): pass
    assert not (tmp_path / ".funds-agentic.lock").exists()


def test_non_ia_sector_is_explicitly_unavailable_not_a_missing_ia_sector():
    actual = result()
    actual.funds[0].sector = "IT UK Equity Income"
    service.validate_coverage(actual)
    assert not actual.errors
    assert any("outside the IA universe" in warning for warning in actual.warnings)


def test_explicit_unclassified_sector_does_not_invent_benchmark():
    actual = result()
    actual.funds[0].sector = "IA Unclassified"
    service.validate_coverage(actual)
    assert not actual.errors
    assert any("no IA sector comparison" in warning for warning in actual.warnings)
