$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
try {
    $taskRunningApp = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/notices/state' -TimeoutSec 2
    if ($taskRunningApp.version -eq '0.2.0') {
        Start-Process 'http://127.0.0.1:8765/'
        exit 0
    }
} catch { }
$taskVenvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $taskVenvPython)) {
    $taskPython = $null
    foreach ($candidate in @('py', 'python', 'python3')) {
        $cmdInfo = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmdInfo) {
            try {
                & $cmdInfo.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
                if ($LASTEXITCODE -eq 0) { $taskPython = $cmdInfo.Source; break }
            } catch { }
        }
    }
    if (!$taskPython) {
        Write-Host 'Python 3.10+ is required. Install it from https://www.python.org/downloads/ and enable Add Python to PATH.'
        exit 1
    }
    & $taskPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$taskLock = Join-Path $PSScriptRoot 'requirements.txt'
$taskHash = (Get-FileHash -LiteralPath $taskLock -Algorithm SHA256).Hash
$taskStamp = Join-Path $PSScriptRoot '.venv\requirements.sha256'
if (!(Test-Path -LiteralPath $taskStamp) -or (Get-Content -LiteralPath $taskStamp -Raw).Trim() -ne $taskHash) {
    & $taskVenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Host 'Dependency installation failed. Check network and retry.'; exit 1 }
    Set-Content -LiteralPath $taskStamp -Value $taskHash -Encoding ASCII
}
Write-Host 'Read HANDOFF.md before collecting or changing this project.'
Write-Host 'Opening http://127.0.0.1:8765 - keep this window running for scheduled scans.'
& $taskVenvPython notice_app.py --open
exit $LASTEXITCODE
