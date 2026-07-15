.PHONY: install dev test lint replay docker-build docker-run

install:
	cd backend && python -m pip install -e ".[dev]"

dev:
	cd backend && uvicorn app.main:app --reload

test:
	cd backend && python -m pytest

lint:
	cd backend && python -m ruff check . --no-cache

replay:
	cd backend && python -m app.cli run-replay argentina_france_no_score_sharp_move --speed 30 --reset-database

docker-build:
	docker build -t txline-sentinel-backend ./backend

docker-run:
	docker compose up --build
