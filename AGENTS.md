# Codex agent instructions — Mobility Lab

Read README.md, docs/PROJECT_SPEC.md, docs/CODEX_HANDOFF.md and docs/PRIVACY.md before making changes.

## Non-negotiable rules
- **Incremental changes only**. Do not recreate the repository or replace working modules. Preserve existing APIs, UI, historical demo rows and tests.
- Never incorporate actual research participants, live patient/GPS data, protected health information, device OAuth tokens, secrets, employer/customer material or individual names. Synthetic demo ONLY until a separately designed and authorized secure research deployment.
- Do not rename an implemented feature as a more advanced method (e.g. current anchor-radius dwell detection is NOT DBSCAN).
- Ask for approval before adding any actual third-party credentials, background jobs, cloud deployment, paid APIs, or new public endpoints exposing data.
- No generated .venv, runtime *.db, .env or caches in commits or delivery zips.
- Every new API/algorithm needs tests; run `python -m pytest -q` (after `pip install -r requirements-dev.txt`).
- Preserve the currently documented API contract, add an explicit migration when altering schema, and verify backward compatibility.
- Report changes, test results, remaining risks, screenshots only if actually captured, and exactly how to start on Windows.

## Work sequence
1. Inspect repo + git status, read docs, run baseline tests.
2. Pick first incomplete P0 task from docs/CODEX_HANDOFF.md.
3. Implement smallest complete vertical slice with tests.
4. Verify API, browser UI, import/rejection, and data isolation from any real samples.
5. Update README/architecture and record what is implemented vs planned.
