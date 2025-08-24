.PHONY: db-upgrade test db-up

DB_URL?=postgresql+psycopg://postgres:postgres@localhost:5432/appdb

db-up:
	docker compose up -d

db-upgrade:
	DATABASE_URL=$(DB_URL) alembic upgrade head

test:
	pytest -q

