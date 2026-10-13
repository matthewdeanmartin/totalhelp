.EXPORT_ALL_VARIABLES:
# Get changed files

FILES := $(wildcard **/*.py)

# if you wrap everything in uv run, it runs slower.
ifeq ($(origin VIRTUAL_ENV),undefined)
    VENV := uv run
else
    VENV :=
endif

uv.lock: pyproject.toml
	@echo "Installing dependencies"
	@uv sync --all-extras

clean-pyc:
	@echo "Removing compiled files"


clean-test:
	@echo "Removing coverage data"
	@rm -f .coverage || true
	@rm -f .coverage.* || true

clean: clean-pyc clean-test

# tests can't be expected to pass if dependencies aren't installed.
# tests are often slow and linting is fast, so run tests on linted code.
test: clean uv.lock
	@echo "Running unit tests"
	# $(VENV) pytest --doctest-modules totalhelp
	# $(VENV) python -m unittest discover
	$(VENV) pytest test -vv -n 2 --cov=totalhelp --cov-report=html --cov-fail-under 48 --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy --timeout=5 --session-timeout=600
	$(VENV) bash ./scripts/basic_checks.sh
#	$(VENV) bash basic_test_with_logging.sh



isort:
	@echo "Formatting imports"
	$(VENV) isort .

.PHONY: isort

black: isort
	@echo "Formatting code"
	$(VENV) metametameta pep621
	$(VENV) black totalhelp # --exclude .venv
	$(VENV) black test # --exclude .venv
	$(VENV) git2md totalhelp --ignore __init__.py __pycache__ --output SOURCE.md

.PHONY: black

pre-commit: isort black
	@echo "Pre-commit checks"
	$(VENV) pre-commit run --all-files

.PHONY: pre-commit

bandit:
	@echo "Security checks"
	$(VENV)  bandit totalhelp -r --quiet

.PHONY: bandit

.PHONY: pylint
pylint: isort black
	@echo "Linting with pylint"
	$(VENV) ruff check --fix
	# pylint never actually ran here while targets were stamp files; this is today's score, ratchet it up.
	$(VENV) pylint totalhelp --fail-under 9.5

# for when using -j (jobs, run in parallel)
.NOTPARALLEL: isort black

check: mypy test pylint bandit check-dist

#.PHONY: publish_test
#publish_test:
#	rm -rf dist && poetry version minor && poetry build && twine upload -r testpypi dist/*

.PHONY: publish
publish: test
	rm -rf dist && hatch build

.PHONY: mypy
mypy:
	$(VENV) echo $$PYTHONPATH
	$(VENV) mypy totalhelp --ignore-missing-imports --check-untyped-defs


check_docs:
	$(VENV) interrogate totalhelp --verbose  --fail-under 70
	$(VENV) pydoctest --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse"

make_docs:
	pdoc totalhelp --html -o docs --force

check_md:
	$(VENV) linkcheckMarkdown README.md
	$(VENV) markdownlint README.md --config .markdownlintrc
	$(VENV) mdformat README.md docs/*.md


check_spelling:
	$(VENV) pylint totalhelp --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) pylint docs --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) codespell README.md --ignore-words=private_dictionary.txt
	$(VENV) codespell totalhelp --ignore-words=private_dictionary.txt
	$(VENV) codespell docs --ignore-words=private_dictionary.txt

check_changelog:
	# pipx install keepachangelog-manager
	$(VENV) kaclm validate

check_all_docs: check_docs check_md check_spelling check_changelog

check_self:
	# Can it verify itself?
	$(VENV) ./scripts/dog_food.sh

#audit:
#	# $(VENV) python -m totalhelp audit
#	$(VENV) tool_audit single totalhelp --version=">=2.0.0"

# ── Dogfooding targets (independent, not wired into check) ───────────────────

.PHONY: version-check
version-check:
	@uv run jiggle_version check

.PHONY: dev-status
dev-status:
	@uv run troml-dev-status validate .

.PHONY: prerelease-check
prerelease-check: version-check dev-status
	@echo "Pre-release checks passed."

.PHONY: dont-be-lazy
dont-be-lazy:
	@uv run dont_be_lazy --root . --no-color summary
	@uv run dont_be_lazy --root . --no-color scan totalhelp --no-config-suppressions || true

.PHONY: pydoc-docs
pydoc-docs:
	@uv run pydoc_fork totalhelp -o ./pydoc/

# ── Distribution verification ────────────────────────────────────────────────

.PHONY: check-dist
check-dist:
	@echo "Building and verifying distributions"
	@rm -rf .build
	@uv build --out-dir .build
	@$(VENV) python scripts/verify_distribution.py .build

# ── Python 3.15 trial environment ────────────────────────────────────────────
# Kept separate from .venv so the normal dev environment is never clobbered.
# NOTE: do not use $(CURDIR) in PATH here -- on Windows it expands to a
# drive-lettered path (C:/github/totalhelp) whose colon silently splits PATH.

PY315     := 3.15.0rc2
VENV315   := .venv315rc2
PY315_EXE := $(VENV315)/Scripts/python.exe

.PHONY: venv315
venv315:
	@test -x $(PY315_EXE) || uv venv $(VENV315) --python $(PY315)
	@uv pip install -e . pytest pytest-cov pytest-mock pytest-timeout pytest-xdist 		--python $(PY315_EXE) --quiet
	@$(PY315_EXE) --version

.PHONY: venv315-clean
venv315-clean:
	@rm -rf $(VENV315)

.PHONY: test315
test315: venv315
	@echo "Running unit tests on Python 3.15"
	@$(PY315_EXE) -m pytest test -q --timeout=60 -p no:randomly

.PHONY: check315
check315: test315
	@echo "Import audit on Python 3.15 (warnings are errors)"
	@$(PY315_EXE) -W error -c "import totalhelp, totalhelp.__main__, totalhelp.library, totalhelp.parser, totalhelp.ui, totalhelp.external"
	@echo "Python 3.15 checks passed."

# `test` is also a directory in this repo; without .PHONY make can call the target up to date and skip it.
.PHONY: test
