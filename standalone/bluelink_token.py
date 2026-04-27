#!/usr/bin/env python3
"""
Bluelink Token Generator — Standalone Desktop Application.
Opens a browser with the Web UI for token generation.
"""

import os
import sys
import threading
import webbrowser
import time

# Set up the path so we can import web.py
sys.path.insert(0, os.path.dirname(__file__))

PORT = 9876


def main():
    # Import web app
    from web import app

    print(f"\n🚗 Bluelink Token Generator")
    print(f"   Opening http://localhost:{PORT} in your browser...\n")

    # Open browser after a short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    # Run Flask (production-ish, single thread is fine for desktop use)
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
