# Project context and discovery record

**Audit date:** 10 November 2026
**Repository:** `aa790933/sotrama`
**Branch:** `main`
**Initial commit:** `9449cbe3bc851411a5b671a21dd1867d0ab70713`

## Goal and boundaries

Sotrama is a separately installable Frappe app for Algerian localization and the operational needs of public works, construction, quarries, roads/VRD, transport and services. The company context is a parent company with two subsidiaries, factory and quarry activity, road works, and monthly and chantier workers. The owner uses English in the ERP interface; employee-facing labels and documents should use French, with Arabic and RTL support where appropriate.

The app must extend Frappe, ERPNext and HRMS using supported hooks, APIs, DocTypes, fixtures, reports, print formats and patches. Their source code must not be forked or directly modified. Legal payroll calculations belong in tested backend code and versioned rule records. Existing payroll configuration and employee records are protected.

## Previous environment work (conversation memory; not independently re-executed here)

- WSL reported versions on 9 November 2026: Frappe `16.55.2`, ERPNext `16.54.0`, HRMS `16.53.1`, CRM `16.0.2`.
- The old site was named `sotrama`. It is a reference-only environment; no commands in this audit changed it.
- Payroll components reported as already present: `BASE`, `PRIM`, `ANC`, `EXP`, `PAN`, `TRAN`, `ADV`, `ABS`, `CNAS_S`, `CNAS_E`, `IRG`.
- Read-only verification in the old site on 10 November confirmed `Structure BTPH Standard` exists, is submitted (`docstatus=1`), active, DZD, for `SARL SOTRAMA TEBESSA`; two submitted Salary Structure Assignments point to it (`HR-SSA-26-11-00001` and `...00002`). This supersedes the earlier uncertainty about whether the structure was eventually submitted.
- The saved structure contains earnings `SB`, `ANC`, `PAN`, `TRAN`; deductions `SS_BASE`, `CNAS_S`, `CACO_S`, `IRG_B`, `IRG_BRUT`, `IRG`; employer contributions `CNAS_E`, `FNPOS`, `CACO_E`, `CACO_CP`. Actual formulas/flags were read without writes: `SB=base` (payment-days on); `ANC=SB*0.01*floor(days since joining/365)` (payment-days off); `PAN=0` and `TRAN=0` (payment-days on); `SS_BASE=gross_pay-PAN-TRAN`; `CNAS_S=SS_BASE*0.09`; `CACO_S=SS_BASE*0.00375`; `IRG_B=SS_BASE-CNAS_S-CACO_S`; `IRG_BRUT` progressive formula; `IRG` 40% abatement/min-max and 30,001–35,000 smoothing; employer `CNAS_E=(gross_pay-PAN-TRAN)*0.25`, `FNPOS=*0.005`, `CACO_E=*0.00375`, `CACO_CP=*0` (placeholder, zero).
- The actual `ANC` formula was corrected to remove `Depends on Payment Days` after the structure validation error. The final structure is present despite earlier failures during setup.
- `~/dz_setup/01_components.py` and `02_structure.py` exist. `01_components.py` was executed and components/formulas persisted (verified in DB). `02_structure.py` was executed and the submitted structure/assignments above are verified. `03_masters.py` was created but no execution was found in shell history; treat it as **not executed**. Its Employment Types, Designations, Departments, Branches, Leave Types and Custom Fields are proposals only.
- Previous discussion considered employee CNAS 9%, employer CNAS 25%, social works 0.5%, CACOBATPH paid-leave 12.21% and weather unemployment 0.375% on each side. These are **historical working assumptions**, not legal approval or confirmed current rules.
- IRG was not confirmed as a successfully configured final formula. Statistical bases were discussed but not executed as a verified completed setup.

## Current repository and local tools

- Git remote: `https://github.com/aa790933/sotrama.git` (fetch/push).
- At discovery, the repository had one 9-byte README and no scaffold. The current `main` working tree contains uncommitted scaffold/audit changes; `origin/main` remains at the initial commit. Nothing has been committed or pushed.
- Windows Python: `3.15.0`; pip `26.2.1`; Bench is absent on Windows. Python 3.15 is not the target runtime for Frappe.
- WSL Ubuntu: system Python `3.12.3`, Bench `5.31.1`; bench directory `/home/frappeuser/frappe-bench` exists. Its environment reports Frappe `16.55.2`, ERPNext `16.54.0`, HRMS `16.53.1`. Site directory `/home/frappeuser/frappe-bench/sites/sotrama` exists. Its site config and database were not opened or changed.
- The old site's live payroll configuration, MariaDB contents, Redis health and integration behavior remain unverified. No DB/site commands or migrations were run. No real employee names/IDs were copied into Git.

## Source data

The uploaded `real exemples.xlsx` was read directly. It contains three worksheets: `10 Octobre cmpt 2026 `, `DAS 2026`, and `Congée 2025-2026`. It has real operational examples but employee names are masked in the supplied file. Detailed formula interpretation and reconciliation warnings are in [Excel payroll analysis](EXCEL_PAYROLL_ANALYSIS.md).

## Evidence labels

- **Observed now:** repository state, workbook cells/formulas/cached results, command output.
- **Reported earlier:** WSL app versions and prior setup actions described above.
- **Unverified:** current law/rates, old site's live configuration, saved Salary Structures, correctness of historical Excel totals, compatibility with Frappe 16 and HRMS 16.
- **Still unverified after read-only inspection:** legality of the saved formulas; actual Salary Slip results for production inputs; whether the two assignments were used in submitted slips; and the correctness of Excel annual totals.

## Safety and data handling

Do not migrate, reset, install, update, or write to the old `sotrama` site as part of this repository work. Do not include production databases, credentials, employee personal data, or payroll exports in Git. All future migration work must be designed around backups and a separate test site.
