# Snap to Intelligence: Workspace Extension

Capture equipment labels into a reviewable inventory workspace. The app stores data in SQLite, extracts structured fields in the background, records every correction, and exports workspaces to Excel.

## Prerequisites

- **Python 3.11 or 3.12** from [python.org](https://www.python.org/downloads/windows/). During installation, select **Add Python to PATH**.
- **Node.js 20 LTS or newer** from [nodejs.org](https://nodejs.org/).
- **Tesseract OCR** only if you want the fallback extraction path. Install the Windows build from the [UB Mannheim Tesseract page](https://github.com/UB-Mannheim/tesseract/wiki) and make sure its install directory is on `PATH`.

The checked-in `.venv` was created from an inaccessible Microsoft Store Python alias. Recreate it after installing Python:

```powershell
cd "D:\Snap to Intelligence"
Remove-Item -LiteralPath ".venv" -Recurse -Force
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

If PowerShell prevents activation, run this once in a normal PowerShell session:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Configure API keys

Copy `backend/.env.example` to `backend/.env` and replace the placeholders:

```powershell
Copy-Item backend\.env.example backend\.env
```

- `GEMINI_API_KEY` is required for live nameplate extraction. Create a free key in [Google AI Studio](https://aistudio.google.com/apikey).
- `SERPAPI_KEY` is optional for live web enrichment. Create one at [SerpAPI](https://serpapi.com/manage-api-key). Without it, scans can still return the label-extraction results.
- `GEMINI_MODEL` can stay as `gemini-flash-lite-latest` for development.

Never commit `backend/.env`.

## Run locally

Open two PowerShell terminals.

Backend:

```powershell
cd "D:\Snap to Intelligence"
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --reload --port 8000
```

Frontend (React, not Vite):

```powershell
cd "D:\Snap to Intelligence\frontend"
npm.cmd install
npm.cmd start
```

Open [http://localhost:3000](http://localhost:3000). API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

`npm.cmd` avoids a PowerShell policy issue where `npm.ps1` is blocked. The database (`backend/snap_to_intelligence.db`) and upload directory are created automatically and are intentionally ignored by Git.

## Full demo flow

1. Create a workspace.
2. Upload a JPEG/PNG/WebP image or select **Use camera** and take a snapshot.
3. The new item starts as **Processing** and polls until extraction completes.
4. Open the item, review low-confidence or conflicting fields, and accept or correct them.
5. Download **Create Excel** from the workspace page. The workbook contains `Summary` and `Field Detail` sheets.
