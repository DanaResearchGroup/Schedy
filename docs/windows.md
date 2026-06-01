# Running & packaging Schedy on Windows

Schedy is cross-platform — every dependency (OR-Tools, FastAPI, uvicorn, openpyxl,
reportlab, SQLite) ships Windows wheels, and the React frontend is OS-agnostic.
This page covers two things:

1. **Running it on a developer's Windows machine** (conda + Node).
2. **Packaging a one-click app** for a non-technical planner — a single `.exe`
   that needs neither Python, conda, nor Node installed.

The key idea for both: **FastAPI serves the *built* frontend itself**, so the
planner runs **one** process and opens a browser. No Node at runtime.

---

## 1. Run on a Windows dev machine

Install [Miniforge](https://github.com/conda-forge/miniforge) and
[Node 20+](https://nodejs.org).

```powershell
# from the repo root (PowerShell)
conda env create -f environment.yml
conda activate schedy
pip install -e backend

# build the frontend once -> frontend/dist
cd frontend
npm install
npm run build
cd ..

# run single-process: FastAPI serves API + the built SPA
$env:SCHEDY_STATIC = "frontend\dist"
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000
# open http://localhost:8000
```

For active frontend development use two processes instead (Vite proxies `/api`):

```powershell
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000
# in another terminal:
cd frontend; npm run dev        # http://localhost:5173
```

> **How the API base is resolved.** In dev the frontend calls `/api/*` and Vite
> proxies to the backend. The production build (`frontend/.env.production` sets
> `VITE_API_BASE=`) calls the same origin that serves it, so no proxy is needed.

---

## 2. Package a one-click `.exe` (recommended: PyInstaller)

This produces a self-contained folder the planner can copy and double-click.
`backend/launcher.py` is the entry point: it starts the server, serves the
bundled SPA, opens the browser, and stores the catalog under
`%APPDATA%\Schedy\schedy.sqlite`.

### Build steps (on a Windows machine, in the `schedy` env)

```powershell
conda activate schedy
pip install -e backend
pip install pyinstaller

# 1. Build the frontend
cd frontend; npm install; npm run build; cd ..

# 2. Bundle backend + built frontend into one folder
pyinstaller backend\launcher.py ^
  --name Schedy ^
  --collect-all ortools ^
  --collect-all reportlab ^
  --collect-submodules uvicorn ^
  --add-data "frontend\dist;dist" ^
  --noconfirm
```

Notes on the flags:

- `--collect-all ortools` — OR-Tools ships native binaries and data the analysis
  step misses; this grabs them. (Same reason for `reportlab`.)
- `--collect-submodules uvicorn` — uvicorn imports its workers/loops lazily.
- `--add-data "frontend\dist;dist"` — bundles the built SPA; `launcher.py` reads
  it from `sys._MEIPASS\dist`. **The `;` separator is Windows-specific** (use `:`
  on macOS/Linux).
- Add `--noconsole` once stable to hide the terminal window (keep the console
  while testing so you can see errors).

The result is `dist\Schedy\Schedy.exe` plus its dependency folder. Zip
`dist\Schedy\` and hand it over. The planner double-clicks `Schedy.exe`; a browser
opens at `http://127.0.0.1:8000`.

### Optional: a desktop shortcut / launcher

Create `Schedy.bat` next to the exe if you prefer a visible launcher:

```bat
@echo off
start "" "%~dp0Schedy.exe"
```

---

## 3. Alternative: conda env + `.bat` (no PyInstaller)

Simpler to produce, but the target machine needs Miniforge installed. Ship the
repo + a launcher:

```bat
@echo off
call conda activate schedy
set SCHEDY_STATIC=%~dp0frontend\dist
start "" http://localhost:8000
uvicorn schedy.api:create_app --factory --app-dir "%~dp0backend" --port 8000
```

---

## Known gaps to address before shipping to end users

- **Hebrew text in PDF export.** The current `reportlab` export uses Helvetica,
  which cannot render Hebrew glyphs (a gap on *every* OS, not just Windows).
  Before relying on PDF, embed a Hebrew-capable TTF (e.g. Noto Sans Hebrew) and
  apply RTL shaping. CSV and the on-screen grid are unaffected.
- **Port already in use.** If `8000` is taken, set `SCHEDY_PORT` before launch.
- **Antivirus / SmartScreen.** Unsigned PyInstaller exes may trigger SmartScreen
  on first run. For wide distribution, code-sign the executable.
- **Catalog location.** Data lives at `%APPDATA%\Schedy\schedy.sqlite`. Document
  this for backups; deleting it resets the catalog.

## Cross-platform packaging note

PyInstaller is **not** a cross-compiler — build the Windows artifact *on* Windows
(a Windows VM or CI runner is fine). The same `launcher.py` + `--add-data` recipe
produces a macOS/Linux bundle when run on those platforms (swap `;` for `:`).
