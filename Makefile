# SceneStealer task runner.
# Windows without make? Use the PowerShell equivalents: .\tasks.ps1 <target>

SCENE ?= $(shell grep -E '^ACTIVE_SCENE=' .env 2>/dev/null | cut -d= -f2)
UV    ?= uv
PNPM  ?= pnpm

.PHONY: help setup dev server web prep test lint check clean

help:
	@echo make setup            install Python + Node dependencies
	@echo make dev              run the API and the web app together
	@echo make server           run the FastAPI backend only
	@echo make web              run the Vite frontend only
	@echo make prep SCENE=ID      run Scene Prep end to end for one scene
	@echo make test             pytest + vitest
	@echo make lint             ruff + tsc
	@echo make check            health check against a running server

setup:
	$(UV) sync --all-groups
	cd web && $(PNPM) install

dev:
	$(UV) run uvicorn server.main:app --reload --port $${SERVER_PORT:-8000} & \
	cd web && $(PNPM) dev

server:
	$(UV) run uvicorn server.main:app --reload --port $${SERVER_PORT:-8000}

web:
	cd web && $(PNPM) dev

prep:
	@test -n "$(SCENE)" || (echo "SCENE is required: make prep SCENE=<scene_id>" && exit 1)
	$(UV) run python -m prep.run_all --scene $(SCENE)

test:
	$(UV) run pytest -q
	cd web && $(PNPM) test

lint:
	$(UV) run ruff check .
	cd web && $(PNPM) lint

check:
	curl -s http://127.0.0.1:$${SERVER_PORT:-8000}/health

clean:
	rm -rf data/tmp .pytest_cache .ruff_cache web/dist
