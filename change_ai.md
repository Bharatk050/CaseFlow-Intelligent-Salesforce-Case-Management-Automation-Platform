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

## 2026-09-29 - Description-driven knowledge-base guidance

- Goal: make the private knowledge base consistent and usable for retrieval. Reason: duplicate and additional files competed with canonical procedures, and supporting references were treated as resolutions. Consolidated 35 source files into 24 active documents under cases/, reference/, and reference/sync-sources/; retained README and the router at the root. Preserved original files in the private, retrieval-excluded _archive/before-description-rag directory. Added document types, required-context metadata, description intake and reply boundaries; normalized names and internal root-relative references. Kept all private content excluded from Git.
- Goal: preserve procedural meaning during cleanup. Reason: newer documents contain valid source-specific branches while other branches, links and templates remain unavailable. Merged the newer material, retained the non-Clever missing-procedure marker and its link-registry entry, recorded source conflicts in open questions, ordered the account-size check before modeling, scoped the bulk-count rule to the documented actions, and removed wording that would falsely imply an unsent password reset had been sent. No missing procedure, URL or required template was invented.
- Goal: ground suggestions in the full description. Reason: broad subject/router keywords and extraction of the first three steps could select the wrong workflow. Added local BM25 section retrieval, normalized alias matching, explicit reference types, complete primary procedure branches, relevant supporting sections and mandatory guardrails. Description evidence has precedence; generic unsupported requests escalate. Source references include section identifiers and legacy filename aliases. No hosted vector database or new model provider was added.
- Goal: provide useful, reviewable drafts with server-enforced boundaries. Reason: agents need a case interpretation, supported next steps, missing details and a customer response without claiming actions were completed. Extended the existing OpenAI Responses integration with validated structured output and per-step/reply source identifiers. Validate citations and URLs, reject detectable internal-only reply content and unverified completion claims, retain deterministic escalation/authorization constraints, and handle refusal, incomplete output and failures with labeled local fallback. Return only safe error categories, including rate-limit/quota failures; provider payloads are never logged or returned. Existing server-side model configuration and store=False remain in use.
- Goal: ensure descriptions reach the same pipeline from both intake sources. Reason: Excel previously preferred Message and substituted metadata, and Salesforce could retain obsolete guidance after a description changed. Excel now selects the first nonblank Description, Case Description, Message or Details per row, normalizes headers, preserves line breaks, accepts up to 32,000 characters and flags missing descriptions separately from metadata. Salesforce preserves full Description and invalidates generated fields when Subject/Description change, preserving agent status, notes and history. Each ticket remains a separate JSON file.
- Goal: unblock the requested Salesforce read mapping. Reason: the previously documented CaseReason query field is invalid for the tested org. Under the current mapping implementation request, corrected queue and list-view hydration to use standard Reason and Description; preserved legacy CaseReason payload compatibility. This resolves the earlier Git-preparation-only deferral without adding automatic writes or changing OAuth controls. Salesforce's published Case example also uses Reason and Description: https://developer.salesforce.com/blogs/2024/06/using-prompt-builder-flows-and-apex-to-summarize-and-classify-cases-faster
- Goal: keep the agent workflow clear. Reason: generated suggestions must be reviewed alongside the actual description and evidence. Added case interpretation, missing details, a separately labeled copyable draft, section-based source previews, old-source alias support and stale-guidance messaging. Local fallback drafts are labeled separately from model-generated drafts. Replies are not sent and Salesforce is not written automatically.
- Validation: 110 backend tests passed, including description mapping/length/precedence, recursive private-document/link integrity, description-led routing, multiple issues, source-specific procedures, bulk-count boundary, guardrails, model citation/URL/refusal/failure boundaries, Salesforce refresh preservation and existing OAuth/access/workflow tests. TypeScript/Vite production build passed. Isolated headless Edge with synthetic responses passed description, loading, interpretation, missing details, draft copying, cited-section/legacy-alias preview and responsive widths 1440/768/390/320. The existing Starlette/httpx deprecation warning remains.
- External verification: the local OpenAI key and enabled flag are present (values were not exposed or changed). One synthetic-case live smoke reached OpenAI but received RateLimitError; a live generated response could not be verified. The UI now reports a safe rate-limit/quota explanation while retaining fallback guidance. No real tickets were sent for testing and no live Salesforce reads or writes were performed.


