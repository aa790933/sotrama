# Sotrama — Algerian Business Extensions for ERPNext

Sotrama is a modular Frappe application that extends ERPNext and Frappe HR for
Algerian businesses, with an initial focus on **BTPH / Travaux Publics**. It is
installed beside the official apps and uses their standard records, workflows,
permissions and accounting/inventory transactions. It does not fork or patch
Frappe, ERPNext or HRMS core.

The app is designed to grow by adding standard Frappe modules. It includes the
**Sotrama** landing module plus **Algerian Localization** and **TP** (public-
works fleet operations). The Sotrama Desk workspace is the app landing page.
Frappe filters its module and settings links by the destination workspace's or
DocType's permissions, so users only see destinations they are allowed to open.

## Architecture and source of truth

Sotrama links to the standard ERPNext / Frappe HR records wherever they exist:

- `Company`, `Employee`, `Department`, `Project`, `Asset`, `Item`, `Supplier`,
  `Warehouse`, `Cost Center` and `Stock Entry` remain authoritative.
- Maintenance stock consumption uses ERPNext Stock Entry and its normal
  valuation/accounting pipeline.
- Drivers may link to the authoritative HRMS `Employee` record; Sotrama does
  not create a parallel employee register.
- Fleet records retain a standard `Company` link to support multiple legal
  entities (for example, a construction company, factory and quarry).

The app does not create parallel general ledgers, stock ledgers, employees or
company records.

## Modules

### Algerian Localization

The optional Algerian Company extension adds these fields to the standard
ERPNext `Company` DocType only after an administrator explicitly enables it:

| Field | Purpose |
|---|---|
| `Company.tax_id` | Standard ERPNext field used for NIF / Matricule Fiscal; Sotrama does not create a duplicate NIF field |
| `custom_article_imposition` | Article d'imposition |
| `custom_nis` | Numéro d'Identification Statistique |
| `custom_rc` | Registre de Commerce |
| `custom_capital_social` | Registered share capital, stored as Currency using the Company's default currency |

**Enable the extension:** sign in as System Manager, open **Sotrama → Sotrama
Settings**, and enable **Enable Algerian Company Registration Fields**. The
fields are displayed on Company records whose Country is Algeria. They remain
optional and do not replace standard ERPNext Company fields.

The fields are deliberately not installed as fixtures and are never created
or altered by a migration. Saving the setting after explicitly enabling it is
the authorization for Sotrama to create any missing fields. Existing fields
are checked first: Sotrama refuses a field-type mismatch or a field owned by
another module rather than silently changing or
taking it over. Review the conflict and resolve it deliberately before
enabling the feature.

Disabling the setting hides Sotrama-owned Company fields; it does not delete
their metadata or stored values. Before app uninstall, Sotrama detaches its
managed Company fields into Frappe's persistent `Custom` module so Frappe's
normal removal of app-owned modules does not delete those fields or their
stored values. Sotrama retains an ownership marker in each generated field's
description and recognizes only marked fields after reinstall; it does not
claim an unrelated system-generated field just because the fieldname matches.
A legacy `custom_nif` field from an older installation
is hidden, not deleted; review its values and reconcile them with the standard
`Company.tax_id` field before retiring any old data. Sotrama does not overwrite
an existing Tax ID automatically.

### TP — Public Works Fleet

The TP module currently provides:

| DocType | Purpose |
|---|---|
| **Vehicle** | Fleet register, registration/chassis details, ownership, valuation and vehicle documents |
| **Driver** | Driver register with optional HRMS Employee link, licence and compliance information |
| **Maintenance Job Card** | Repair and service work orders, labour, parts, other costs and stock issue integration |
| **Breakdown Incident** | Failure tracking, downtime and linked maintenance work |
| **Maintenance Schedule** | Recurring time- or mileage-based preventive maintenance |
| **Vehicle Inspection** | Inspection checklist, defects and safety follow-up |
| **Operational Task** | Vehicle/driver/project assignment and operational output |
| **Company Classification** | Public-works company classification record |
| **Vehicle Make / Model** | Fleet reference data |

Supporting child tables hold vehicle documents, job-card parts/labour/costs,
photos, inspection items and restricted driver compliance history.

**TP Settings** remains the configuration area for fleet-specific defaults and
operating policies: per-Company department, Cost Center and parts Warehouse;
driver/employee rules; compliance policies; and reminder windows. It does not
replace the new app-wide **Sotrama Settings**. Standard Company, Warehouse,
Cost Center, Department and Employee records remain the source of truth.

## Reports and printing

The module includes the standard Script Reports **Fleet Cost Analysis** and
**Upcoming Document Expiries**. They declare their reference DocTypes, use
Company/Vehicle/date filters where applicable, and use permission-aware access
for parent fleet records. Fleet Cost Analysis labels depreciation as an
estimate; it is not a substitute for ERPNext Asset depreciation or ledger
balances. Its maintenance cost fields currently use the Frappe site's default
currency, so compare legal entities only when their fleet cost data shares that
currency. Company-specific multi-currency conversion is not yet implemented.

