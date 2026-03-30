VENV   := aiqa
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

.PHONY: install ingest clean setup

install:
	python3 -m venv $(VENV)
	$(PIP) install torch --index-url https://download.pytorch.org/whl/cpu
	$(PIP) install -r requirements.txt

ingest:
	$(PYTHON) ingest.py --clean

clean:
	rm -rf $(VENV) data/chroma/ __pycache__ .pytest_cache

setup: install ingest