## 2026-09-29 ? Description evidence, local vectors, and Salesforce loading
- Goal: replace repeated clarification with useful grounded answers. Added explicit answer/procedure/mixed/clarification model responses, source validation, bullet rendering, and verbatim agent evidence when generation is unavailable. Customer drafting availability is explicit; no inferred customer-safe fallback is sent.
- Goal: improve recall across long descriptions. Added local MiniLM CPU embeddings and normalized FAISS inner-product search, token-window queries, lexical/vector reciprocal-rank fusion, content-addressed index and JSON metadata under ignored `.runtime/faiss`. Retrieved sections retain complete branch conditions and tables. Requests use cached models only and label lexical fallback. Archives and ticket files are excluded.
- Goal: load Salesforce cases reliably without widening access. Retained corrected Reason/Description mapping, added Case describe-based optional-field selection and explicit required Description access, fixed safe provider errors, and separated Excel refresh from Salesforce session failures. OAuth and explicit writeback restrictions remain enforced.
- Goal: make deployment and service failures diagnosable. Added startup build fingerprint to health and separate quota/rate-limit errors; retries exclude exhausted quota. Existing safety gates remain authoritative.

Validation: 115 backend tests passed; production frontend build passed; isolated headless browser checks passed for description, loading, interpretation, reply copy, cited source/legacy aliases and responsive widths. MiniLM downloaded successfully; FAISS built from 24 active documents and returned matches for a synthetic role question. Verified and restarted RQC PID 22852 as PID 23264; live health build 375388832cfe matches disk and the live schema accepts 32000-character descriptions. Synthetic live OpenAI generation returned APIConnectionError, so live generation remains unverified. Existing Salesforce sessions were expired; fresh user OAuth is needed to verify org-specific loading.


## 2026-09-30 ? Explicit Salesforce Save
Goal: agent Save writes Salesforce cases directly. Added an authorized save endpoint, Salesforce status choices and user/queue IDs, internal Case Comments, and all-or-none composite writes. Local mirrors and audit entries update only after provider success. Unchanged notes are not posted repeatedly. Excel remains local. Enabled the local SALESFORCE_ALLOW_WRITEBACK setting under the user?s explicit instruction; no customer email or automatic AI writeback was added. Salesforce rejects record-type and validation-rule violations. Consulted the case-management playbook and official Composite request documentation. Also corrected a variable typo in the legacy queue sync path.

Validation: 118 backend tests passed, then 3 targeted save tests passed after final error-handling adjustment; frontend production build passed. Restarted verified backend as PID 19444 and checked live build, save route, and enabled writeback via diagnostics. Salesforce calls were mocked in tests; no customer case was changed as a test. Owner access and record-type validation remain enforced by Salesforce. Case Comments are explicitly unpublished as required by the playbook; it recommends Chatter Post as an alternative.

## 2026-09-30 - Concise description-driven answers and procedures

