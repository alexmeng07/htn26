$ErrorActionPreference = 'Continue'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root
$log = Join-Path $root '.kiro\scripts\import.log'
Remove-Item $log -ErrorAction SilentlyContinue

# The Python code lives in backend\; PYTHONPATH makes `server.*` importable
# from the repo root, which is where .venv and .env live.
$env:PYTHONPATH = Join-Path $root 'backend'

'--- import server.main ---' | Out-File -Encoding utf8 $log
& .venv\Scripts\python.exe -c "import server.main; print('import ok')" 2>&1 |
    Out-File -Append -Encoding utf8 $log
"exit: $LASTEXITCODE" | Out-File -Append -Encoding utf8 $log

'' | Out-File -Append -Encoding utf8 $log
'--- uvicorn startup (5s, then killed) ---' | Out-File -Append -Encoding utf8 $log
$p = Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') `
    -ArgumentList '-m','uvicorn','--app-dir','backend','server.main:app','--port','8000' `
    -RedirectStandardOutput (Join-Path $root '.kiro\scripts\uvicorn.out') `
    -RedirectStandardError  (Join-Path $root '.kiro\scripts\uvicorn.err') `
    -WorkingDirectory $root -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 8

try {
    $r = Invoke-WebRequest 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 15
    "health status: $($r.StatusCode)" | Out-File -Append -Encoding utf8 $log
    $r.Content | Out-File -Append -Encoding utf8 $log
} catch {
    "health failed: $_" | Out-File -Append -Encoding utf8 $log
}

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue

'' | Out-File -Append -Encoding utf8 $log
'--- uvicorn stderr ---' | Out-File -Append -Encoding utf8 $log
Get-Content (Join-Path $root '.kiro\scripts\uvicorn.err') -ErrorAction SilentlyContinue |
    Out-File -Append -Encoding utf8 $log
