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

## Compatibility

- Python: **3.14**
- Frappe Framework: **16.60.0 or later, below 17.0.0**
- ERPNext: **16.60.0 or later, below 17.0.0**
- Frappe HR (HRMS): **16.60.0 or later, below 17.0.0**

The current source review was checked against Frappe **16.60.2**, ERPNext
**16.60.0** and HRMS **16.60.0**. HRMS 16.60 requires Frappe 16.60.0 or later.
The latest published release is **1.3.5**. The current unreleased development
tree is **1.3.6** and must not be treated as a production release until its
site-level migration and permission checks have been completed.

## Architecture and source of truth

Sotrama links to the standard ERPNext / Frappe HR records wherever they exist:

- `Company`, `Employee`, `Department`, `Project`, `Asset`, `Item`, `Supplier`,
  `Warehouse`, `Cost Center` and `Stock Entry` remain authoritative.
- Maintenance stock consumption uses ERPNext Stock Entry and its normal
  valuation/accounting pipeline.
- Drivers may link to the authoritative HRMS `Employee` record; Sotrama does
  not create a parallel employee register. Only HR Manager/System Manager can
  change the link; Fleet Manager and Workshop users are not granted broad HRMS
  Employee read access.
- Job titles use Frappe HR's standard `Designation` master. Sotrama does not
  introduce a parallel position or job-title DocType.
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
A legacy `custom_nif` field from an older installation is hidden, not deleted,
only after an ownership-verified, conflict-free migration. Sotrama copies its
values into standard `Company.tax_id` only when the field metadata proves Sotrama
ownership and the standard Tax ID is empty; the update is conditional so a
concurrent Tax ID change cannot be overwritten. Existing Tax IDs are never
overwritten. Conflicting values, unowned legacy fields and unresolved schema
cases remain visible/untouched and are reported in Error Log for manual
reconciliation. The legacy field and its original values are retained.

### HR — Public Works Designations

Sotrama can optionally add the company's curated **202-title French BTPH
catalogue** to the standard Frappe HR `Designation` master. Open **Sotrama →
Company Registration & HR Job Titles Settings**, check **Create Missing BTPH
Designation Records**, and save. When the setting is enabled, the **HR Job
Titles → Create Missing BTPH Job Titles** form action can also be used later
to add newly introduced catalogue entries without toggling the setting. This
creates job-title master records only;
it does not create Employees, Drivers or employee assignments. The app creates
only missing records and keeps existing Designations unchanged. The option is
off by default; disabling it later does not delete records already used by
Employees. HR users continue creating, editing and assigning titles through
the standard **Human Resources → Employee → Designation** screens.

The catalogue follows the job titles supplied for the company, with exact
duplicate entries removed. It covers management, BTPH site operations, heavy
equipment, transport, workshops, engineering, laboratories, HSE, roads and
asphalt, concrete plants, quarries, VRD and utilities, logistics, HR and
accounting. No generic work-family labels are written into HRMS's optional
Description field; HR can enter accurate job descriptions and Required Skills
for each role using the standard Designation form.

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

On a draft Maintenance Job Card, the **Add Entry** toolbar group names the
record type explicitly: **Add Spare Part (Item)** selects an ERPNext stock
Item, **Add Mechanic (Employee)** selects an active Frappe HR Employee, and
**Add Other Cost** records a separate expense. The table headings explain
where each record comes from and how it affects stock or maintenance costs.
Part and labour line amounts and job-card totals recalculate as quantities,
hours, rates or additional costs change; removing a line recalculates the
totals too. The server verifies that a selected mechanic belongs to the same
Company as the work order. Server-side validation remains authoritative when
the document is saved or submitted. Vehicle Inspections also provide an explicit **Add
Inspection Check** action alongside the standard checklist loaded for new
inspections.

Workshop employee selection uses a restricted server-side lookup: Fleet Manager
and Workshop users see only active Employee names, IDs and job titles for a
Company whose vehicles they can access. They are not granted broad read
permission on HRMS Employee records or access to employees' personal
information.

