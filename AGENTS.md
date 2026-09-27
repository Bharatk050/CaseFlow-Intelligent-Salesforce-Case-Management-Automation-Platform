# AI project rules

1. Keep the frontend focused on the agent workflow and the backend as the source of truth.
2. Store each support ticket as a separate JSON file in `backend/support_files/`; never overwrite unrelated tickets.
3. Help-center playbooks live in `backend/data/CA/` as Markdown and must be consulted before changing routine-resolution rules.
4. Automation must escalate security, privacy, payment disputes, data-loss, abusive, urgent, or low-confidence requests to a human.
5. Every AI-driven product, logic, or configuration decision must be appended to `change_ai.md` with its goal and reason.
6. Prefer deterministic, explainable behavior until an approved external model integration is added.
7. Salesforce access must use a user-authorized OAuth flow; credentials, access tokens, and client secrets must never be committed or returned to the frontend.
8. Do not write to Salesforce automatically. Case updates require an explicit agent action and `SALESFORCE_ALLOW_WRITEBACK=true`.
