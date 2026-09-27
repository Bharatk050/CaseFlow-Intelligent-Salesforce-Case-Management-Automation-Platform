# AI decision log

## 2026-09-15 — Initial triage application

- **Goal:** make an internal support queue easier to prioritize and process.
- **Decision:** use React + FastAPI with file-backed JSON tickets.
  - **Reason:** it keeps the first release local, transparent, and straightforward to inspect or extend.
- **Decision:** use deterministic triage rather than an external model.
  - **Reason:** routine cases can be handled consistently without credentials or model costs, while sensitive and uncertain requests remain under human control.
- **Decision:** use Markdown articles in `backend/data/CA/` as the routine-resolution source.
  - **Reason:** support staff can edit the guidance without changing application code.
- **Decision:** apply a dark operations-console interface.
  - **Reason:** this matches the requested command-center visual direction and makes urgency states easy to scan.

## 2026-09-15 — Salesforce queue and RAG integration

- **Goal:** import authorized Salesforce support-queue Cases, retrieve relevant help-center playbooks, and make the handling recommendation auditable.
- **Decision:** use Salesforce OAuth with a configurable Case SOQL query or Queue ID.
  - **Reason:** the org controls the exact queue path and fields while the app never stores secrets in source control.
- **Decision:** mirror Salesforce Cases to local ticket JSON files before triage.
  - **Reason:** it preserves a reviewable local working queue and avoids changing Salesforce during retrieval.
- **Decision:** retrieve ranked Markdown playbooks before categorization, while retaining deterministic escalation rules.
  - **Reason:** recommendations are grounded in the help center and sensitive, urgent, or low-confidence Cases remain human-only.
- **Decision:** disable Salesforce write-back by default and require an explicit per-ticket agent action.
  - **Reason:** Salesforce Case statuses vary by organization and external records should not be changed without approval.

## 2026-09-15 — Local Salesforce sync reliability

- **Goal:** allow the local browser UI to reach the Salesforce sync API and make configuration failures actionable.
- **Decision:** allow both standard Vite loopback origins (`localhost:5173` and `127.0.0.1:5173`) and report failed sync requests clearly.
  - **Reason:** the UI uses `127.0.0.1` by default, which was blocked by the API's origin policy; clear failures make an unavailable API or rejected Case query diagnosable without weakening OAuth or write-back safeguards.

## 2026-09-15 — OAuth-first Salesforce sync

- **Goal:** complete the authorized Salesforce login and Case import in one user flow.
- **Decision:** send an unconnected user to the OAuth authorization endpoint on sync, then import Cases automatically after the callback returns to the configured frontend URL.
  - **Reason:** authentication remains explicitly user-authorized while avoiding a second click after a successful login; no write-back behavior is changed.
- **Decision:** include the configured frontend callback origin in the API's CORS allowlist.
  - **Reason:** OAuth may return to a configured local development port other than the default, and the automatic post-login import must remain browser-accessible only from that explicit origin.

## 2026-09-15 — Agent-triggered RAG suggestions

- **Goal:** keep intake and Salesforce synchronization passive until an agent asks for handling guidance on an opened case.
- **Decision:** create and sync tickets with an untriaged, human-review state; run retrieval, deterministic safety evaluation, and any optional model assistance only through the explicit “Suggest me the approach” case action.
  - **Reason:** this gives the agent control over when case content is analyzed while preserving the existing escalation policy whenever a suggestion is requested.

## 2026-09-16 — Beta Excel ticket import

- **Goal:** allow safe test-data ingestion before a production source integration is available.
- **Decision:** accept up to 200 valid `.xlsx` rows with Subject, Customer, and Message columns, and store each row as a separate local ticket JSON in an untriaged human-review state.
  - **Reason:** it provides a bounded, explainable beta path without automatic RAG, automatic resolution, or external write-back.
- **Decision:** allow `localhost` and `127.0.0.1` browser origins on local development ports.
  - **Reason:** browsers treat the two loopback hostnames as distinct origins; allowing both prevents local Excel upload preflights from being blocked while keeping the exception restricted to loopback hosts.
- **Decision:** update the visible queue from a successful Excel-import response rather than requiring a second network refresh.
  - **Reason:** the import response already contains the saved tickets, so this avoids presenting a misleading upload failure if a later refresh request is interrupted.

## 2026-09-16 — Local API routing reliability

