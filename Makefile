.PHONY: install data app test lint audit eval eval-final eval-visitor eval-heldout replay secrets business video screenshots

install:        ## install dependencies
	pip install -r requirements-dev.txt

data:           ## rebuild the synthetic bookings database (seeded, reproducible)
	python scripts/make_data.py

app:            ## run the staff web app
	streamlit run app.py

test:           ## unit tests with coverage
	python -m pytest -q --cov --cov-report=term-missing

lint:           ## lint and format check
	ruff check . && ruff format --check .

audit:          ## known vulnerabilities in dependencies
	pip-audit -r requirements.txt

eval:           ## one real run of the 40 labelled emails (uses the API, about $0.05)
	python -m eval.run_eval --set main --label dev --price-in 0.10 --price-out 0.50

eval-final:     ## final real run, 3 runs (uses the API)
	python -m eval.run_eval --set main --runs 3 --label final --price-in 0.10 --price-out 0.50

eval-visitor:   ## 10 visitor-style emails (uses the API)
	python -m eval.run_eval --set visitor --label final --price-in 0.10 --price-out 0.50

eval-heldout:   ## 8 held-out emails, run once (uses the API)
	python -m eval.run_eval --set heldout --label final --price-in 0.10 --price-out 0.50

replay:         ## re-score the recorded final run with the gates (free, what CI does)
	python -m eval.run_eval --replay eval/recorded/main-final.jsonl --gate --no-report

secrets:        ## build .streamlit/secrets.toml from .env (prints key names only)
	python scripts/make_secrets.py

business:       ## projected value, three scenarios
	python scripts/business_case.py --scenarios

video:          ## record the captioned demo video (no voice) from the live app
	python scripts/record_demo.py

screenshots:    ## README screenshots (app must be running)
	python scripts/capture_screenshots.py
