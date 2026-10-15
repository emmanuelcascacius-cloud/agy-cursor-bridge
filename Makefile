.PHONY: install test lint check serve tunnel clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

check:
	agy-cursor check

models:
	agy-cursor models

serve:
	agy-cursor serve --port 8000

tunnel:
	agy-cursor serve --port 8000 --tunnel

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
