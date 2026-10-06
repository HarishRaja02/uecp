install:
	python -m pip install -r requirements.txt
keys:
	bash scripts/generate_keys.sh
seed:
	PYTHONPATH=backend python backend/seed.py
api:
	PYTHONPATH=backend python backend/app/main.py
test:
	PYTHONPATH=backend pytest -q
frontend:
	cd frontend && npm install && npm run dev
frontend-build:
	cd frontend && npm install && npm run build
security:
	PYTHONPATH=backend bandit -r backend/app -q
