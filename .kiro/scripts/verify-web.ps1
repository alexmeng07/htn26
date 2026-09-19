$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path

# Absolute: this script changes directory into frontend/, so a relative log path
# would stop resolving half way through.
$log = Join-Path $root '.kiro\scripts\web.log'
Remove-Item $log -ErrorAction SilentlyContinue
function Log($t) { $t | Out-File -Append -Encoding utf8 $log }
function Section($n) { Log ''; Log "===== $n =====" }

$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

Set-Location $root
Section 'pnpm version'
Log "$(pnpm --version 2>&1)"

Set-Location (Join-Path $root 'frontend')

Section 'pnpm install'
pnpm install 2>&1 | Select-Object -Last 30 | Out-File -Append -Encoding utf8 $log
Log "exit: $LASTEXITCODE"

Section 'tsc (pnpm lint)'
pnpm lint 2>&1 | Select-Object -Last 30 | Out-File -Append -Encoding utf8 $log
Log "exit: $LASTEXITCODE"

Section 'vitest (pnpm test)'
pnpm test 2>&1 | Select-Object -Last 30 | Out-File -Append -Encoding utf8 $log
Log "exit: $LASTEXITCODE"

Section 'done'
