# Windows without make: run the python commands directly.
PY ?= python

.PHONY: setup day1 test pain all

setup:
	$(PY) -m pip install -r requirements.txt

day1:
	$(PY) -m scripts.run_day1

test:
	$(PY) -m pytest -q

pain:
	$(PY) -m scripts.pain_model

all: day1 test
