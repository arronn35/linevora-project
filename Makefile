.PHONY: check test eval
check: test eval
	@command -v node >/dev/null && node --check src/linevora/web/app.js || echo "node not found, app.js check skipped"
test:
	.venv/bin/python -m pytest -q
eval:
	.venv/bin/python eval/run_eval.py --cases eval/cases --extractor scripted --min-score 0.8
