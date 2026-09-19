<#
    SceneStealer task runner for Windows (the `make` equivalent).
        .\tasks.ps1 setup
        .\tasks.ps1 dev
        .\tasks.ps1 prep -Scene dev-clip

    Layout: Python lives in backend\, the React app in frontend\. The Python
    project root (pyproject.toml, uv.lock, .venv) stays at the repo root so
    there is one venv for the repo -- hence `--app-dir backend` below.
#>
param(
    [Parameter(Position = 0)][string]$Target = 'help',
    [string]$Scene
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Get-EnvValue($name, $fallback) {
    if (Test-Path .env) {
        $line = Select-String -Path .env -Pattern "^$name=" -ErrorAction SilentlyContinue |
                Select-Object -First 1
        if ($line) {
            $value = $line.Line.Split('=', 2)[1].Trim()
            if ($value) { return $value }
        }
    }
    return $fallback
}

$port = Get-EnvValue 'SERVER_PORT' '8000'

switch ($Target) {
    'setup' {
        uv sync --all-groups
        Push-Location frontend; pnpm install; Pop-Location
    }
    'dev' {
        Start-Process -FilePath 'uv' -ArgumentList @(
            'run', 'uvicorn', '--app-dir', 'backend', 'server.main:app', '--reload', '--port', $port
        )
        Push-Location frontend; pnpm dev; Pop-Location
    }
    'server' { uv run uvicorn --app-dir backend server.main:app --reload --port $port }
    'web'    { Push-Location frontend; pnpm dev; Pop-Location }
    'prep' {
        if (-not $Scene) { $Scene = Get-EnvValue 'ACTIVE_SCENE' $null }
        if (-not $Scene) { throw 'Scene is required: .\tasks.ps1 prep -Scene <scene_id>' }
        Push-Location backend
        try { uv run python -m prep.run_all --scene $Scene } finally { Pop-Location }
    }
    'test' {
        uv run pytest -q
        Push-Location frontend; pnpm test; Pop-Location
    }
    'lint' {
        uv run ruff check .
        Push-Location frontend; pnpm lint; Pop-Location
    }
    'check' { Invoke-RestMethod "http://127.0.0.1:$port/health" | ConvertTo-Json -Depth 5 }
    default {
        Write-Host @"
.\tasks.ps1 setup             install Python + Node dependencies
.\tasks.ps1 dev               run the API and the web app together
.\tasks.ps1 server            run the FastAPI backend only
.\tasks.ps1 web               run the Vite frontend only
.\tasks.ps1 prep -Scene <id>  run Scene Prep end to end for one scene
.\tasks.ps1 test              pytest + vitest
.\tasks.ps1 lint              ruff + tsc
.\tasks.ps1 check             health check against a running server
"@
    }
}
