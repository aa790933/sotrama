# Sotrama — Algerian Localization & TP Fleet Management for ERPNext

Adds **NIF, NIS, and RC** fields to the ERPNext **Company** doctype, plus a
**TP (Travaux Publics / Public Works)** fleet-management module for Algerian
construction companies. Classification scoring and payroll/legal calculations
must be validated against applicable Algerian regulations before statutory use.

Sotrama is a **separate Desk app**. It appears alongside ERPNext and Frappe HR on
the Apps screen, has its own Fleet dock and TP sidebar, and does not insert its
DocTypes into ERPNext's Accounts, Stock, Selling or other modules.

## What it does

### Algerian Localization
- Adds `custom_nif` (Tax ID), `custom_nis` (Statistical ID), and `custom_rc` (Trade Registry) fields to the **Company** doctype — `custom_` prefixed to prevent collisions with future ERPNext fields
- Fields are defined in code, not the database — they survive `bench update` and migrate cleanly
- Created by the app's `after_install` and `after_migrate` hooks; fields are available on Company records and are not conditionally created by country

### TP Fleet Management (Public Works)

The shipped navigation is grouped into Fleet Operations, Maintenance & Safety,
Reports & Analysis, and Setup & Masters. The Sotrama Fleet workspace presents
the fleet number cards and grouped links without turning every DocType into one
long menu.

| DocType | Purpose |
|---|---|
| **Vehicle** | Fleet vehicle master — license plate, chassis, tonnage, odometer, status, Algerian docs, document expiry child table |
| **Driver** | Driver master — license number, class, expiry, medical, safety certifications |
| **Maintenance Job Card** | Repair/service work order — parts, labour, vendor and costs; stock issue requires a company and source warehouse configured on the Vehicle |
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

### ERPNext and Frappe HR integration

Fleet records use standard links to shared ERPNext/HRMS masters and transactions:
Company, Department, Cost Center, Warehouse, Asset, Item, Supplier, Project,
Employee, and Stock Entry. Sotrama does not duplicate those ledgers or create
parallel copies of ERPNext/HRMS records. Stock-consuming maintenance uses ERPNext
Stock Entry and its normal valuation/accounting pipeline.

## Why this app?

Custom fields added via the Desk UI (Customize Form) live in the database. On `bench update`, they can be wiped or conflicted. Sotrama defines all customizations in **code** — they're version-controlled, reinstall cleanly on new sites, and never conflict with ERPNext upgrades.

**No custom CSS** — the app follows standard Frappe Desk styling and uses only standard Frappe UI components. All client-side behavior is handled through standard DocType JS files.

## Compatibility

- Frappe Framework 16.50+ and ERPNext 16.50+
- Frappe HRMS 16.50+ (required for the Driver-to-Employee relationship)
- Python 3.14 (matching the Frappe v16 runtime requirement)
- Node.js 24 for the v16 asset toolchain
- This app does not currently implement Algerian payroll statutory calculations.

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/aa790933/sotrama
bench --site your-site install-app sotrama
bench --site your-site migrate
```

Or clone manually:

```bash
cd ~/frappe-bench/apps
git clone https://github.com/aa790933/sotrama.git
cd ../
bench install-app sotrama
bench --site your-site migrate
```

## Upgrade safety

- All custom fields are defined in `hooks.py` / `setup.py` as Python code — never in the database
- `custom_` prefix on Company fields prevents collisions with future ERPNext standard fields
- App metadata, app-screen permission, Dock and module Sidebar are shipped using Frappe v16 hooks and standard records
- `create_custom_fields()` is called with the Frappe 16 API; lifecycle hooks are registered as import paths
- `fixtures` in `hooks.py` exports them as JSON for version control and clean reinstall
- `after_migrate()` re-applies fields after any schema migration
- `before_uninstall()` removes fields cleanly — no orphaned metadata

### Frappe 16 navigation on upgraded sites

Frappe 16 keeps the legacy Desktop icon grid as a fallback on sites upgraded
from earlier releases. To show Sotrama alongside ERPNext and Frappe HR, a
System Manager must open **Desktop Settings**, set **Desktop Page** to **Apps**,
and save. This is a site-wide navigation preference; Sotrama does not silently
change it during installation. The Sotrama app then opens its own Fleet module
and sidebar, without moving its DocTypes into ERPNext modules.
- Daily scheduler checks document expiries, maintenance due dates, and driver license expiries
- Supports the Frappe/ERPNext 16 major release line; upgrade the framework and app together after taking a site backup
- Uses standard DocType controller lifecycle methods; no redundant `doc_events` wrappers are registered

## License

MIT
