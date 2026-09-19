<#
    Verifies the R1 baseline and logs everything to .kiro/scripts/baseline.log.

    Runs in a child process and writes to a file on purpose: the interactive
    shell mangles long commands and truncates progress output, so a log file is
    the only reliable way to read results back.
#>
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
Set-Location $PSScriptRoot\..\..

$log = '.kiro\scripts\baseline.log'
Remove-Item $log -ErrorAction SilentlyContinue

function Log($text) { $text | Out-File -Append -Encoding utf8 $log }
function Section($name) { Log ''; Log "===== $name =====" }

# Make the freshly installed tools visible to this process.
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

Section 'versions'
Log "uv      : $(uv --version 2>&1)"
Log "node    : $(node --version 2>&1)"
Log "ffmpeg  : $((ffmpeg -version 2>&1 | Select-Object -First 1))"
Log "python  : $(.venv\Scripts\python.exe --version 2>&1)"

Section 'corepack / pnpm'
corepack enable pnpm 2>&1 | Out-File -Append -Encoding utf8 $log
Log "pnpm    : $(pnpm --version 2>&1)"

Section 'pytest'
.venv\Scripts\python.exe -m pytest -q 2>&1 | Out-File -Append -Encoding utf8 $log
Log "pytest exit: $LASTEXITCODE"

Section 'ruff'
.venv\Scripts\python.exe -m ruff check . 2>&1 | Out-File -Append -Encoding utf8 $log
Log "ruff exit: $LASTEXITCODE"

Section 'pnpm install'
Push-Location frontend
pnpm install 2>&1 | Select-Object -Last 25 | Out-File -Append -Encoding utf8 $log
Log "pnpm install exit: $LASTEXITCODE"

Section 'tsc'
pnpm lint 2>&1 | Out-File -Append -Encoding utf8 $log
Log "tsc exit: $LASTEXITCODE"

Section 'vitest'
pnpm test 2>&1 | Out-File -Append -Encoding utf8 $log
Log "vitest exit: $LASTEXITCODE"
Pop-Location

Section 'done'
Log 'baseline verification finished'
