"""Desktop launcher for the packaged (e.g. Windows) Schedy app.

Starts the FastAPI server (which serves both the API and the bundled built
frontend) and opens the planner's default browser. This is the PyInstaller entry
point — see docs/windows.md.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser


def _resource_dir() -> str:
    # PyInstaller unpacks bundled data files to sys._MEIPASS at runtime.
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    import uvicorn
    from schedy.api import create_app

    # Persist the catalog in the user's profile, not next to the executable.
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    db_dir = os.path.join(base, "Schedy")
    os.makedirs(db_dir, exist_ok=True)
    os.environ.setdefault("SCHEDY_DB", os.path.join(db_dir, "schedy.sqlite"))

    # Serve the bundled built frontend (PyInstaller puts it under _MEIPASS/dist).
    os.environ.setdefault("SCHEDY_STATIC", os.path.join(_resource_dir(), "dist"))

    port = int(os.environ.get("SCHEDY_PORT", "8000"))
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
