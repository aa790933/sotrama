# Roadmap

## Stage 1 — Audit & discovery (in progress)

- [x] Record repository, branch, remote and initial commit.
- [x] Read the uploaded payroll workbook and identify formulas and reconciliation issues.
- [x] Record prior payroll setup outcomes separately from proposals.
- [x] Locate WSL Bench and verify installed Frappe/ERPNext/HRMS versions; confirm the old site directory exists without opening or modifying it.
- [ ] Verify official Algerian legal sources and current effective rules.
- [x] Confirm HRMS 16.53.1 Salary Slip regional deduction and employer-contribution hooks from installed source.

## Stage 2 — Foundation

- [x] Add independent Python/Frappe app package skeleton, four modules, legal-source/rule DocTypes and payroll-audit metadata.
- [x] Add baseline docs, license, ignore rules and CI checks.
- [ ] Validate app packaging with Bench and install on a disposable compatible site.
- [ ] Add app fixtures/workspaces and role/permission design after version verification.
- [ ] Add install, migration and smoke tests in a MariaDB/Redis-backed CI environment.

## Stage 3 — Sotrama Core

- [ ] Company/Algeria settings and configuration validation.
- [ ] Effective-dated, source-linked legal rule DocTypes and review workflow.
- [ ] Reference data import/update with stable identifiers and aliases.
- [ ] Audit log and rule-version retention.

## Stage 4 — Algeria Payroll

- [ ] Inspect HRMS regional payroll hooks and Salary Slip lifecycle.
- [ ] Component legal classifications and independent CNAS/CACOBATPH/IRG bases.
- [ ] Pure calculation functions, rounding policy and effective-dated rules.
- [ ] Compare against reviewed Excel cases and official legal examples.
- [ ] Payroll audit, variance reports and historical rule snapshots.

## Stage 5 — Compliance

- [ ] Verify current G50/G29/DAS/DAC requirements and official formats.
- [ ] Obligation calendar, input validation, preparation and export.
- [ ] Reconciliation and approval workflow; no unreviewed automatic filing.

## Stage 6 — HR & BTPH

- [ ] Professional designation dictionary and legacy aliases.
- [ ] Employee/chantiers assignments and history.
- [ ] Equipment/site activity references and reports.

## Stage 7 — UI and print formats

- [ ] French-first labels and documents; Arabic/RTL where required.
- [ ] Separate workspaces, dashboards and operational reports.
- [ ] A4 payslip/attestations and declaration templates with PDF tests.

## Stage 8 — Release

- [ ] Clean install and upgrade tests on disposable sites.
- [ ] Permissions/security review and backup/restore rehearsal.
- [ ] Full test suite and CI green; compatibility matrix and changelog.
- [ ] Release tag and installation/upgrade instructions.

## Current release status

`0.1.0` is a scaffold version only. No Algerian legal payroll computation, declaration export or production workflow is released yet.
