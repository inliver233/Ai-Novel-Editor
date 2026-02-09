param(
    [switch]$Clean = $false,
    [string]$SpecPath = "pyinstaller/ai_novel_editor.spec"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if ($Clean) {
    if (Test-Path build) { Remove-Item -Recurse -Force build }
    if (Test-Path dist) { Remove-Item -Recurse -Force dist }
}

# Prefer Python 3.11 on Windows (PyQt6 wheels + project deps). Fallback to `python` if `py` is unavailable.
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

try {
    Invoke-Python @("-c", "import PyInstaller; print(PyInstaller.__version__)") | Out-Null
} catch {
    Write-Error "PyInstaller not installed for the selected Python. Install with: $pythonExe $($pythonPrefixArgs -join ' ') -m pip install pyinstaller"
    exit 1
}

if (-not (Test-Path $SpecPath)) {
    Write-Error "Spec file not found: $SpecPath"
    exit 1
}

Invoke-Python @("-m", "PyInstaller", "--noconfirm", "--clean", $SpecPath)
Write-Host "Build done. Output: dist/"
