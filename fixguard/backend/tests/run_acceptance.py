"""Run the SRS acceptance suite with one command.

The suite talks to a live API and a live testbed on purpose - mocking
Playwright would only prove the mock works. That honesty used to cost three
terminals to start, which meant the suite was run rarely and never in CI.
This starts both servers, waits for them, runs the scenarios and tears
everything down again.

    python -m tests.run_acceptance

Exits non-zero if any applicable scenario fails, so CI and a deploy gate can
use it directly.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TESTBED = BACKEND.parent / "testbed" / "server.py"
API_HEALTH = "http://127.0.0.1:8000/api/v1/health"
TESTBED_URL = "http://127.0.0.1:8080/good.html"
LOGS = BACKEND / "tests" / "_server_logs"


def wait_for(url: str, label: str, timeout: float = 90.0) -> None:
    """Poll until the service answers, rather than sleeping a guessed amount."""
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):
                print(f"  {label} is up")
                return
        except urllib.error.HTTPError:
            # Any HTTP answer means the server is listening, which is the
            # thing being waited for. The status code is not.
            print(f"  {label} is up")
            return
        except Exception as exc:  # noqa: BLE001 - any failure means not ready
            last = type(exc).__name__
            time.sleep(0.5)
    raise SystemExit(f"{label} did not come up within {timeout:.0f}s ({last})")


def main() -> int:
    env = {
        **os.environ,
        # The testbed lives on 127.0.0.1, which the auditor refuses to visit
        # unless it is told this is a test run.
        "ALLOW_PRIVATE_TARGETS": "1",
        "FIXGUARD_API_KEY": "fixguard-dev-key",
        "CORS_ORIGINS": "http://127.0.0.1:5173",
        "PUBLIC_BASE_URL": "http://127.0.0.1:5173",
    }

    # Server output is captured rather than inherited. Playwright's node
    # driver throws EPIPE when uvicorn is torn down with a browser still
    # open, and that noise prints after the results - exactly where a reader
    # looks for the verdict. The logs are still shown whenever a server
    # fails to start, which is when they carry information.
    LOGS.mkdir(exist_ok=True)
    handles: list = []
    procs: list[subprocess.Popen] = []

    def spawn(name: str, argv: list[str], cwd: Path) -> None:
        fh = (LOGS / f"{name}.log").open("w", encoding="utf-8")
        handles.append(fh)
        procs.append(subprocess.Popen(argv, cwd=str(cwd), env=env,
                                      stdout=fh, stderr=fh))

    def dump(name: str) -> None:
        path = LOGS / f"{name}.log"
        if path.exists():
            print(f"\n----- {name} log -----")
            print(path.read_text(encoding="utf-8", errors="replace")[-4000:])

    try:
        print("starting testbed...")
        spawn("testbed", [sys.executable, str(TESTBED)], TESTBED.parent)
        try:
            wait_for(TESTBED_URL, "testbed")
        except SystemExit:
            dump("testbed")
            raise

        print("starting api...")
        spawn("api",
              [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
              BACKEND)
        try:
            wait_for(API_HEALTH, "api")
        except SystemExit:
            dump("api")
            raise

        print("running acceptance scenarios...\n")
        from tests import test_acceptance, test_accounts

        srs = test_acceptance.main()
        print("\nrunning account scenarios...\n")
        # Both run even when the first fails. A red SRS suite says nothing
        # about whether ownership still holds, and finding out both at once
        # is worth more than stopping at the first bad news.
        accounts = test_accounts.main()
        return srs or accounts
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        for fh in handles:
            fh.close()


if __name__ == "__main__":
    sys.exit(main())
