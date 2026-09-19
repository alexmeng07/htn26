<#
    One-off: put uv and the portable Node on the user PATH.

    Both tools were installed without administrator rights:
      - uv   via winget, which drops it under WinGet\Packages
      - Node as the official portable zip under ~\tools
    Neither location is on PATH by default, so `make`/tasks.ps1 could not find
    them. This adds them to the *user* PATH (no elevation, reversible by
    removing the two entries).

    Safe to re-run: entries are only added when missing.
#>
$ErrorActionPreference = 'Stop'

$uv = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter uv.exe -ErrorAction SilentlyContinue |
      Select-Object -First 1
if (-not $uv) { throw 'uv.exe not found under WinGet\Packages' }

$node = Get-ChildItem "$env:USERPROFILE\tools" -Directory -Filter 'node-v*-win-x64' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
if (-not $node) { throw 'portable Node not found under ~\tools' }

$wanted = @($uv.DirectoryName, $node.FullName)

$current = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $current) { $current = '' }
$parts = $current -split ';' | Where-Object { $_ }

$added = @()
foreach ($dir in $wanted) {
    if ($parts -notcontains $dir) {
        $parts += $dir
        $added += $dir
    }
}

if ($added) {
    [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User')
}

# Make it effective for the current process too, so callers need no new shell.
foreach ($dir in $wanted) {
    if (($env:Path -split ';') -notcontains $dir) { $env:Path = "$env:Path;$dir" }
}

Write-Output "uv   : $($uv.FullName)"
Write-Output "node : $($node.FullName)"
Write-Output "added to user PATH: $(if ($added) { $added -join ', ' } else { '(nothing, already present)' })"