Maintenance Job Card and Vehicle Inspection ship with standard Frappe Print
Format defaults using the **Print Format Builder Beta** (`format_data`). To
customize one without editing app files, duplicate it from the Print Format
list and edit the resulting site-owned copy in the standard Print Format
editor. Sotrama does not pin a PDF renderer in its source files. Frappe 16.60
uses Chrome for Builder Beta formats by default, while supported alternatives
can be selected on a site-owned copy. Frappe 16.60 also improves report
printing with a full-page preview and server-rendered report output.

## Navigation and permissions

- **Sotrama** is the app workspace and home route (`/desk/sotrama`).
- **Algerian Localization** and **TP** are separate Frappe modules with their
  own standard Workspace and Sidebar records.
- The app Dock exposes both module sidebars.
- App visibility is controlled by `sotrama.permissions.has_app_permission`;
  visibility does not grant DocType permissions. Normal Frappe role and
  document permissions still apply.
- Report Company filters accept the exact Company name without expanding
  Fleet Manager's permissions on the standard Company DocType. Vehicle filters
  remain linked to the permission-controlled Vehicle register.
- Only System Manager can change Sotrama Settings. Accounts Manager can read
  the settings page but cannot change its options.

On upgraded Frappe sites that still use the legacy Desktop icon grid, a System
Manager can open **Desktop Settings** and select **Apps** as the Desktop Page
to show installed apps alongside ERPNext and Frappe HR.

## Compatibility

- Frappe Framework `>=16.60.0,<17.0.0`
- ERPNext `>=16.60.0,<17.0.0`
- Frappe HR / HRMS `>=16.60.0,<17.0.0`
- Python `>=3.14,<3.15`
- Node.js 24 is required by the Frappe v16 Bench asset toolchain; Sotrama
  itself currently has no Node.js package dependencies or bundle build.
- Sotrama version: **1.3.1**

The minimum version reflects the v16.60 platform baseline. It does not mean
that an existing site has been upgraded: verify the installed versions with
`bench version` before installing this release. Sotrama does not currently
implement Algerian payroll statutory calculations; payroll rules must not be
assumed compliant without a separate legal and accounting validation.

## Installation

Install the app in a Bench that already has compatible ERPNext and HRMS apps:

```bash
cd ~/frappe-bench
bench get-app https://github.com/aa790933/sotrama
bench --site your-site install-app sotrama
bench --site your-site migrate
```

Sotrama currently has no Node.js frontend bundle or third-party JavaScript
dependencies. It deliberately does not ship a `package.json`: Bench runs
`yarn install` for every app that contains that file, and an empty manifest
would create an untracked `yarn.lock` in the cloned app repository on install.
That makes `bench update` reject the app as locally modified. The app's
Python package metadata and version are defined only in `pyproject.toml` and
`sotrama/__init__.py`.

For an existing installation, pull the published app revision and run the
site migration after taking a backup. Do not enable optional Company fields
until any existing custom fields have been reviewed.

## Upgrade and data safety

- Standard Frappe DocType JSON, hooks, patches, Workspaces and
  Sidebars are used. Frappe 16.60 registers app modules declared in
  `modules.txt` during migration; Sotrama does not maintain a parallel module
  registry or patch the framework's Module Def lifecycle.
- Optional Company fields are created only by explicit opt-in. They are not
  imported through Custom Field fixtures or synchronized during migration.
  Saving Sotrama Settings is the only operation that applies the optional
  Company extension.
- Existing Company fields are never automatically converted between field
  types. In particular, formatted text such as `2 897 268 000.00 DA` must not
  be cast directly into a Decimal/Currency database column.
- Disabling the Company extension hides fields without deleting data.
- The uninstall hook preserves Company fields by detaching them; it never
  deletes their metadata or values.
- Fleet policies and defaults remain in TP Settings; application-wide options
  belong in Sotrama Settings.
- Always back up the site before upgrading Frappe apps or Sotrama. Upgrade the
  framework, ERPNext, HRMS and dependent apps as a compatible set.
- Uninstalling an app through Frappe removes its app-owned DocTypes and their
  records. The Company extension is specifically preserved, but Fleet records
  and Sotrama Settings are app-owned data and must be exported/backed up before
  uninstalling Sotrama.
- Do not add an empty `package.json` just to store the app version. If Sotrama
  later adds a real JavaScript build or runtime dependency, add a deliberate
  manifest and commit its lockfile so Bench's automatic Yarn install remains
  reproducible and does not dirty the app checkout; remove the `yarn.lock`
  ignore entry at that point.
- Bench enables maintenance mode and pauses the scheduler before pulling app
  repositories. If an update exits early because a repository is dirty, Bench
  may not reach its normal cleanup. After resolving the repository issue,
  inspect `sites/common_site_config.json`; if either flag was left enabled,
  restore them with `bench set-config -g maintenance_mode 0` and
  `bench set-config -g pause_scheduler 0`, then run `bench restart`.

## Development checks

From the app repository, run the static checks and packaging build:

```bash
python -m ruff check sotrama
python -m compileall -q sotrama
python -m build --wheel
```

Frappe integration tests run inside a separate disposable Bench/site:

```bash
bench --site test-site run-tests --app sotrama
```

Do not run integration tests against a production site.

## License

MIT
