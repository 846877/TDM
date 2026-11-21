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

$dockerVersion = "27.5.1"
$composeVersion = "2.32.4"
$dockerCli = "build\docker"
if (-not (Test-Path "$dockerCli\docker.exe")) {
    # Client docker (sans moteur) et plugin compose : sans Docker Desktop, ils pilotent le moteur Docker
    # de TDM (VM VirtualBox, labs\moteur-docker). Le moteur dockerd.exe de l'archive n'est pas embarqué.
    New-Item -ItemType Directory -Force "$dockerCli\cli-plugins" | Out-Null
    $zip = "build\docker-cli.zip"
    Invoke-WebRequest "https://download.docker.com/win/static/stable/x86_64/docker-$dockerVersion.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath "build\docker-zip" -Force
    Copy-Item "build\docker-zip\docker\docker.exe" "$dockerCli\docker.exe"
    Invoke-WebRequest "https://github.com/docker/compose/releases/download/v$composeVersion/docker-compose-windows-x86_64.exe" `
        -OutFile "$dockerCli\cli-plugins\docker-compose.exe"
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
    --add-data "$dockerCli;docker" `
    --collect-submodules app `
    --collect-submodules uvicorn `
    --collect-all webview `
    --collect-all winpty `
    --exclude-module winpty.tests --exclude-module pytest `
    --hidden-import vagrant_agent `
    desktop\tdm_desktop.py
Write-Host "OK : dist\TDM.exe"
