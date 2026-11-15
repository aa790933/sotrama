# Algerian Localization

Custom Frappe app that adds Algerian business registration fields (NIF, NIS, RC) to the **Company** doctype in ERPNext, plus a country setup script for Algeria.

## Why this app?

When you add custom fields via the Desk UI (Customize Form), they're stored in the database. On `bench update`, they can be wiped or conflicted. This app defines them in **code** — they're part of the app's source, so they survive updates and migrate cleanly to new sites.

## What it does

- Adds three fields to the **Company** doctype:
  - `nif` — Numéro d'Identification Fiscale (tax ID)
  - `nis` — Numéro d'Identification Statistique (statistical ID)
  - `rc` — Registre de Commerce (trade registry number)
- Sets Algeria as the default country for new companies
- Provides a `setup` script that can be called from ERPNext's regional setup system

## Installation

```bash
cd ~/frappe-bench
bench new-app algerian_localization
# OR if you already have the app files:
bench install-app algerian_localization
bench --site your-site migrate
```

## Usage

After installation, every Company record will show NIF, NIS, and RC fields. These are standard `Data` fields — they appear in search, filters, and reports like any other field.

## License

MIT