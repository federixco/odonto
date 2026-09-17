$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$LocalDir = Join-Path $ProjectRoot ".local"
$LogsDir = Join-Path $LocalDir "logs"
$RunDir = Join-Path $LocalDir "run"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$MinioExe = Join-Path $LocalDir "minio\minio.exe"
$MinioData = Join-Path $LocalDir "minio-data-clean"
$EnvFile = Join-Path $ProjectRoot ".env"

New-Item -ItemType Directory -Force -Path $LogsDir, $RunDir | Out-Null

function Stop-ProcessOnPort {
    param([int]$Port)

    $processIds = @(
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess

        netstat -ano -p tcp | ForEach-Object {
            if ($_ -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
                [int]$matches[1]
            }
        }
    ) | Sort-Object -Unique

    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-SavedProcess {
    param([string]$PidFile)

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return
    }

    $savedPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($savedPid -match '^\d+$') {
        Stop-Process -Id ([int]$savedPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Wait-ForPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 15
    )

    $limit = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
            return $true
        }
        if (netstat -ano -p tcp | Select-String -Quiet "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+\d+\s*$") {
            return $true
        }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $limit)

    return $false
}

Write-Host "Reiniciando el sistema..." -ForegroundColor Cyan

Stop-SavedProcess (Join-Path $RunDir "django.pid")
Stop-SavedProcess (Join-Path $RunDir "minio.pid")
Stop-ProcessOnPort 8000
Stop-ProcessOnPort 9000
Stop-ProcessOnPort 9001

# También limpia instancias viejas iniciadas desde este mismo repositorio.
Get-Process -Name "minio" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $MinioExe } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $PythonExe } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# El servicio utilizado por el proyecto es MySQL 8.4. Si ya esta activo, no hace nada.
$mysql = Get-Service -Name "MySQL84" -ErrorAction SilentlyContinue
if ($mysql -and $mysql.Status -ne "Running") {
    Start-Service -Name "MySQL84"
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "No se encontro el entorno virtual: $PythonExe"
}
if (-not (Test-Path -LiteralPath $MinioExe)) {
    throw "No se encontro MinIO: $MinioExe"
}
if (-not (Test-Path -LiteralPath $MinioData)) {
    New-Item -ItemType Directory -Force -Path $MinioData | Out-Null
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "No se encontro el archivo .env del proyecto."
}

$environment = @{}
foreach ($line in Get-Content -LiteralPath $EnvFile) {
    if ($line -match '^\s*([^#][^=]*)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"').Trim("'")
        $environment[$name] = $value
    }
}

if (-not $environment["AWS_ACCESS_KEY_ID"] -or -not $environment["AWS_SECRET_ACCESS_KEY"]) {
    throw "Faltan las credenciales locales de MinIO en .env."
}

$env:MINIO_ROOT_USER = $environment["AWS_ACCESS_KEY_ID"]
$env:MINIO_ROOT_PASSWORD = $environment["AWS_SECRET_ACCESS_KEY"]

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$minioOut = Join-Path $LogsDir "minio-$timestamp.out.log"
$minioErr = Join-Path $LogsDir "minio-$timestamp.err.log"
$djangoOut = Join-Path $LogsDir "django-$timestamp.out.log"
$djangoErr = Join-Path $LogsDir "django-$timestamp.err.log"

$minio = Start-Process `
    -FilePath $MinioExe `
    -ArgumentList @(
        "server",
        $MinioData,
        "--address", "127.0.0.1:9000",
        "--console-address", "127.0.0.1:9001"
    ) `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $minioOut `
    -RedirectStandardError $minioErr `
    -WindowStyle Hidden `
    -PassThru

$minio.Id | Set-Content -LiteralPath (Join-Path $RunDir "minio.pid")

if (-not (Wait-ForPort -Port 9000)) {
    throw "MinIO no pudo iniciar. Revisa $minioErr"
}

$django = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList @("manage.py", "runserver", "127.0.0.1:8000", "--noreload") `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $djangoOut `
    -RedirectStandardError $djangoErr `
    -WindowStyle Hidden `
    -PassThru

$django.Id | Set-Content -LiteralPath (Join-Path $RunDir "django.pid")

if (-not (Wait-ForPort -Port 8000)) {
    throw "Django no pudo iniciar. Revisa $djangoErr"
}

Write-Host "Sistema iniciado correctamente." -ForegroundColor Green
Write-Host "Aplicacion:    http://127.0.0.1:8000"
Write-Host "MinIO API:     http://127.0.0.1:9000"
Write-Host "MinIO consola: http://127.0.0.1:9001"
Write-Host "Logs:          $LogsDir"
