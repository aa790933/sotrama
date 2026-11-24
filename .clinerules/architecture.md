# Sotrama Frappe App — Architecture, Graphify & Workflow Rules

## 1. Graph-First Context Retrieval (Mandatory)
- NEVER scan the entire repository or read multiple files blindly. Before modifying any code or answering architectural questions, query the `graphify` MCP server first:
  - Use `god_nodes` to identify core controllers and high-dependency modules.
  - Use `query_graph` and `get_neighbors` to trace DocType hooks, imports, and function callers.
  - Use `shortest_path` to check impact radius before refactoring shared utilities or `hooks.py`.
- Read `graphify-out/GRAPH_REPORT.md` and `memory-bank/activeContext.md` at the start of major tasks.

## 2. Frappe v16.60.2 & ERPNext/HRMS v16.60.0 Standards
- Ground security and compatibility claims in actual Frappe v16.60.2 / ERPNext v16.60.0 / HRMS v16.60.0 code behavior and exact file/symbol locations.
- Use `frappe.qb` or `frappe.get_all` / `frappe.get_list` for database queries; keep business logic in Python controllers or whitelisted APIs, and keep `hooks.py` handlers modular.
- Preserve `File` lifecycle behavior (`file_doc.save(ignore_permissions=True)` rather than raw `is_private` DB mutation) and verify `/files/` vs `/private/files/`, `is_downloadable()`, private URL reuse, cross-company/parent moves, child tables, and `DocShare` rules carefully.

## 3. Git Safety, Verification Separation & Planning
- Always inspect `git status --short --branch`, `git rev-parse HEAD`, `git branch -vv`, `git remote -v`, `git diff --stat`, `git diff --check`, and untracked files before editing.
- Never run `git reset`, `git clean`, force-push, `rebase`, `amend`, or history rewrites. Never commit, push, create a temporary branch, or create a release without explicit user approval.
- Never treat static checks, `ruff`, JS tests, or wheel builds as Frappe/MariaDB runtime or CI verification. Clearly separate modified items, verified items, untested items, and items requiring Frappe/MariaDB/CI.
