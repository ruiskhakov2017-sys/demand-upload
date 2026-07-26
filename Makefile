.PHONY: up down logs migrate test api-test frontend-build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose run --rm api alembic upgrade head

test:
	docker compose run --rm api pytest

api-test:
	cd backend && pytest

frontend-build:
	cd frontend && npm run build

