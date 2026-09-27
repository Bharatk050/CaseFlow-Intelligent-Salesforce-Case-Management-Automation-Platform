# Salesforce External Client App troubleshooting

## HTTPS development and personal progress

Run `python backend/run.py` from the project root and `npm run dev` inside
`frontend`. Open **https://localhost:5173**. Vite uses the existing localhost
certificate and a fixed port. Trust the local certificate for both that address
and **https://localhost:8012**. Use HTTPS and the localhost hostname consistently.

Keep the registered Salesforce callback at
`https://localhost:8012/auth/salesforce/callback`. The frontend passes its origin
when starting OAuth; the backend accepts only FRONTEND_URL or
`https://localhost:5173`, stores it in a short-lived HTTP-only cookie, and returns
there after authorization. Production continues to use FRONTEND_URL. CORS permits
these explicit origins only. Failed status checks now offer a retry rather than
claiming configuration is missing. Expired sessions can start a fresh login.

Connect Salesforce before importing Excel to retain new imports and progress
under that organization and user. Earlier beta imports remain temporary and are
not automatically transferred. Track Progress (`#/progress`) counts each explicit
transition to local Resolved: repeated saves do not add credit; reopening and
resolving again does. No Salesforce closure or writeback occurs.

Progress starts with newly recorded events and includes currently accessible
cases only. Historical status edits cannot reliably establish resolution credit.
Reconnect with the same Salesforce identity to retrieve your progress. The
7/30/90-day chart uses your browser timezone and includes a daily-count table.

Install backend requirements, including `tzdata` for Windows timezone support.
Use the single-worker `backend/run.py` launcher: ticket mutations use an
in-process lock and atomic JSON replacement. Multiple worker processes are not
supported by this file-storage synchronization.

The app runs at `https://localhost:8012`. Excel beta works independently of Salesforce on this computer, with separate HTTP-only browser sessions. It does not grant access to Salesforce cases. Historical unowned imports remain unchanged.

## Identify the target org

In Salesforce, open **Setup → My Domain** and copy **Current My Domain URL**.

- A sandbox typically uses `https://company--sandbox.sandbox.my.salesforce.com`.
- Production and Developer Edition use `https://login.salesforce.com` or their My Domain origin. Sandbox login uses `https://test.salesforce.com` or its My Domain origin.
- Set `SALESFORCE_LOGIN_URL` in `backend/.env` to the target org's HTTPS login origin, then restart the backend. Both authorization and token exchange use it. Do not use a Lightning application URL.

Source: [Salesforce login URLs](https://help.salesforce.com/s/articleView?id=xcloud.domain_name_login_code.htm&language=en_US&type=5).

## Check the External Client App in that same org

### Identified scope mismatch for this installation

The user confirmed that the registered app selects only `api`, while the running backend requests `api id`. The backend needs `id` to retrieve the signed-in user's identity. The Consumer Key and callback were reported to match.

In **External Client Apps Manager → your app → Settings → Edit → Selected OAuth Scopes**, retain **Manage user data via APIs (api)** and add **Access the identity URL service (id, profile, email, address, phone)**, then save. Keep the existing PKCE and self-authorization settings. No backend scope change or restart is required for this Salesforce-side correction.

Start a fresh login from the dashboard's **Connect Salesforce** button. Completion requires the callback to succeed, the dashboard to show **Connected**, and authorized queues to load. Then explicitly sync the intended queue to verify read access. The scope mismatch is confirmed from user-provided settings; it is not yet proven to be the only cause of the generic error. Do not record OAuth as fixed until the live flow succeeds.

Source: [Salesforce identity scope](https://help.salesforce.com/s/articleView?id=sf.sso_provider_addl_params_scope.htm&language=en_US&type=5).

### Other registration checks

1. Open **Setup → External Client Apps Manager → your app**.
2. Confirm OAuth is enabled and the registered callback is exactly `https://localhost:8012/auth/salesforce/callback`.
3. Confirm the app allows the requested scopes `api` and `id`. This application uses Authorization Code web-server flow with PKCE S256; it does not use client-credentials or password login.
4. Under **Policies → OAuth Policies → Permitted Users**, check whether users must be preauthorized. If so, the administrator must assign access to this app through the intended user's profile or permission set. Do not grant broad “Use Any API Client” permissions merely to bypass the error.
5. Ensure the app is deployed/available in the org being used and that its Consumer Key and Consumer Secret match the server-side configuration. Never paste either into frontend code or diagnostic messages.

Source: [Preauthorize External Client App users](https://help.salesforce.com/s/articleView?id=sf.preauth_user_app_access_through_eca.htm&language=en_US&type=5).

`OAUTH_APPROVAL_ERROR_GENERIC` alone does not identify the exact failed setting. The error page's `error` and `error_description` values or Salesforce administrator login/authorization diagnostics are needed to distinguish an org mismatch, app availability, and policy rejection. Share only those error fields, never authorization codes, state, tokens, or secrets.

Salesforce also documents this message for **uninstalled Connected Apps**, which is a distinct app type. Do not treat that explanation as confirmed for an External Client App: [Connected App restrictions](https://help.salesforce.com/s/articleView?id=005132365&language=en_US&type=1).

## Local checks

- `GET /health` reports whether the API is running.
- `GET /auth/salesforce/diagnostics` is restricted to loopback clients and reports the login URL, callback, scopes, PKCE mode, and writeback setting without credentials.
- OAuth error callbacks now return actionable, fixed messages to the dashboard and do not echo provider-supplied descriptions.
- App approval cannot be verified by local configuration checks alone; complete a user-authorized Salesforce login after the administrator confirms the settings.
- `SALESFORCE_ALLOW_WRITEBACK=false` remains the default. Fixing login must not enable writes.

## Start the app

From the project root, after `npm run build` in `frontend`:

```powershell
python backend/run.py
```

From inside `backend`, use `python run.py`. The launcher resolves imports and certificates relative to its own location. Python 3.11 or newer is required. Use `python backend/run.py --check` for a configuration check.

If RQC is already running, the launcher reports its URL and does not start a competing server. Stop the previous RQC server before restarting it to load backend changes. On Windows, the launcher uses a selector event loop for this single-process server to avoid Proactor socket-cleanup connection-reset tracebacks. Access logging remains disabled to avoid logging OAuth query parameters.


## Signed-in name and Roster support Queue list view

The workspace displays the Salesforce user's full name, while ownership and
progress continue to use the authenticated organization and user ID. Existing
sessions acquire a name on their next lookup; unavailable names show Salesforce
user. No credential or token is returned to the browser.

After sign-in or page reload, the app automatically finds the accessible **Case
list view** whose complete label is **Roster support Queue**, ignoring case and
surrounding whitespace. This is the saved view in the Salesforce Cases dropdown,
not a Group queue or an OwnerId filter. The existing saved view determines case
membership, including open/closed conditions. Refresh cases repeats the lookup.

- No accessible matching view: **No queue found**.
- Matching view with no results: **No cases**.
- Duplicate matching labels: an explicit ambiguity error.
- Permission, session, or network failures: an error with retry/reconnect guidance.

The authenticated POST /auth/salesforce/roster-support/sync endpoint returns the
view, found/missing state, cases, count, and sync timestamp. Results are paginated,
full workspace fields are fetched by Case ID, and saved-view order is retained.
New results replace displayed Salesforce cases; saved ticket JSON and resolution
history are preserved. Excel imports remain identifiable by their source.
Legacy queue sync remains available to existing API clients but is no longer used
by the workspace. These retrieval operations do not write to Salesforce.
