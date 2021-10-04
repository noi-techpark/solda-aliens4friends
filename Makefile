# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

pytype:
	pytype --config pytype.cfg aliens4friends

test:
	python -m unittest discover aliens4friends/tests/

.PHONY: pytype test