#### Fleet security and audit controls

- Driver data is separated by need-to-know: Fleet Manager can see approved
  operational contacts and driving eligibility (licence category/expiry),
  while licence number, residential address, hire date, date of birth, national ID,
  medical/training/professional-certificate records and the HRMS Employee link
  remain HR-only. Workshop sees only base driver identity/company/status, not
  elevated fields. The Employee link is editable only by HR Manager/System
  Manager; linking an Employee does not copy personal mobile numbers or
  personal email into Fleet-visible fields. Review existing Driver operational
  contact values created by older versions before granting Fleet access; the
  app does not erase them automatically because they may be approved company
  contacts.
- Files attached to Driver records or Driver compliance rows are forced into
  private storage. Frappe's File download controller is extended through the
  supported `extend_doctype_class` hook so non-HR users cannot download these
  files, even if a file was previously public or detached. Existing local files
  are migrated to private storage. Existing remote links are removed from the
  attachment list and attachment comments. Where the URL is stored in an
  HR-only Attach field, that field retains it for HR review; otherwise HR must
  recover/re-upload the document. The migration records remote attachments in
  Error Log. File list/search, Driver form docinfo, attachment logs and the
  attachment gallery also suppress this metadata for non-HR roles, with
  server-side File read/download checks as a second layer.
- Vehicle and Driver Company ownership becomes immutable after submission.
  Inter-company transfers need a controlled transfer process; changing the
  Company field directly would rewrite the context of historical Fleet/HR
  records.
- Road-licence fields are optional on Driver records so off-road public-works
  equipment operators are not incorrectly treated as regulated road
  transport drivers. A Transport Operational Task records whether it is for
  **Compte d'autrui** or **Compte propre** and requires an explicit regulatory
  applicability decision before submission. A pending decision blocks submit;
  a confirmed regulated activity requires a current licence
  number/category/expiry. When **Require Professional Certificate for
  Transport** is enabled (default), it additionally requires the professional
  certificate and current medical/drug-screening clearances. A decision that
  own-account or other transport is not subject to those rules requires an
  authority reference, decision date and evidence attachment. The app does not
  infer the legal treatment of own-account hauling; confirm it with the
  competent Algerian transport authority.
- An open Breakdown Incident or uncleared safety-critical inspection prevents
  a Vehicle from returning to service or being cancelled. Critical inspections
  require a passing follow-up rather than cancellation; unresolved breakdowns
  require a recorded resolution date and notes. Workflow-managed status and
  restoration fields are validated server-side.
- Submitted Fleet records are retained for audit and cannot be deleted through
  normal document deletion. Draft records remain deletable.
- **Upcoming Document Expiries** is available to Fleet Manager and Workshop;
  the financial **Fleet Cost Analysis** report is restricted to Fleet
  Manager/System Manager in **Fleet Management Reports**.

Inspection checklist rows start at **Not Checked**, never at Okay. Drafts may
be saved while an inspection is in progress, but submission is blocked until
every checklist item is explicitly marked Okay or Defective; defective items
require remarks. Overall status is calculated from the completed checklist:
Pass for all-Okay results, Conditional Pass for non-critical defects, and Fail
for safety-critical defects. The server repeats these checks before submission.

**TP Settings** remains the configuration area for fleet-specific defaults and
operating policies: per-Company department, Cost Center and parts Warehouse;
driver/employee rules; compliance policies; and reminder windows. It does not
replace the new app-wide **Sotrama Settings**. Standard Company, Warehouse,
Cost Center, Department and Employee records remain the source of truth. The
primary Company and per-Company defaults are restricted to System Manager
because TP Settings is a global singleton; Fleet Manager receives only the
defaults returned for a Company they may access when they have permission to
create the target Fleet record. Raw TP Company Defaults child-table list/value
queries and generic TP Settings list queries are blocked for lower roles;
single-value RPCs enforce the same field permlevels as the Desk form. DocShare
sharing of these protected settings records and Company-scoped Fleet records is
blocked for every role, including System Manager; use Company User Permissions
instead. Legacy shares are removed during migration so shared-record query paths
cannot bypass the policy.

