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

## Description-based suggestions

Excel imports accept `Description`, `Case Description`, `Message`, or `Details`
(in that order, using the first nonblank value in each row). Headers ignore case,
extra whitespace and underscores. Descriptions retain line breaks and support up
to 32,000 characters. Older exports without descriptions still import, but require
clarification rather than using metadata as customer-written text.

Salesforce queue and list-view reads request `Description` and the standard `Reason`
field. A changed subject or description clears obsolete suggestions while preserving
agent notes, status and activity. OAuth permissions and explicit writeback controls
still apply.

Select **Suggest me the approach** to retrieve procedure sections and generate
handling steps, a case interpretation, missing details, and a customer reply draft.
The complete description determines whether guidance is a direct answer, ordered
agent steps, both, or a clarification request. Guidance shows up to four primary
bullets; expand remaining steps and review required checks before acting. Retrieval
and source validation run internally; source names and IDs are not shown. Customer drafts use
short bullets or customer-performable steps and must be reviewed before sending;
Copy draft preserves the exact text. Unavailable or invalid model output displays
safe clarification and human-review steps rather than an unvalidated customer reply.
The backend uses the existing `GEMINI_MODEL` when `ENABLE_GEMINI_TRIAGE=true` and
`GEMINI_API_KEY` is configured. Set these only in `backend/.env`. The complete case
description, agent refinement notes and relevant private playbooks are sent to that
configured service; use the organization's authorized configuration.
The backend uses Google's `google-genai` SDK with stateless Gemini Interactions
requests (`store=false`). The default model is `gemini-3.8-flash`. Set the key and
enable flag in the server-side environment, then restart `python backend/run.py`.
Generation stays disabled until a Gemini key is configured. Old OpenAI settings
are ignored; generation does not fall back to another provider.

Model output uses validated source identifiers and retains server-enforced safety
constraints. A disabled/unavailable model, refusal, or invalid response falls back
to local guidance. Internal citations identify supplied evidence; they do not replace
employee verification of the recommendation. Reply drafts are never sent automatically.


Local vector retrieval: install `backend/requirements.txt`, then run `python backend/prepare_vectors.py` once to download the public MiniLM embedding model and build FAISS. Private playbooks are embedded locally; only retrieved evidence is sent to the configured Gemini generation service. Index files live in ignored `.runtime/faiss/` and rebuild when active playbooks change. Set `ENABLE_FAISS=false` for deterministic lexical-only tests. Missing local model/dependencies use labeled lexical fallback. `/health` includes the startup build fingerprint; restart `python backend/run.py` after backend edits.
