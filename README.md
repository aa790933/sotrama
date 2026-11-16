# Sotrama — Algerian Localization & TP Fleet Management for ERPNext

Adds **NIF, NIS, and RC** fields to the ERPNext **Company** doctype, plus a complete
**TP (Travaux Publics / Public Works)** Fleet Management module for Algerian
construction companies — especially those holding a **Grade 8 (Catégorie 8)**
classification per Décret Exécutif n° 14-139.

## What it does

### Algerian Localization
- Adds `custom_nif` (Tax ID), `custom_nis` (Statistical ID), and `custom_rc` (Trade Registry) fields to the **Company** doctype — `custom_` prefixed to prevent collisions with future ERPNext fields
- Fields are defined in code, not the database — they survive `bench update` and migrate cleanly
- Hooks into ERPNext's regional setup: created automatically when a Company with `country = "Algeria"` is created

### TP Fleet Management (Public Works)

| DocType | Purpose |
|---|---|
| **Vehicle** | Fleet vehicle master — license plate, chassis, tonnage, odometer, status, Algerian docs, document expiry child table |
| **Driver** | Driver master — license number, class, expiry, medical, safety certifications |
| **Maintenance Job Card** | Repair/service work order — parts, labour, vendor, costs, auto-posts Stock Entry |
| **Breakdown Incident** | Unexpected failure tracking — auto-creates job cards, tracks downtime, marks vehicle Out of Service |
| **Maintenance Schedule** | Preventive maintenance — calendar or mileage-based, auto-generates next occurrence |
| **Vehicle Inspection** | Structured checklist — pass/fail per item, auto-creates ERPNext Issues for defects |
| **Operational Task** | Task assignment — vehicle ↔ driver ↔ project, tracks hours and output |
| **Company Classification** | Algerian grade (I–IX) calculator per Arrêté Interministériel formula |
| **Vehicle Document** | Child table — document expiry tracking (registration, insurance, pollution, etc.) |
| **Maintenance Job Type** | Master for service categories (Oil Change, Brake Service, etc.) |
| **Vehicle Make / Model** | Manufacturer and model masters |

### Supporting Child Tables
- **Job Card Part** — parts consumed with item validation and cost calculation
- **Job Card Labour** — labour lines with mechanic and rate
- **Job Card Other Cost** — incidental costs (toll, fuel, rental, etc.)
- **Job Card Photo** — photos attached to job cards
- **Breakdown Photo** — photos attached to breakdown incidents
- **Inspection Item** — checklist items with Defective/Okay status and remarks enforcement

## Why this app?

Custom fields added via the Desk UI (Customize Form) live in the database. On `bench update`, they can be wiped or conflicted. Sotrama defines all customizations in **code** — they're version-controlled, reinstall cleanly on new sites, and never conflict with ERPNext upgrades.

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

## Upgrade safety

- All custom fields are defined in `hooks.py` / `setup.py` as Python code — never in the database
- `custom_` prefix on Company fields prevents collisions with future ERPNext standard fields
- `fixtures` in `hooks.py` exports them as JSON for version control and clean reinstall
- `after_migrate()` re-applies fields after any schema migration
- `before_uninstall()` removes fields cleanly — no orphaned metadata
- Daily scheduler checks document expiries, maintenance due dates, and driver license expiries
- Uses v16 `extend_doctype_class` pattern (extend, don't override) for core Vehicle integration
- Pinned version range `>=16.50.0, <17.0.0` in `pyproject.toml`

## License

MIT