param(
    [switch]$Recreate = $false
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

# Prefer Python 3.11 on Windows (PyQt6 wheels + repo tooling target-version).
$pythonExe = "python"
$pythonPrefixArgs = @()
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $pyLauncher) {
    $pythonExe = "py"
    $pythonPrefixArgs = @("-3.11")
}

function Invoke-Python {
    param([string[]]$PythonArgs)
    & $pythonExe @pythonPrefixArgs @PythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed (exit=$LASTEXITCODE): $pythonExe $($pythonPrefixArgs -join ' ') $($PythonArgs -join ' ')"
    }
}

$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"

if ($Recreate -and (Test-Path $venvDir)) {
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Invoke-Python @("-m", "venv", ".venv")
}

& $venvPython -m pip install -U pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $venvPython -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Bootstrap done."
Write-Host "Activate with: .venv\\Scripts\\Activate.ps1"

