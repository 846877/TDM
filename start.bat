@echo off
REM Lance la plateforme TDM sous Windows (Docker Desktop doit être démarré).
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop n'est pas lance. Demarre-le puis relance ce script.
  pause
  exit /b 1
)
docker compose up --build -d
if errorlevel 1 (
  pause
  exit /b 1
)
echo TDM demarre sur http://localhost:8000
timeout /t 3 >nul
start http://localhost:8000
