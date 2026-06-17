# Repo-level lint + smoke-test targets. Run from the repo root.
.PHONY: lint lint-citation lint-paper smoke help

help:
	@echo "make lint            run all lint checks"
	@echo "make lint-citation   fail if CITATION.cff still has literal TODO placeholders"
	@echo "make lint-paper      build the paper once (cd paper && make)"
	@echo "make smoke           run analysis scripts as a release smoke test"

# Fails CI if CITATION.cff has TODO inside a quoted VALUE 
lint-citation:
	@if grep -nE '"[^"]*TODO[^"]*"' CITATION.cff; then \
	  echo "FAIL: CITATION.cff has a TODO inside a quoted value." 1>&2; \
	  exit 1; \
	else \
	  echo "OK: CITATION.cff has no TODO values (inline # TODO comments are allowed)."; \
	fi

lint-paper:
	$(MAKE) -C paper all

smoke:
	python3 analysis/paper_breakdown.py > /dev/null
	python3 analysis/stats.py > /dev/null
	@echo "OK: analysis scripts ran cleanly."

lint: lint-citation
