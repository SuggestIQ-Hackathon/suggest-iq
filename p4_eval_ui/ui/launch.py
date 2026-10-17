"""Start the dashboard in light mode.   python -m p4_eval_ui.ui.launch [--port 8501]   Owner: P4.

Equivalent to `streamlit run p4_eval_ui/ui/dashboard.py` with the light theme flags below.
"""
import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent / "dashboard.py"
LIGHT = {
    "theme.base": "light",
    "theme.primaryColor": "#4f46e5",
    "theme.backgroundColor": "#f7f8fc",
    "theme.secondaryBackgroundColor": "#eceff7",
    "theme.textColor": "#1b1f24",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="8501")
    ap.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = ap.parse_args()
    import threading
    import webbrowser

    from streamlit.web import cli

    url = f"http://localhost:{args.port}"
    print(f"Dashboard: {url}")
    if not args.no_open:
        threading.Timer(2.5, lambda: webbrowser.open(url)).start()

    sys.argv = ["streamlit", "run", str(APP), "--server.port", args.port, "--server.headless", "true", "--browser.gatherUsageStats", "false"] + [x for k, v in LIGHT.items() for x in (f"--{k}", v)]
    cli.main()


if __name__ == "__main__":
    main()
