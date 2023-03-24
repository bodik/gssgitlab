.PHONY: all venv install-deps freeze lint test coverage

all: lint coverage

venv:
	apt-get -y install python3-venv
	python3 -m venv venv

install-deps:
	pip install -r requirements-dev.lock

freeze:
	@pip freeze | grep -v '^pkg-resources='

lint:
	python -m flake8 gssgitlab.py tests
	python -m pylint gssgitlab.py tests

test:
	python -m pytest -v

coverage:
	coverage run --source gssgitlab -m pytest tests -x -vv
	coverage report --show-missing --fail-under 100