- Goal: make guidance readable and followable by a beginner. Reason: fallback guidance exposed entire playbook excerpts and model steps permitted long narrative text. Prompt the existing configured model to distinguish answer, procedure, mixed and clarification intent from the entire description; use plain language, one action/fact per bullet, a short summary, and preserve every necessary condition and approval. Target 3-6 primary bullets; validate each guidance bullet at 60 words maximum, with up to 40 ordered steps so brevity does not remove required work.
- Goal: retrieve applicable knowledge-base evidence instead of unrelated similar procedures. Reason: hybrid results were appended without sufficient topic corroboration. Retain lexical/FAISS retrieval, require explicit aliases/title corroboration for additional case playbooks, require topic or definition overlap for references, exclude incompatible documented Clever and password-reset SSO branches, and keep whole applicable branch evidence plus guardrails. Support single-term glossary questions and skip unverified glossary rows in fallback excerpts. Consulted the local guardrails, link registry, password-reset, syncing-admin-behavior, Clever, glossary, and support-routing documents. No knowledge-base wording or resolution policy was rewritten.
- Goal: separate agent actions from customer-ready wording. Reason: internal operations must not become customer instructions. Add cited answer_bullets, agent_steps and evidence_details while preserving legacy response fields. Require topic evidence for factual answers, reject unsupported citations/URLs, internal citations in replies, overly long output, unverified completion claims and Soft SSO self-reset instructions. Customer drafts are concise bulleted answers or numbered customer-performable steps; agent review remains required. These checks verify structure and provenance, not semantic correctness. Model failures show short verbatim evidence and full expandable conditions, with customer drafting unavailable.
- Goal: show concise guidance without hiding requirements. Reason: long excerpts and reasoning obscured the next action. Show six primary bullets, expandable remaining steps, separately visible required checks and blocking questions, collapsed evidence/reasoning, and a readable customer reply with exact text available for copying. Preserve numbered customer instructions and clipboard text. Clear new structured fields and response type when a Salesforce description changes; preserve workflow/history and unrelated ticket files. Existing tickets remain compatible; automatic sending and Salesforce writeback behavior are unchanged.
- Validation: all 140 backend tests passed, including intent, single-term reference retrieval, unrelated-vector rejection, SSO branch filtering, structured output, citation/URL boundaries, passive completion claims, safe/unsafe Soft SSO wording, model fallback, and stale guidance. Final TypeScript/Vite production build passed. Isolated headless Edge against the built site with synthetic responses verified six primary steps, expansion, visible required checks, collapsed evidence, answer-only and mixed layouts, numbered customer instructions, exact clipboard text, legacy source aliases, and 1440/768/390/320 widths. Existing dependency deprecation warnings remain. No live model request or Salesforce customer write was made. The app service remains stopped; this change is implemented and built locally.

## 2026-09-30 - Repair approach length and visual formatting

- Goal: resolve long, poorly aligned guidance actually visible in the workspace. Reason: inspection of saved ticket shape (without printing customer text) found pre-structured fallback approaches with 64-109 lines and 4,885-7,674 characters; the UI still rendered those in full. Added a compact legacy view with an explicit request for fresh guidance and an expandable, complete saved approach. Stored ticket files are not rewritten. Mandatory checks and escalation indicators stay visible.
- Goal: make new guidance shorter without deleting procedure requirements. Reason: the previous six primary bullets and 60-word limit still permitted dense paragraphs. Show four primary bullets; prompt for 12-22 words per bullet and enforce 40 words plus a 25-word summary. Retain additional ordered steps behind an explicit review-before-acting expansion. Oversized existing structured steps expand individually with no textual truncation. Procedural model fallbacks now give short evidence-review steps instead of presenting raw playbook paragraphs as executable instructions; full evidence remains available. Shortened generic check wording while retaining account notes, employee review, and stop-on-missing-reference requirements. Consulted the local guardrails before changing presentation of these requirements.
- Goal: align bullets, paragraphs and sections on desktop and mobile. Reason: unordered lists relied on browser defaults while ordered lists had separate styling. Applied consistent outside markers, 22px indentation, left alignment, 13px text, 1.6 line height, section spacing and paragraph margins. Render safe Markdown emphasis/code and headings, normalize newline variants, and join indented continuation lines into the same list item. Exact reply copying still uses the original string.
- Validation: full backend regression run passed 140 tests; after adding three format-specific cases, all 25 focused guidance tests passed (including 41-word rejection, 26-word summary rejection and compact procedural fallback). Final TypeScript/Vite build passed. Isolated headless Edge against the final built site tested a synthetic 90-paragraph legacy result, complete expansion, visible escalation/checks, four primary steps, remaining-step numbering, aligned list coordinates and computed indentation, section spacing, emphasis, answer-only/mixed layouts, exact clipboard text, and 1440/768/390/320 widths. Desktop/mobile screenshots were inspected and saved locally in .runtime/guidance-format-1440.png and .runtime/guidance-format-390.png. No live model requests or Salesforce customer writes were made.

## 2026-09-30 - Gemini generation and source-free case guidance