- **Goal:** make the browser UI consistently reach the local support API for Excel imports and other ticket actions.
- **Decision:** use the project’s fixed local backend address (`http://127.0.0.1:8012`) rather than reading a browser-side `VITE_API_URL` port.
  - **Reason:** an inherited or stale environment value pointed the frontend at port 8011 while the backend was running on 8012. A fixed project-local address removes that configuration mismatch and the Vite proxy configuration could not be loaded in this local environment.

## 2026-09-16 — Case-export Excel compatibility

- **Goal:** import the supplied Salesforce-style case workbook without forcing users to restructure it into a three-column template.
- **Decision:** treat `Account Name` as the customer field and construct a reviewable message from Case export fields when no description column is present; retain populated source columns in `imported_case_fields`.
  - **Reason:** the supplied workbook contains case metadata such as Case Number, Case Reason, Product, and Priority but no free-text message. Preserving it supports human review while keeping imported tickets untriaged.

## 2026-09-16 - Roster Support knowledge-base integration

- **Goal:** align ticket triage and retrieval with the supplied Roster Support operational playbooks.
- **Decision:** index both `.md` and `.md.txt` case files, map requests to documented Roster Support case types, and exclude router/reference documents from primary case-playbook recommendations.
  - **Reason:** the revised knowledge base is delivered as `.md.txt` files; the prior `*.md` scan ignored all of it.
- **Decision:** remove automated ticket resolution and require human review for every Roster Support recommendation.
  - **Reason:** the updated guardrails require Provisioning Notes, authorization, and confirmation before action, especially for destructive changes, and prohibit inventing missing internal procedures or URLs.

## 2026-09-16 - Playbook-grounded approach and priority

- **Goal:** provide a useful, reviewable handling recommendation only after an agent requests it for a case.
- **Decision:** derive a numbered suggested approach from the selected case playbook and use its documented risk, controlled actions, data sensitivity, owner, and missing-procedure markers to set priority, rationale, and escalation state.
  - **Reason:** this keeps categorization and priority explainable from the updated knowledge base while ensuring the application proposes rather than executes operational changes.

## 2026-09-17 - Metadata-aware Agentic RAG

- **Goal:** make suggested approaches more relevant, concise, and auditable for the case an agent opens.
- **Decision:** rank playbooks primarily by their declared aliases and case type, prefer the most specific router phrase over broad keyword matches, and extract only early actions from named procedure sections.
  - **Reason:** Roster Support playbooks share general words such as sync, account, and user; alias-aware ranking avoids selecting a plausible but incorrect procedure or a reference document.
- **Decision:** show the retrieved knowledge-base sources with each recommendation and stop/escalate when a selected playbook declares a missing procedure or a different owner.
  - **Reason:** agents can verify the basis for each suggestion, while incomplete documentation is never silently filled with invented instructions.

## 2026-09-19 - Agent-directed suggestion refinement and team attribution

- **Goal:** keep the CA knowledge-base recommendation stable by default while allowing an agent to request a targeted AI rewrite.
- **Decision:** only call optional model refinement when the agent supplies refinement notes; otherwise retain the deterministic CA-grounded suggestion unchanged.
  - **Reason:** this makes the original playbook guidance the dependable default and prevents silent changes to agent-facing recommendations.
- **Decision:** attribute suggestion requests and case edits to the locally selected team member and compute Team Performance from that activity history.
  - **Reason:** a local identity selector supports individual work tracking without introducing credentials or an unapproved external identity provider.

## 2026-09-19 - AI suggestion and advisory priority

- **Goal:** use the enabled model to make agent-requested handling suggestions more case-specific while preserving controlled queue behavior.
- **Decision:** call the model whenever a signed-in agent requests an approach, and save its playbook-grounded suggestion plus an advisory priority and rationale.
  - **Reason:** agents receive AI help even without entering optional notes, while notes can still guide a more specific rewrite.
- **Decision:** keep the CA/safety priority as the final priority used for queue colors, filters, and ordering; display the AI priority only as advice.
  - **Reason:** deterministic escalation and documented risk controls must not be silently overridden by a model assessment.

## 2026-09-20 - Salesforce OAuth and authorized Case sync

- **Goal:** let users authorize Salesforce through Salesforce's own login, then display and assign only Cases they are permitted to access.
- **Decision:** use Authorization Code Flow with PKCE, validated one-time state, encrypted server-side SQLite sessions, and an HTTP-only session cookie.
  - **Reason:** no Salesforce passwords or tokens are collected by the frontend, and each browser user has an isolated backend session.
