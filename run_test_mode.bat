@echo off
chcp 65001 >nul
cd /d "%~dp0"
set LOCAL_TEST_MODE=1

echo ============================================================
echo   Hakbah Million - Isolated Local Test Mode (Sandbox)
echo   Database: hakbah_test.db (NO Railway Server Sync)
echo ============================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" admin_app.py
) else if exist "dist\HakbahMillionAdmin\HakbahMillionAdmin.exe" (
    "dist\HakbahMillionAdmin\HakbahMillionAdmin.exe"
) else (
    python admin_app.py
)
