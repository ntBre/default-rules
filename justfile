fmt *args:
    ruff check --select I --fix {{args}}
    ruff format {{args}}

lint *args:
	ruff check {{args}}
