clean:
	rm -rf build dist pip-wheel-metadata .pytest_cache
	find . -regex ".*/__pycache__" -exec rm -rf {} +
	find . -regex ".*\.egg-info" -exec rm -rf {} +

install:
	pip install .

install-pip-setuptools:
	python -m pip install -U "pip>=19.1.1, <20.0" "setuptools>=41.0.1, <42.0" wheel

lint:
	isort
	pylint -j 0 --disable=unnecessary-pass kedro_docker
	pylint -j 0 --disable=missing-docstring,redefined-outer-name,no-self-use,invalid-name tests
	pylint -j 0 --disable=missing-docstring,no-name-in-module features
	flake8 kedro_docker tests features

test:
	pytest tests

e2e-tests:
	behave

package: clean install
	python setup.py clean --all
	python setup.py sdist bdist_wheel

legal:
	python tools/license_and_headers.py

install-pip-setuptools:
	python -m pip install -U "pip>=18.0, <19.0" "setuptools>=38.0, <39.0" wheel
