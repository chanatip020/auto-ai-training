# Convenience targets for the AI Auto Training Platform.
# Run `make help` to see what's available.

.DEFAULT_GOAL := help
.PHONY: help up down logs build dev prod migrate verify-db rebuild clean

help:
	@echo "Targets:"
	@echo "  make dev         Bring up the stack with hot reload (compose override)"
	@echo "  make prod        Bring up the stack in production mode"
	@echo "  make down        Stop the stack"
	@echo "  make logs        Tail logs for both services"
	@echo "  make migrate     Run alembic upgrade head against the running api"
	@echo "  make verify-db   Print schema status (tables + alembic head)"
	@echo "  make rebuild     Rebuild images from scratch"
	@echo "  make clean       Remove containers, volumes, and ./data"

dev:
	docker compose up --build

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
