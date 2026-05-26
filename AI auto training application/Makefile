# Convenience targets for the AI Auto Training Platform.
# Run `make help` to see what's available.

.DEFAULT_GOAL := help
.PHONY: help up down logs build dev prod migrate verify-db rebuild clean \
        test test-backend test-frontend lint lint-backend lint-frontend ci \
        install-training mock-on mock-off

help:
	@echo "Targets (compose):"
	@echo "  make dev             Bring up db + api + web with hot reload (compose override)"
	@echo "  make prod            Bring up db + api + web in production mode"
	@echo "  make up              Alias for 'make dev' — the one-command start"
	@echo "  make down            Stop the stack"
	@echo "  make logs            Tail logs for all services"
	@echo "  make migrate         Run alembic upgrade head against the running api"
	@echo "  make verify-db       Print schema status (tables + alembic head)"
	@echo "  make rebuild         Rebuild images from scratch"
	@echo "  make clean           Remove containers, volumes (incl. db), and ./data"
	@echo ""
	@echo "  Self-contained — boots Postgres 16 inside docker by default."
	@echo "  Use Supabase/etc. by setting DATABASE_URL in the project-root .env."
	@echo ""
	@echo "Targets (tests / lint):"
	@echo "  make test            Run backend + frontend test suites"
	@echo "  make test-backend    pytest tests/unit"
	@echo "  make test-frontend   vitest run"
	@echo "  make lint            ruff + tsc"
	@echo "  make lint-backend    ruff check"
	@echo "  make lint-frontend   tsc --noEmit"
	@echo "  make ci              Lint + tests (what CI runs)"
	@echo ""
	@echo "Targets (training engine):"
	@echo "  make install-training Install ultralytics + torch into the running api container"
	@echo "  make mock-on         Switch the api to TRAINING_MOCK=1 (no real training)"
	@echo "  make mock-off        Disable TRAINING_MOCK and restart"

# ---- compose ----
dev:
	docker compose up --build

# Convenience alias so newcomers can just type `make up`.
up: dev

prod:
	docker compose -f docker-compose.yml up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose exec api alembic upgrade head

verify-db:
	docker compose exec api python scripts/verify_db.py

rebuild:
	docker compose build --no-cache

clean:
	docker compose down -v
	rm -rf data

# ---- tests ----
test: test-backend test-frontend

test-backend:
	cd backend && pytest tests/unit -q

test-frontend:
	cd frontend && npm test --silent

# ---- lint ----
lint: lint-backend lint-frontend

lint-backend:
	cd backend && ruff check app tests

lint-frontend:
	cd frontend && npm run lint

# What CI runs locally
ci: lint test

# ---- training engine helpers ----
install-training:
	@echo "Installing ultralytics into the running api container (~2 GB, takes 3-5 min)..."
	docker compose exec api pip install --no-cache-dir ultralytics torch
	@echo "Done. Real training is now enabled until the container is rebuilt."

mock-on:
	docker compose exec api sh -c 'echo "TRAINING_MOCK=1 enabled for this session"; export TRAINING_MOCK=1' || true
	@echo "NOTE: TRAINING_MOCK is read at process start. To make it stick:"
	@echo "  1) add  TRAINING_MOCK=1  to backend/.env"
	@echo "  2) make down && make dev"

mock-off:
	@echo "Remove TRAINING_MOCK from backend/.env, then: make down && make dev"
