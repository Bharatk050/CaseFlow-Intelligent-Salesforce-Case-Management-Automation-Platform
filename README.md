# Support Operations

React/TypeScript agent workspace with a FastAPI backend, Salesforce OAuth,
Case list-view retrieval, Excel imports, playbook guidance, and resolution progress.

## Local setup

1. Install Python 3.11+ and a Node.js version supported by the installed Vite release.
2. Create a Python virtual environment and install `backend/requirements.txt`.
   For tests, also install `pytest` and `httpx`.
3. Run `npm ci` in `frontend`.
4. Copy `backend/.env.example` to `backend/.env` and configure OAuth and the
   session encryption key. Never commit the populated environment file.
5. Provide a trusted localhost TLS certificate and its private key at
   `backend/.certs/localhost-cert.pem` and `backend/.certs/localhost-key.pem`.
   These machine-specific files are intentionally excluded from Git.
6. Privately provision the authorized Markdown playbooks in `backend/data/CA/`.
   These internal documents are excluded from this public repository; see
   [knowledge-base setup](backend/data/README.md). Playbook-dependent tests require
   these files to be present locally.
7. Run `npm run build` in `frontend`, then `python backend/run.py` from the root.
   Open **https://localhost:8012**.

For frontend development, run `npm run dev` in `frontend` and open
**https://localhost:5173** while the backend is running.

See [Salesforce setup](backend/SALESFORCE_SETUP.md) for callback, scopes, and
list-view behavior. Case updates to Salesforce require an explicit agent action
and `SALESFORCE_ALLOW_WRITEBACK=true`; the default is disabled.

## Checks

- Backend: `python -m pytest backend/tests -q`
- Frontend: `npm run build` from `frontend`

## Repository contents and local data

Commit application source, tests, dependency manifests and the npm lockfile,
sanitized environment examples, project rules, and documentation.
Do not commit `.env`, TLS material, Salesforce session databases, ticket JSON,
browser profiles, logs, screenshots, dependencies, generated builds, or caches.
The empty `backend/support_files/` directory is preserved with `.gitkeep`.

## Known issue

The current Salesforce case-detail query uses `CaseReason`, but the tested org
exposes the API field as `Reason`. Read-only diagnostics confirmed that replacing
the query field and its backend mapping resolves the request failure. That code
change has not been applied, per the user's instruction.