- **Decision:** sync only the user-selected Roster Support Queue and keep local mirrors limited to the fields required by the Case dashboard.
  - **Reason:** it avoids broad Case retrieval while Salesforce remains the authority for every object and record permission.

## 2026-09-20 - Local Salesforce session configuration

- **Goal:** allow a completed Salesforce OAuth authorization to establish a secure local application session.
- **Decision:** configure the backend's Fernet session-encryption key in the local, untracked environment file.
  - **Reason:** the OAuth callback must encrypt the Salesforce token before it can create the HTTP-only browser session; without this key, authorization cannot be persisted.
- **Decision:** load the backend's project-local `.env` with override enabled.
  - **Reason:** an inherited empty environment variable otherwise takes precedence over the operator's local configuration and incorrectly leaves Salesforce unavailable after a restart.

## 2026-09-20 - HTTPS localhost Salesforce callback

- **Goal:** make local Salesforce OAuth compatible with the External Client App callback policy.
- **Decision:** run the RQC frontend and backend on HTTPS localhost and use `https://localhost:8012/auth/salesforce/callback` as the configured callback URL.
  - **Reason:** Salesforce rejects HTTP callback URLs for External Client Apps, while the registered HTTPS localhost callback keeps development local and exact-match OAuth validation intact.
- **Decision:** serve the built frontend from the HTTPS backend origin for local OAuth.
  - **Reason:** the callback and all authenticated browser requests then use one HTTPS first-party origin, so the HTTP-only Salesforce session cookie is available without cross-origin browser restrictions.
- **Decision:** request only the `api` and `id` OAuth scopes by default.
  - **Reason:** the current application does not exchange or use refresh tokens, so avoiding the unnecessary refresh-token scope reduces authorization-policy requirements while retaining the API and identity access used by the Case dashboard.

## 2026-09-27 - Review fixes and authenticated agent workflow

- **Goal:** enforce the Salesforce writeback policy and protect cached case data.
- **Decision:** require `SALESFORCE_ALLOW_WRITEBACK=true` for assignment; authenticate private endpoints with the existing Salesforce session, recheck Salesforce record visibility before returning or changing mirrors, and separate mirror filenames by instance.
  - **Reason:** a browser action alone must not bypass the writeback gate, and a shared disk cache must not bypass the current user's Salesforce permissions.
- **Decision:** associate new local tickets/imports with the authenticated user and instance. Preserve but hide historical unowned tickets; require explicit ownership migration before making them available. Replace caller-supplied team identities with the Salesforce session identity and scope activity summaries to the current user.
  - **Reason:** the previous identity header could be forged, and historical ownership cannot safely be inferred.
- **Goal:** enforce OAuth and session lifetimes.
- **Decision:** expire pending authorizations after ten minutes and server sessions after eight hours; fail closed for legacy sessions without expiration. Bind callbacks to an HTTP-only initiating-browser state cookie and consume state within a write transaction.
  - **Reason:** one-time state, browser binding, and server-side expiry prevent stale authorizations and sessions from remaining usable.
- **Goal:** restore agent-directed handling and explainable escalation.
- **Decision:** expose suggestions, retrieved playbooks, local status/owner/notes, and activity in the frontend; preserve existing local workflow status when guidance does not require escalation. Derive stable filters from the full authorized result set and use the serving origin by default.
  - **Reason:** backend capabilities need reviewable UI actions; requesting guidance should not silently reopen an in-progress or resolved ticket.
- **Decision:** recognize conduct word variants and explicitly escalate unknown or low-confidence matches, after consulting CA guardrails and escalation/routing guidance.
  - **Reason:** exact stems missed abusive reports, and uncertain routing must reach a human.
- **Decision:** align the OAuth scope regression test with the documented `api id` default and add mocked access-control, lifecycle, writeback, and workflow tests.
  - **Reason:** tests must verify the intended policy without using live accounts or altering Salesforce.
- **Decision:** mark private API responses `Cache-Control: no-store` and clear frontend case data after authentication failures.
  - **Reason:** private case responses should not persist in browser caches or remain displayed after an expired session is detected.
- **Validation:** 43 backend tests passed with synthetic tickets and mocked Salesforce calls; TypeScript checking and Vite production build passed. One installed Starlette/httpx deprecation warning remains. Browser interaction and live Salesforce OAuth were not exercised.
- **Operational note:** restart the backend and reconnect Salesforce; legacy server sessions without an expiry fail closed. Existing unowned imports remain untouched on disk and require explicit ownership assignment before display.

