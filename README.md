# Sotrama

Algerian localization for ERPNext — adds **NIF, NIS, and RC** fields to the **Company** doctype.

## Why this app?

When you add custom fields via the Desk UI (Customize Form), they're stored in the database. On `bench update`, they can be wiped or conflicted. Sotrama defines them in **code** — they're part of the app's source, so they survive updates and migrate cleanly to new sites.

## What it does

- Adds three fields to the **Company** doctype:
  - `nif` — Numéro d'Identification Fiscale (tax ID)
  - `nis` — Numéro d'Identification Statistique (statistical ID)
  - `rc` — Registre de Commerce (trade registry number)
- Hooks into ERPNext's regional setup system: when a Company with `country = "Algeria"` is created, the fields are created automatically
- Provides clean uninstall: removes the custom fields when the app is uninstalled

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/dekukoda41/sotrama
bench --site your-site install-app sotrama
bench --site your-site migrate
```

Or clone manually:

```bash
cd ~/frappe-bench/apps
git clone https://github.com/dekukoda41/sotrama.git
cd ../
bench install-app sotrama
bench --site your-site migrate
```

## Usage

After installation, every Company record will show NIF, NIS, and RC fields under the **Tax Details** section. These are standard `Data` fields — they appear in search, filters, and reports like any other field.

When you create a new Company with `country = "Algeria"`, the fields are created automatically via ERPNext's regional setup hook.

## Upgrade safety

- All custom fields are defined in `hooks.py` / `setup.py` as Python code — never in the database
- `fixtures` in `hooks.py` exports them as JSON for version control and clean reinstall
- `after_migrate()` re-applies fields after any schema migration
- `before_uninstall()` removes fields cleanly — no orphaned metadata

## License

MIT