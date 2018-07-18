tests:
	pytest --cov src --cov-report term-missing --vcr-record-mode none
.PHONY: tests

publish:
	rm -rf dist
	./setup.py sdist bdist_wheel
	twine upload dist/*
.PHONY: publish
