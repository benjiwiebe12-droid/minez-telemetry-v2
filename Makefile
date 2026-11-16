.PHONY: up down install reset-db load live worker api test

PYTHON := python3
PIP    := $(PYTHON) -m pip

up:
	docker compose up -d --wait

down:
	docker compose down -v

install:
	$(PIP) install -r requirements.txt

reset-db:
	docker compose exec postgres psql -U minez -d minez -f /docker-entrypoint-initdb.d/02_schema.sql

load:
	$(PYTHON) -m generator.stream --load data/sample.jsonl

live:
	$(PYTHON) -m generator.stream --live data/sample.jsonl

worker:
	$(PYTHON) -m app.worker

api:
	uvicorn app.api:app --reload --port 8000

test:
	pytest -q