## 2026-09-27 - Restore independent Excel beta and diagnose OAuth approval

- **Goal:** keep beta workbook testing available while Salesforce login is unavailable.
- **Decision:** render Upload Excel BETA independently of Salesforce connection state and establish a separate loopback-only, HTTP-only, random browser session with an eight-hour server expiry. Imported tickets belong to that browser capability; local sessions cannot read or write Salesforce mirrors.
  - **Reason:** the previous review fix incorrectly hid Excel and required Salesforce authentication for the beta workflow. A separate local capability restores the workflow without opening shared tickets anonymously.
- **Decision:** reuse local browser sessions across reloads and retain beta imports when Salesforce is disconnected. Preserve historical unowned tickets without guessing their owner.
  - **Reason:** a failed external integration should not interrupt independent local testing or expose another user's data.
- **Goal:** make OAuth configuration and rejection handling accurate and reviewable.
- **Decision:** honor a validated SALESFORCE_LOGIN_URL for authorization and code exchange, supporting production, sandbox, and My Domain. Retain PKCE, state binding, least scopes, and disabled writeback.
  - **Reason:** hardcoding production ignored the configured endpoint and would prevent the correct org from being targeted when sandbox or My Domain is required.
- **Decision:** handle error callbacks without requiring a code; consume state and show fixed actionable messages. Add loopback-only credential-free diagnostics and an External Client App setup guide. Align .env.example with the running HTTPS callback.
  - **Reason:** OAuth rejection must not become a FastAPI missing-code error, leak provider response data, or be described as a confirmed local fix when org policy is unknown.
- **Finding:** the runtime still used an old uvicorn process on port 8012. Replaced the verified RQC process with the updated backend and kept access logging off to avoid logging OAuth query parameters.
- **Validation:** 56 backend tests passed; frontend production build passed. A real headless Edge session confirmed the beta button is visible/enabled without Salesforce, successfully uploaded a synthetic workbook, and retained the import after reload. Removed only that synthetic ticket after the check. HTTPS health and safe OAuth diagnostics passed.
- **Remaining external verification:** the user identified an External Client App. Its My Domain and Permitted Users policy are still needed; no Salesforce administrator settings were changed and no successful OAuth approval is claimed.

## 2026-09-27 - Target the user-confirmed Salesforce My Domain

- **Goal:** send OAuth authorization and token exchange to the org the user identified.
- **Decision:** set the local backend SALESFORCE_LOGIN_URL to https://dream-page-1540.my.salesforce.com, preserving callback, PKCE, scopes, credentials, and disabled writeback.
  - **Reason:** the user confirmed this My Domain; using it directly removes ambiguity from the generic production login endpoint. This configuration change alone does not prove Salesforce has approved the app.

## 2026-09-27 - Reliable backend startup on Windows

- **Finding:** starting a second uvicorn server reproduced WinError 10048 because the existing RQC process already owns port 8012. The existing server remained healthy. Logs also showed Windows Proactor transport cleanup WinError 10054 after client disconnects.
- **Goal:** provide a predictable startup command and avoid noisy Windows socket-cleanup exceptions.
- **Decision:** add backend/run.py with absolute project/certificate paths, dependency/TLS checks, a certificate-verified check for an already-running RQC server, and clear handling of occupied ports. Use asyncio.Runner with a Windows SelectorEventLoop for the single-process server, keeping access logging disabled.
  - **Reason:** users should not need a specific working directory or accidentally launch competing servers. The application does not require asynchronous subprocess support, and using a selector avoids the observed Proactor shutdown path without suppressing application exceptions.
- **Decision:** update CMD and the setup guide to use the launcher. Existing healthy servers are reported, not killed or silently restarted.
  - **Reason:** restarting a running process should remain an explicit action, and unrelated services must not be stopped.
- **Validation:** two real-process launcher tests passed: imports/TLS from the backend directory, HTTPS startup from another directory, and a second invocation correctly reusing the existing server. Restarted the verified RQC server with the launcher; certificate-verified HTTPS health returned 200, and another launch reported the existing server without WinError 10048.

## 2026-09-27 - Confirmed OAuth registration scope mismatch

