import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("bootstrap", Path(__file__).parents[1] / "scripts" / "bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)

@pytest.mark.parametrize("value", ["../other", "bad/name", "..", "bad name"])
def test_computer_id_cannot_escape_runtime(monkeypatch, value):
    monkeypatch.setenv("FUNDS_COMPUTER_ID", value)
    with pytest.raises(ValueError): bootstrap.computer_id()

def test_machine_runtime_paths_stay_with_project(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setenv("FUNDS_COMPUTER_ID", "Laptop-A")
    directory, python, environment = bootstrap.runtime_paths()
    assert directory == tmp_path / "runtime" / "laptop-a"
    assert python == directory / ".venv" / "Scripts" / "python.exe"
    assert environment["PLAYWRIGHT_BROWSERS_PATH"] == str(directory / "browsers")

def test_missing_runtime_requires_explicit_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(bootstrap.sys, "argv", ["bootstrap.py"])
    with pytest.raises(ValueError, match="setup.bat"):
        bootstrap.main()

def test_machine_specific_override(tmp_path, monkeypatch):
    from funds_agentic.config import build_parser, load_config
    monkeypatch.setenv("FUNDS_COMPUTER_ID", "Laptop-A")
    config = tmp_path / "settings.toml"
    config.write_text('[scraper]\ninput_path = "holdings.xlsx"\noutput_dir = "output"\n')
    machines = tmp_path / "machines"; machines.mkdir()
    (machines / "laptop-a.local.toml").write_text('[scraper]\noutput_dir = "laptop-output"\n')
    cfg = load_config(build_parser().parse_args(["--config", str(config)]))
    assert cfg.output_dir == tmp_path / "laptop-output"
