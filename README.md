# Sotrama — Algerian Localization & TP Fleet Management for ERPNext

Adds Algerian company registration fields to ERPNext **Company** — **NIF / Matricule Fiscal**, **Article d'imposition**, **NIS**, **RC**, and **Capital Social** — plus a
**TP (Travaux Publics / Public Works)** fleet-management module for Algerian
construction companies. Classification scoring and payroll/legal calculations
must be validated against applicable Algerian regulations before statutory use.

Sotrama is a **separate Desk app**. It appears alongside ERPNext and Frappe HR on
the Apps screen, has its own Fleet dock and TP sidebar, and does not insert its
DocTypes into ERPNext's Accounts, Stock, Selling or other modules.

## What it does

### Algerian Localization
- Adds `custom_nif` (NIF / Matricule Fiscal), `custom_article_imposition`, `custom_nis` (Statistical ID), `custom_rc` (Trade Registry), and `custom_capital_social` fields to **Company** — `custom_` prefixed to prevent collisions with future ERPNext fields
- NIF / Matricule Fiscal is stored once, avoiding duplicate fields for the same tax identifier; Article d'imposition is stored separately as the article fiscal shown on the Certificate of Existence (C n°20)
- Capital Social is a Currency field using the Company's default currency
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
| **Maintenance Job Card** | Repair/service work order — parts, labour, vendor and costs; stock issue uses the Vehicle's warehouse or the TP Settings default, with strict company and Cost Center validation |
| **Breakdown Incident** | Unexpected failure tracking — auto-creates job cards, tracks downtime, marks vehicle Out of Service |
| **Maintenance Schedule** | Preventive maintenance — calendar or mileage-based, advances its next-due date from submitted service cards and can create a linked successor when a plan is completed |
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

### TP Settings and multi-company defaults

The **TP Settings** singleton centralizes policy switches and reminder windows.
Its **Company Defaults** child table stores one Company Classification,
Department, Cost Center and Parts Warehouse per legal entity. Fleet records
inherit defaults for their selected company and retain their own company
assignment, so adding a factory or quarry does not require more Custom Fields.
Company, Warehouse, Cost Center, Department, Project and Employee links are
validated to prevent cross-company posting and assignment mistakes. A Driver
may link to an existing Employee; this link remains optional unless enabled in
TP Settings. Users need the normal ERPNext/Frappe HR permission to read Employee
records — Sotrama does not grant extra HR access automatically.

### Reports and print formats

Fleet Cost Analysis now filters by Company, Vehicle and date range, aggregates
submitted maintenance/task records, and labels straight-line depreciation as
an estimate. Upcoming Document Expiries reads the alert window from TP Settings
when no report filter is entered. Both reports declare a reference DocType so
the Frappe 16 report view can load metadata correctly.

Completing a Scheduled Service Job Card advances the selected recurring plan
in place. The plan's prior service and due-date values are retained on the Job
Card so cancellation can restore them without overwriting a later service.
Manually completing a plan instead creates a linked successor occurrence.

The Maintenance Job Card and Vehicle Inspection formats use Frappe 16's
editable Print Format Builder Beta layout (`format_data`), rather than legacy
JS print formats. They can be adjusted later in the standard Print Format
Editor. Frappe 16 selects a compatible PDF renderer (Chromium or PlutoPrint)
and falls back to Chromium when a server does not have the optional PlutoPrint
runtime or a layout uses unsupported features.

### Algerian transport-driver compliance

Driver licence categories follow Article 180 as amended by Executive Decree
25-169 (Official Gazette No. 43, 13 July 2025). For the five professional
road-transport activities in Articles 79–80 of Law 26-09 (Official Gazette
No. 36, 17 May 2026), Sotrama checks the activity-specific *brevet
professionnel*, a current medical-fitness record and a negative drug-screening
record before assignment. Periodic and unannounced screening follow-up is
tracked through HR-restricted child records; the application deliberately does
not invent a universal medical or screening validity interval. Review dates are
entered from the competent provider and implementing rules. Medical results
are visible only at the restricted HR permission level, and scheduler tasks
contain no test result or medical date.

Safety-critical inspection findings keep the vehicle Out of Service until a
separate follow-up inspection is submitted with an overall **Pass** result and
no remaining critical defects. Cancelling that follow-up reinstates the hold;
the original inspection is retained as the audit record.

## Why this app?

Custom fields added via the Desk UI (Customize Form) live in the database. On `bench update`, they can be wiped or conflicted. Sotrama defines all customizations in **code** — they're version-controlled, reinstall cleanly on new sites, and never conflict with ERPNext upgrades.

**No custom CSS** — the app follows standard Frappe Desk styling and uses only standard Frappe UI components. All client-side behavior is handled through standard DocType JS files.

## Compatibility

- Frappe Framework 16.50+ and ERPNext 16.50+
- Frappe HRMS 16.50+ (required for the Driver-to-Employee relationship)
- Python 3.14 (matching the Frappe v16 runtime requirement)
- Node.js 24 for the v16 asset toolchain
- This app does not currently implement Algerian payroll statutory calculations.
- Sotrama application version: 1.2.1

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
- A legacy `custom_capital_social` Data field is upgraded to Currency before field synchronization, avoiding Frappe's direct fieldtype-change validation error
- `before_uninstall()` removes fields cleanly — no orphaned metadata
- All Company localization fields are re-applied by migration and are named in a single code-owned schema definition
- TP operational policies are centralized in `TP Settings`; company-specific defaults are in the `TP Company Defaults` child table
- Fleet report queries use permission-aware list access and avoid per-vehicle N+1 aggregation
- Print formats ship as editable Frappe 16 Print Format Builder Beta layouts

### Frappe 16 navigation on upgraded sites

Frappe 16 keeps the legacy Desktop icon grid as a fallback on sites upgraded
from earlier releases. To show Sotrama alongside ERPNext and Frappe HR, a
System Manager must open **Desktop Settings**, set **Desktop Page** to **Apps**,
and save. This is a site-wide navigation preference; Sotrama does not silently
change it during installation. The Sotrama app then opens its own Fleet module
and sidebar, without moving its DocTypes into ERPNext modules.
- Daily scheduler checks document expiries, maintenance due dates, and driver license expiries
- Supports the Frappe/ERPNext 16 major release line; upgrade the framework and app together after taking a site backup
- Uses standard DocType controller lifecycle methods; the sole `Company.validate` event synchronizes the standard ERPNext Tax ID with the Algerian NIF alias

## License

MIT
