@echo off
setlocal EnableDelayedExpansion
REM Lance la plateforme TDM sous Windows (Docker Desktop doit etre demarre).
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop n'est pas lance. Demarre-le puis relance ce script.
  pause
  exit /b 1
)

REM Fichier .env : jeton de l'agent Vagrant et dossier des labs Vagrant (modifiable).
if not exist .env (
  for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set TOKEN=%%i
  > .env echo TDM_VAGRANT_TOKEN=!TOKEN!
  >> .env echo TDM_VAGRANT_DIR=%USERPROFILE%\Desktop\INFORMATIQUE\devops\vagrant
  echo Fichier .env cree.
)

REM Agent Vagrant : seulement si Vagrant et Python sont installes.
where vagrant >nul 2>&1
if not errorlevel 1 (
  set PY=
  where py >nul 2>&1 && set PY=py
  if "!PY!"=="" ( where python >nul 2>&1 && set PY=python )
  if "!PY!"=="" (
    echo Python est introuvable : les labs en machine virtuelle seront indisponibles.
  ) else (
    start "TDM - agent Vagrant" !PY! scripts\vagrant_agent.py
  )
) else (
  echo Vagrant n'est pas installe : les labs en machine virtuelle seront indisponibles.
)

docker compose up --build -d
if errorlevel 1 (
  pause
  exit /b 1
)
echo TDM demarre sur http://localhost:8000
timeout /t 3 >nul
start http://localhost:8000