- **Finding:** the user confirmed the External Client App selects only api, while live local diagnostics show the backend requests api id. The user also confirmed that its Consumer Key and callback match the backend.
- **Goal:** align Salesforce app authorization with the backend's required API and identity access.
- **Decision:** retain api id in the backend and document adding the identity URL service scope to the Salesforce registration. Do not remove identity lookup or relax PKCE to mask the mismatch.
  - **Reason:** the server uses the authenticated Salesforce user identity for attribution and assignment. The external registration must allow the requested scopes.
- **Decision:** isolate the default-login unit test from the developer's configured My Domain by explicitly setting its test login URL.
  - **Reason:** a valid local My Domain configuration should not change the test's expected default fixture endpoint.
- **Execution boundary:** no Salesforce admin connection is available and no Salesforce sessions are stored. The external scope change has been requested from the user, not applied or claimed complete. Real login, queue loading, and case synchronization remain pending that change and user authorization.
- **Validation:** all 58 backend tests passed, including mocked OAuth/PKCE, local Excel isolation, writeback controls, and real-process startup checks. Salesforce-side scope update and end-to-end approval are still unverified.


## 2026-09-27 - Support Operations visual redesign
- Goal: present the existing support workflow as a polished enterprise dashboard. Reason: the plain layout lacked hierarchy and clear action states. Added a navy/charcoal palette, restrained indigo accents, consistent controls and badges, SVG icons, elevated panels, and responsive layouts. Backend endpoints, OAuth, Salesforce permissions, case storage, and resolution logic remain unchanged.
- Goal: make requested guidance clear and reviewable. Reason: plain text obscured the relationship between the request and response. Added an analyzing state, animated muted-green guidance card, numbered-step presentation, source references, and a separate amber approval section using existing priority and approval language. Original guidance and safety text remain visible; this presentation does not authorize or execute actions. Existing saved suggestions remain available. AI labels distinguish model-refined responses from deterministic playbook guidance.
- Goal: improve day-to-day case review. Reason: agents need to distinguish selection, priority, metadata, and local changes quickly. Added selected-row emphasis, filter empty states, structured metadata, compact local tracking forms, and a dated activity timeline. Kept Excel import accessible independently of Salesforce. Summary counts derive from loaded tickets.
- Goal: keep interactions comfortable and accessible. Reason: guidance updates should not reset the detail panel. Retained detail component identity across activity updates, synchronized local fields with backend values, added keyboard focus styling and reduced-motion support, and increased small text after screenshot review.
- Validation: TypeScript/Vite production build passed. Browser checks exercised guidance loading/reveal/approval, playbook display, local-save payloads, search empty state, error recovery, and simulated Salesforce assignment/sync/disconnect. Responsive overflow checks covered 1024, 768, 390, and 320 pixel widths. Salesforce tests used browser fixtures and did not write to a live org.
- Final validation: the rebuilt UI passed the browser interaction and responsive checks. A real synthetic Excel workbook imported successfully through the local backend, remained after reload, and its test ticket was removed afterward; unrelated tickets were untouched.


## 2026-09-28 - Salesforce development connection and personal progress

- Goal: restore reliable Vite connection. Reason: the API was configured, but failed status checks left the frontend falsely unconfigured; development also mixed HTTP and HTTPS. Added HTTPS localhost Vite on fixed port 5173, explicit credentialed CORS origins, retryable readiness states, and an allowlisted OAuth return destination. Preserved the backend callback, PKCE, state binding, server-only secrets, and disabled writeback.
- Goal: retain progress across reconnects with the selected Salesforce-only identity. Reason: temporary beta sessions cannot establish permanent ownership. New signed-in imports and tickets now prefer the Salesforce session. Existing beta ownership remains unchanged and is labeled temporary; no history or ownership is guessed.
- Goal: count each explicit resolution as requested. Reason: edit counts do not identify completions. Non-resolved-to-resolved saves append timestamped actor/organization events to that ticket's JSON. Repeated resolved saves do not count; reopening permits another completion. Other workflows never generate credit.
- Goal: prevent duplicate concurrent credit and lost history. Reason: requests overlap even with one worker. Serialized ticket mutation paths and atomically replaced JSON files. Documented the single-process deployment constraint.
- Goal: provide private, explainable progress. Reason: counts must match the authenticated organization/user and current case visibility. Added no-store GET /me/progress, IANA timezone aggregation with tzdata for Windows, 7/30/90-day zero-filled counts, and accessible SVG/table presentation at #/progress. Disconnect and session failure clear private progress.
- Validation: 63 backend tests passed, covering concurrent saves, reopenings, reconnect persistence, isolation, revoked visibility, timezone boundaries, legacy exclusion, durable Excel ownership, CORS, and development OAuth return. TypeScript/Vite build and launcher import/TLS checks passed. Restarted the verified RQC backend and started HTTPS Vite; both returned 200 and the progress API is live.
- External verification: live Salesforce authorization, org approval, queues, and synchronization still require user sign-in. No Salesforce writes or administrator changes were performed.

