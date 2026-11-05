# Mismatch Desk

## Product and engineering rules
- Build a focused invoice exception review workflow for small distributors and manufacturers.
- Use AI for extraction, candidate matching, and grounded explanations; use deterministic Python rules for arithmetic and business decisions.
- Never authorize payments or silently resolve discrepancies. Human decisions must be explicit and auditable.
- Keep the Python API typed, small, and testable. Use LangGraph for meaningful workflow state and review pauses, not as decoration.
- Use synthetic fixtures only. Never commit credentials, employer data, or real invoices.
- Prefer small changes with clear acceptance criteria. Update README when behavior or setup changes.

## Commands
- Backend setup: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'`
- Run API: `cd backend && uvicorn mismatch_desk.main:app --reload`
- Run checks: `cd backend && pytest`
