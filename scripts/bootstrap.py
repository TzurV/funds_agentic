"""Windows setup/launcher using one Drive runtime per computer. Stdlib only."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
POETRY_VERSION = "2.2.1"

def computer_id() -> str:
    raw = os.environ.get("FUNDS_COMPUTER_ID") or socket.gethostname()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", raw) or raw in {".", ".."}:
        raise ValueError("FUNDS_COMPUTER_ID must be a simple computer name, not a path")
    return raw.lower()

def runtime_paths() -> tuple[Path, Path, dict[str, str]]:
    directory = ROOT / "runtime" / computer_id()
    python = directory / ".venv" / "Scripts" / "python.exe"
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(directory / "browsers")
    environment["VIRTUAL_ENV"] = str(directory / ".venv")
    environment["PATH"] = str(python.parent) + os.pathsep + environment.get("PATH", "")
    environment["POETRY_VIRTUALENVS_CREATE"] = "false"
    environment["POETRY_KEYRING_ENABLED"] = "false"
    return directory, python, environment

def lock_hash() -> str:
    return hashlib.sha256((ROOT / "poetry.lock").read_bytes() + (ROOT / "pyproject.toml").read_bytes()).hexdigest()

def execute(command: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)

def main() -> int:
    if os.name != "nt":
        raise ValueError("This launcher supports Windows. The Python package can be invoked directly elsewhere.")
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Install Python 3.12 on this computer, then run setup.bat")
    args = sys.argv[1:]
    setup = bool(args and args[0] == "--setup")
    if setup:
        args = args[1:]
    directory, python, environment = runtime_paths()
    marker = directory / "environment.json"
    if setup:
        directory.mkdir(parents=True, exist_ok=True)
        tools = directory / ".poetry" / "Scripts" / "python.exe"
        execute([sys.executable, "-m", "venv", "--upgrade", str(tools.parents[1])])
        execute([str(tools), "-m", "pip", "install", "--quiet", f"poetry=={POETRY_VERSION}"])
        execute([sys.executable, "-m", "venv", "--upgrade", str(python.parents[1])])
        execute([str(tools), "-m", "poetry", "sync", "--with", "dev", "--no-interaction"], environment)
        execute([str(python), "-m", "playwright", "install", "chromium"], environment)
        marker.write_text(json.dumps({"lock_hash": lock_hash(), "python": str(Path(sys._base_executable).resolve()),
            "computer": computer_id(), "project_root": str(ROOT)}, indent=2), encoding="utf-8")
        print(f"Environment ready: {python}")
        return 0
    if not python.is_file() or not marker.is_file():
        raise ValueError("Run setup.bat once on this computer before run.bat")
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    if metadata.get("lock_hash") != lock_hash():
        raise ValueError("Locked dependencies changed. Run setup.bat explicitly to synchronize this computer.")
    if metadata.get("project_root") != str(ROOT):
        raise ValueError("Project location changed. Run setup.bat to update this computer's environment.")
    if metadata.get("python") != str(Path(sys._base_executable).resolve()):
        raise ValueError("Local Python installation changed. Run setup.bat on this computer.")
    # Run a preflight in the actual runtime; a synced environment may reference
    # another installation after a rename or relocation.
    execute([str(python), "-c", "import sys; assert sys.version_info[:2] == (3, 12); import pandas, pydantic, playwright"], environment)
    check_browser = "from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); available=Path(p.chromium.executable_path).is_file(); p.stop(); assert available, 'Browser missing; run setup.bat'"
    execute([str(python), "-c", check_browser], environment)
    module = "pytest" if args and args[0] == "--test" else "funds_agentic.main"
    if module == "pytest":
        args = args[1:]
    return subprocess.run([str(python), "-m", module, *args], cwd=ROOT, env=environment).returncode

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Setup/launch failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
