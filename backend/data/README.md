# Private knowledge-base content

Place the authorized support playbooks in `backend/data/CA/` as Markdown files.
The application reads this directory when providing guidance.

These internal procedures are intentionally excluded from the public repository.
Obtain them through your organization's approved private distribution channel.
Do not remove the ignore rule or force-add these documents to a public remote.

Without the playbooks, case intake and Salesforce integration remain available,
but playbook guidance is unavailable or routes to human review. Tests that expect
the organization's supplied playbooks require those files to be provisioned first.

## Layout and retrieval

Use `CA/cases/` for resolution playbooks, `CA/reference/` for guardrails, glossary,
routing and workflow references, and `CA/reference/sync-sources/` for vendor-specific
guidance. Keep `README.md` and the router `SKILL.md` at the CA root. The loader also
supports existing flat distributions. Underscore-prefixed and hidden directories
(including `CA/_archive/`) are excluded from both retrieval and the knowledge-base API.

Each document needs a unique filename stem. Case documents declare `type: case`,
`case_type`, `aliases`, `risk`, and a JSON-array `required_context` in frontmatter;
reference documents declare `type: reference`. Existing authorization, sensitivity,
owner and destructive-action metadata remains authoritative. H2 sections retain
their nested conditions, tables and steps when retrieved. Inline document paths in
the private corpus are relative to the CA root.

The local migration consolidated duplicate/additional documents and preserved all
original files under `CA/_archive/before-description-rag/`. Distribute the active
private corpus separately when deploying application changes. Do not publish the
archive or private source text in Git or test fixtures.
