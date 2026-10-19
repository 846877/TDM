# Construit dist\TDM.exe (Windows). Usage : powershell -ExecutionPolicy Bypass -File desktop\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$pythonVersion = "3.12.8"
$embed = "build\python"
if (-not (Test-Path "$embed\python.exe")) {
    # Distribution « embeddable » officielle : c'est elle qui exécute le code des exercices.
    New-Item -ItemType Directory -Force build | Out-Null
    $zip = "build\python-embed.zip"
    Invoke-WebRequest "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $embed -Force
}

python -m pip install -r desktop\requirements.txt
# « labs » embarque aussi labs\systemes-windows (Vagrantfile + scripts des VM Windows) : l'agent Vagrant
# les copie dans %LOCALAPPDATA%\TDM\vagrant avant de les lancer (ne lance pas `vagrant up` dans le dépôt :
# l'état .vagrant serait embarqué dans l'exe).
python -m PyInstaller --noconfirm --clean --onefile --windowed --name TDM `
    --paths backend --paths scripts `
    --add-data "frontend;frontend" `
    --add-data "content;content" `
    --add-data "labs;labs" `
    --add-data "sandbox;sandbox" `
    --add-data "backend/app/python/runner.py;app/python" `
    --add-data "$embed;python" `
    --collect-submodules app `
    --collect-submodules uvicorn `
    --collect-all webview `
    --collect-all winpty `
    --exclude-module winpty.tests --exclude-module pytest `
    --hidden-import vagrant_agent `
    desktop\tdm_desktop.py
Write-Host "OK : dist\TDM.exe"
