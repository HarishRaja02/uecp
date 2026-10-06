# Validation

## Completed in the build environment
- Python backend source compiled successfully with `python -m compileall`.
- Project structure checked after conversion to Flask + React.js.
- No Docker configuration or Docker runtime dependency is included.
- Secrets are excluded from source control via `.gitignore`.

## Not executable in this sandbox
The sandbox does not have the project's third-party Flask stack installed and cannot download the packages from PyPI/npm reliably. Therefore a full runtime pytest suite and React production build were not falsely marked as passed here.

## Local validation
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
.\scripts\generate_keys.ps1
$env:PYTHONPATH="backend"
python backend\seed.py
pytest -q backend\tests
python backend\app\main.py
```
In another terminal:
```powershell
cd frontend
npm install
npm run build
npm run dev
```
