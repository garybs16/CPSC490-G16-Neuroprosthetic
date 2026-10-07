"""
One-click launcher for BridgeWatch (SNX-3 prototype).

In VS Code: open this file and press Run. It runs the tests, starts the server
at http://127.0.0.1:8001 and opens the dashboard. Stop the server with Ctrl+C.

Install the packages once first:  pip install -r requirements.txt -r requirements-dev.txt

  python run_bridgewatch.py          live: real bridges on Ethereum mainnet (needs internet)
  python run_bridgewatch.py --demo   synthetic bridges with a "simulate exploit" button
"""

import importlib.util
import os
import subprocess
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8001"
os.chdir(HERE)
sys.path.insert(0, HERE)
if "--demo" in sys.argv:
    os.environ["BRIDGEWATCH_MODE"] = "demo"      # the flag wins over an inherited env var
else:
    os.environ.setdefault("BRIDGEWATCH_MODE", "live")

missing = [m for m in ("fastapi", "uvicorn", "httpx") if importlib.util.find_spec(m) is None]
if missing:
    sys.exit(f"Missing packages: {', '.join(missing)}. Run once:  pip install -r requirements.txt -r requirements-dev.txt")
if importlib.util.find_spec("pytest") is not None:
    print("1) Running BridgeWatch tests...", flush=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q"], check=False)
mode = os.environ["BRIDGEWATCH_MODE"]
print(f"2) Starting the server at {URL} in {mode} mode "
      f"({'reading 7 days of real bridge history first' if mode == 'live' else 'synthetic data'})...", flush=True)
threading.Timer(4, lambda: webbrowser.open(URL)).start()

import uvicorn  # noqa: E402

uvicorn.run("bridgewatch.app:app", host="127.0.0.1", port=8001, log_level="warning")
