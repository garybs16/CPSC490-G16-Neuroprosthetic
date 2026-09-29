"""
One-click launcher for BridgeWatch (SNX-3 prototype).

In VS Code: open this file and press Run. It installs the packages, runs the
tests, starts the server at http://127.0.0.1:8001 and opens the dashboard.
Stop the server with Ctrl+C.

  python run_bridgewatch.py          live: real bridges on Ethereum mainnet (needs internet)
  python run_bridgewatch.py --demo   synthetic bridges with a "simulate exploit" button
"""

import os
import subprocess
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8001"
os.chdir(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("BRIDGEWATCH_MODE", "demo" if "--demo" in sys.argv else "live")

print("1) Installing packages...", flush=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt", "pytest"], check=False)
print("2) Running BridgeWatch tests...", flush=True)
subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_bridgewatch.py", "tests/test_bridgewatch_live.py"], check=False)
mode = os.environ["BRIDGEWATCH_MODE"]
print(f"3) Starting the server at {URL} in {mode} mode "
      f"({'reading 7 days of real bridge history first' if mode == 'live' else 'synthetic data'})...", flush=True)
threading.Timer(4, lambda: webbrowser.open(URL)).start()

import uvicorn  # noqa: E402

uvicorn.run("bridgewatch.app:app", host="127.0.0.1", port=8001, log_level="warning")
