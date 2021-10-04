pytype:
	pytype --config pytype.cfg aliens4friends

test:
	python -m unittest discover aliens4friends/tests/

.PHONY: pytype test