- Goal: use the user-selected Gemini 3.8 Flash API instead of OpenAI. Reason: the user explicitly replaced the previous provider request with Gemini. Replace the OpenAI requirement with google-genai>=2.25,<3.0 and use Google's native Interactions client against its default Google endpoint. Supply GEMINI_API_KEY explicitly, GEMINI_MODEL=gemini-3.8-flash, and ENABLE_GEMINI_TRIAGE; old OpenAI credentials/flags are ignored. Use store=false, a 40-second request timeout, no tools or previous interaction, and one bounded retry on HTTP 429. Close the SDK client after success or failure. Adapt the wire schema to Gemini's supported subset while retaining all Pydantic, word-limit, grounding and safety checks locally. Emit gemini_rag_refined and update activity tracking and provider-safe error handling. SDK 2.25.0 was installed and tested; no live generation request was made.
- Goal: remove visible document references without weakening retrieval. Reason: the user does not want referenced playbooks mentioned in guidance. Remove reference lists, source previews, source/reasoning panels and associated viewer state from the workspace. Use neutral guidance labels; no document IDs are appended to suggested_approach. Keep source_ids, reply_source_ids, retrieved documents and evidence internally for validation and compatibility. Prompt Gemini to keep citations only in structured source fields; reject source IDs, document paths and reference-panel/playbook mentions in visible response fields. Reword deterministic summaries/fallbacks so agents are never told to open a removed panel. Local fallbacks propose clarification and experienced-agent review when validated drafting is unavailable.
- Goal: support saved results without exposing old source panels. Reason: older stored guidance can contain inline citations and obsolete panel instructions. Sanitize displayed citations and old source-panel wording; render legacy OpenAI mode as ordinary AI guidance without calling that provider. Long legacy source-heavy approaches now request regeneration rather than displaying full raw document excerpts. Existing ticket JSON is not rewritten, and mandatory approval/escalation checks remain visible. Customer reply copying preserves its original validated text. Consulted local guardrails and missing-reference requirements; no resolution policies or private source documents were changed.
- Goal: prepare safe server-side configuration. Reason: no Gemini credential is present. Add missing Gemini settings to the ignored backend/.env with an empty key and generation disabled; preserve all existing credentials/settings. Update the sanitized environment example and README with activation/restart instructions. No credentials or provider exception payloads are returned to the frontend or committed.
- Validation: all 159 backend tests passed. Tests include a real google-genai SDK request/response roundtrip over httpx.MockTransport verifying Google's hostname, model, store=false, JSON schema, output parsing and timeouts; retries/client closure; provider status, timeout, malformed/truncated/refused responses; source-free visible text; internal grounding; and old OpenAI settings not enabling generation. Final TypeScript/Vite build passed. Isolated headless Edge against the final built site verified no visible document titles/IDs/reference panels (including synthetic legacy data), Gemini/legacy AI labels, direct answers/mixed procedures, compact layout and aligned markers, visible checks, exact reply clipboard text, and 1440/768/390/320 widths. Mobile screenshots were reviewed. Tests used synthetic descriptions, mocked provider transport and temporary tickets; no live Gemini call or Salesforce customer write occurred. Activation/live verification requires a server-side Gemini key and ENABLE_GEMINI_TRIAGE=true.

## 2026-09-30 - Preserve Salesforce connection errors

- Goal: show the actual Salesforce connection failure instead of incorrectly attributing every failure to localhost TLS. Reason: Connect caught all non-401 HTTP errors and replaced their safe backend detail with a generic certificate/running-server warning. Preserve structured HTTP error messages (permission, configuration, provider unavailable); only network failures receive browser connectivity instructions, with certificate trust conditional on an actual browser warning. HTTP 401 still permits the explicit fresh OAuth action. No OAuth, credentials, session, writeback, or resolution policy changed.
- Diagnosis: live /auth/salesforce/status returned 200 without cookies, Salesforce configuration was present, system TLS trust succeeded, and the exact https://localhost:8012 browser origin was accepted. The user's cookie-specific failure requires the same-browser status response; no cause is assumed from these cookie-free checks.

## 2026-09-30 - Restore backend outbound Salesforce connectivity

- Goal: allow the locally running backend to reach Salesforce during authorized OAuth and connection checks. Reason: a credential-free request to the configured Salesforce authorization endpoint failed with WinError 10061 inside the restricted execution environment, but reached Salesforce with HTTP 400 outside it (expected for a request without OAuth parameters). Stopped the restricted backend session and restarted `python backend/run.py` with approved network access. No credentials, OAuth scopes, customer records, or writeback settings were changed.
- Validation: restarted HTTPS backend reports /health HTTP 200 and cookie-free /auth/salesforce/status HTTP 200 with configured=true. Salesforce public endpoint reachability is verified; authenticated connection completion still requires the user's browser OAuth flow.
