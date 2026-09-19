<#
    Installs the grading dependencies, downloads the pinned keypoint models, and
    proves both landmarkers actually construct and run on a real frame.

    Constructing them is the part worth verifying: the wheels resolving says
    nothing about whether the native delegate loads on this machine.
#>
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root
$log = Join-Path $root '.kiro\scripts\grading.log'
Remove-Item $log -ErrorAction SilentlyContinue
function Log($t) { $t | Out-File -Append -Encoding utf8 $log }
function Section($n) { Log ''; Log "===== $n =====" }

$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

Section 'uv sync (installs mediapipe + numpy)'
uv sync --all-groups 2>&1 | Select-Object -Last 15 | Out-File -Append -Encoding utf8 $log
Log "exit: $LASTEXITCODE"

Section 'fetch models'
# The script lives in backend\scripts; `-m` resolves modules from the cwd.
Push-Location (Join-Path $root 'backend')
uv run python -m scripts.fetch_models 2>&1 | Out-File -Append -Encoding utf8 $log
Pop-Location
Log "exit: $LASTEXITCODE"

Section 'construct + run both landmarkers'
uv run python (Join-Path $root '.kiro\scripts\_probe_landmarkers.py') 2>&1 |
    Out-File -Append -Encoding utf8 $log
Log "exit: $LASTEXITCODE"

Section 'regression: existing tests still pass'
uv run pytest -q 2>&1 | Select-Object -Last 8 | Out-File -Append -Encoding utf8 $log
Log "exit: $LASTEXITCODE"