Scheduled Fleet reminders are assigned only to an enabled role user who can
read the referenced Vehicle, Maintenance Schedule or Driver under that user's
Company permissions; otherwise they remain assigned to Administrator. Driver
licence numbers never appear in Fleet ToDos, and safety-training or professional
compliance reminders are routed to an authorized HR Manager. Breakdown links on
Maintenance Job Cards are workflow-managed and must match the same Vehicle and
Company. The next `bench migrate` also sanitizes and reassigns legacy generated
Fleet ToDos that were created before Company-aware routing. The restricted
Employee name/designation lookup is limited to the target Fleet workflow and
checks the applicable Company scope for the target record, Employee and Vehicle;
it does not grant Fleet Manager or Workshop general Employee read access.
The primary Company Link is returned only through the target Fleet DocType's
Company User Permission scope; this does not grant general Company read access.
Server-side Link validation also checks read access to the exact linked Vehicle,
Driver, Project, Inspection, Schedule, Item, Warehouse, Cost Center, Department
or Company Classification, and applies that linked DocType's own Company scope
where applicable. A target record's Company match alone is not treated as proof
that the caller may read the linked record.

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
Format defaults using the **Print Format Editor** (`format_data`, stored as
Builder Beta layouts). To
customize one without editing app files, duplicate it from the Print Format
list and edit the resulting site-owned copy in the standard Print Format
editor. Sotrama does not pin a PDF renderer in its source files. Frappe 16.60
uses Chromium for editor formats by default, while supported alternatives
can be selected on a site-owned copy. Frappe 16.60 also improves report
printing with a full-page preview and server-rendered report output.

## Navigation and permissions

- **Sotrama** is the app workspace and home route (`/desk/sotrama`).
- **Algerian Localization** and **TP** are separate Frappe modules with their
  own standard Workspace and Sidebar records.
- The app Dock exposes role-scoped Workspace shortcuts for the Sotrama overview,
  Fleet and Algerian Localization. Frappe filters each shortcut using the
  destination Workspace permissions; the TP sidebar also filters its individual
  DocType and Report links by the current user's permissions.
- App visibility is controlled by `sotrama.permissions.has_app_permission`;
  visibility does not grant DocType permissions. Normal Frappe role and
  document permissions still apply.
- For company/branch isolation, assign standard Frappe **User Permission**
  records for the `Company` DocType to each restricted user. Fleet documents
  carry a Company Link; Sotrama explicitly checks Company User Permissions after
  deriving Company server-side, in addition to Frappe's linked-field checks and
  permission-aware list queries. Without a Company restriction, a user
  with the relevant Fleet role may see records across all Companies granted by
  that role. Every Vehicle, Driver, Operational Task, Job Card, Inspection,
  Breakdown, Maintenance Schedule and Company Classification must be assigned
  to one legal Company; assign existing unscoped records before editing or
  using them in new operations. For restrictions across all Fleet DocTypes, set
  the User Permission to **Apply To All Document Types**; otherwise Frappe's
  `Applicable For` scope is respected.
- Report Company filters accept the exact Company name without expanding
  Fleet Manager's permissions on the standard Company DocType. Vehicle filters
  remain linked to the permission-controlled Vehicle register.
- System Manager controls the Algerian Company extension. HR Manager can
  change only the level-1 HR designation option; Accounts Manager can read the
  settings page but cannot change its options.

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
- Sotrama version: **1.3.6-dev**

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
- Public-works designations are added only by explicit opt-in and are stored in
  HRMS's standard `Designation` DocType. Existing records are never overwritten
  or deleted, and turning the option off does not remove them.
- Before install, Sotrama repairs only an unplaced, non-custom `Module Def`
  whose name is declared by Sotrama. It never changes a module owned by another
  app or a site-created custom module; Frappe remains responsible for handling
  custom-module name conflicts.
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
