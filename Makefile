tests:
	pytest --cov src --cov-report term-missing --vcr-record-mode none
.PHONY: tests