- Browser validation: isolated headless Edge verified real HTTPS frontend/API access and the signed-out progress state. Synthetic API fixtures verified totals, 7/30/90-day chart ranges, error retry, accessible daily table, back navigation, disconnect clearing, and widths 1440/768/390/320. No live Salesforce session was created.


## 2026-09-28 - Salesforce display name and Roster support Queue list view

- Goal: identify the signed-in person by full name. Reason: raw Salesforce IDs are unsuitable display names. Capture OAuth identity display_name, migrate sessions with a nullable display-name column, and backfill older sessions using their authenticated User record. Use Salesforce user as a fallback. Header, My Activity, and new activity entries use this name; identity IDs and historical events are unchanged.
- Goal: retrieve the exact saved Case list view requested by the user. Reason: Roster support Queue is a Cases dropdown view, not a queue-owner filter. Discover accessible Case views, match the full label case-insensitively with trimmed whitespace, and reject ambiguous matches. Page through view results and hydrate workspace fields by ID while retaining view order. Restrict pagination URLs to the authenticated org.
- Goal: make retrieval outcomes accurate. Reason: missing views, empty views, and errors mean different things. Added authenticated POST /auth/salesforce/roster-support/sync with found/missing state, view, cases, count, and timestamp. UI shows No queue found, No cases, or a separate retryable error. HTTP 401/403 produce fixed reconnect/permission messages without provider details.
- Goal: load the view automatically after login and on reload. Reason: manual queue selection is no longer relevant. Replace the picker with the fixed view label and Refresh cases; coalesce concurrent refreshes, replace displayed Salesforce results, and retain separately labeled Excel cases. Preserve ticket JSON/history and legacy queue-sync endpoints. No automatic Salesforce writeback is added.

- Validation: full backend regression suite passed (69 tests); after final pagination/error handling adjustments, all 8 focused roster/name/error tests passed. TypeScript/Vite production build passed. Isolated headless Edge against the built site verified the full name, exactly one automatic sync, replacement of stale Salesforce results, missing/empty view messages, permission error and retry, Excel preservation, and 1440/768/390/320 widths using synthetic responses.
- Runtime: restarted the verified RQC launcher on https://localhost:8012; health returned 200 and OpenAPI exposes the new roster-support endpoint. No live Salesforce authorization or case retrieval was performed; actual org verification remains dependent on the user's sign-in. Existing Starlette/httpx deprecation warning is unchanged.


## 2026-09-28 - Prepare essential project files for Git

- Goal: version the application without publishing local secrets or customer data. Reason: the project had no Git repository or ignore rules. Initialized a main branch and added exclusions for environment credentials, TLS certificates/private keys, Salesforce session databases, support-ticket JSON, browser profiles, runtime artifacts, dependencies, generated builds, and caches. Retained safe environment examples and a support_files directory placeholder.
- Goal: make a fresh checkout understandable. Reason: ignored local configuration and TLS files must be supplied independently. Added a root README with installation, runtime, verification, and repository-content guidance; documented the confirmed CaseReason/Reason issue without applying the unapproved application fix.
- Publication boundary: the destination repository URL and visibility are pending. Internal CA playbooks need a restricted destination; no remote push has been performed.

- Destination confirmed: the user supplied the public, initially empty GitHub repository Bharatk050/CaseFlow-Intelligent-Salesforce-Case-Management-Automation-Platform. Excluded internal backend/data/CA playbooks from public version control and added private-provisioning documentation. Application source, synthetic tests, lockfile, environment examples, and project documentation are included; real tickets, sessions, TLS files, credentials, runtime profiles, and generated artifacts remain local.
- Pre-publication verification: explicit staged-file selection matched no populated local credential values or common private-key/token patterns. Verified ignore rules for environment, session database, private TLS key, ticket JSON, runtime logs, dependencies, and frontend build output. No application logic changes, including the pending Salesforce Reason-field correction, were made for Git preparation.
