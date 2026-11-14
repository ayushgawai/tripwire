.PHONY: venv backend test smoke

venv:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt

backend:
	.venv/bin/uvicorn backend.app:app --reload --port 8000

test:
	.venv/bin/pytest -q backend

smoke:
	.venv/bin/python demo/smoke.py
