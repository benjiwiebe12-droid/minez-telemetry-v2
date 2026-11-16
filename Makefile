.PHONY: up down install reset-db sample worker api test

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

sample:
	$(PYTHON) generator/generate.py --sample --out data/sample.jsonl

load:
	$(PYTHON) generator/generate.py --load data/sample.jsonl

live:
	$(PYTHON) generator/generate.py --live

worker:
	$(PYTHON) -m app.worker

api:
	uvicorn app.api:app --reload --port 8000

test:
	pytest -q
