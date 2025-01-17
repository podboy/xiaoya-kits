MAKEFLAGS += --always-make

all: build reinstall test


clean-cover:
	rm -rf cover .coverage

clean-tox: clean-cover
	rm -rf .stestr .tox

clean: build-clean clean-tox


upgrade:
	pip3 install -i https://pypi.org/simple --upgrade xiaoya


upload:
	xpip-upload --config-file .pypirc dist/*


build-requirements:
	pip3 install -r requirements.txt xpip.build pylint flake8 pytest
build-clean:
	xpip-build --debug setup --clean
build: build-requirements build-clean
	xpip-build --debug setup --all

build-image:
	git checkout image
	git reset --hard origin/master
	git push -f origin image
	git checkout master

install:
	pip3 install dist/*.whl
uninstall:
	pip3 uninstall -y xiaoya
reinstall: uninstall
	pip3 install --force-reinstall --no-deps dist/*.whl


prepare-test:
	pip3 install --upgrade pylint flake8 pytest

pylint:
	pylint $$(git ls-files xiaoya/*.py test/*.py example/*.py)

flake8:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

pytest:
	pytest

test: prepare-test pylint flake8 pytest
