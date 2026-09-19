<#
    Installs pnpm without administrator rights.

    Background: the winget Node MSI did finish writing files to
    C:\Program Files\nodejs (and put it on the machine PATH), but
    `corepack enable pnpm` fails there with EPERM because creating its shims
    needs write access to Program Files.

    Fix: install pnpm with npm into a user-writable prefix and put that prefix
    on the user PATH. No elevation, and it survives shell restarts.
#>
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot\..\..
$log = '.kiro\scripts\setup-pnpm.log'
Remove-Item $log -ErrorAction SilentlyContinue
function Log($t) { $t | Out-File -Append -Encoding utf8 $log }

$ProgressPreference = 'SilentlyContinue'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

$sys = 'C:\Program Files\nodejs'
Log '--- system Node sanity ---'
Log "node: $(& "$sys\node.exe" -e 'console.log(process.version)' 2>&1)"
Log "npm : $(& "$sys\npm.cmd" --version 2>&1)"

$prefix = "$env:USERPROFILE\tools\npm-global"
New-Item -ItemType Directory -Force -Path $prefix | Out-Null

Log ''
Log "--- installing pnpm into $prefix ---"
& "$sys\npm.cmd" install -g pnpm --prefix $prefix 2>&1 |
    Select-Object -Last 12 | Out-File -Append -Encoding utf8 $log
Log "npm exit: $LASTEXITCODE"

Log ''
Log '--- prefix contents ---'
Get-ChildItem $prefix -ErrorAction SilentlyContinue | ForEach-Object { Log "  $($_.Name)" }

# Put the prefix on the user PATH (idempotent).
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $userPath) { $userPath = '' }
$parts = $userPath -split ';' | Where-Object { $_ }
if ($parts -notcontains $prefix) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $prefix) -join ';'), 'User')
    Log ''
    Log "added to user PATH: $prefix"
} else {
    Log ''
    Log 'prefix already on user PATH'
}

$env:Path = "$env:Path;$prefix"
Log ''
Log "pnpm version: $(& "$prefix\pnpm.cmd" --version 2>&1)"
