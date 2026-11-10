# Algerian legal sources and verification register

**Status:** initial register; no payroll rates in this document are approved for production.

## Source hierarchy

1. Journal officiel de la République algérienne (JORA): promulgated laws, ordinances and decrees.
2. Direction générale des impôts (DGI): current tax guidance, IRG schedules, forms and instructions.
3. CNAS: contribution rates, assessment base, declarations and employer guidance.
4. CACOBATPH: construction-sector contributions, assessment bases, paid leave and weather unemployment rules.
5. Ministry of Labour and other competent official agencies.

## Official entry points

- JORA portal: https://www.joradp.dz/
- DGI: https://www.mfdgi.gov.dz/
- CNAS: https://www.cnas.dz/
- CACOBATPH: https://www.cacobatph.dz/
- Ministry of Labour: https://www.mtess.gov.dz/

These are source portals, not proof of any individual rate or legal interpretation. For each rule, record the exact document/article, official URL, publication date, effective date, access date, calculation interpretation, reviewer and tests.

## Sources checked on 10 November 2026

- **SNMG:** JORA No. 1 (8 January 2026), Presidential Decree 26-01 of 7 January 2026, Article 1 sets 24,000 DA/month for 40 hours/week (173.33 hours/month), 138.46 DA/hour; Article 3 effective 1 January 2026. [Official PDF](https://www.joradp.dz/FTP/jo-francais/2026/F2026001.pdf).
- **IRG salaries:** DGI's official [IRG treatments and salaries page](https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires) identifies CIDTA Articles 69–73 for taxable base and Article 104 for withholding; describes the monthly progressive schedule, 40% allowance and special abatements for the 30,001–35,000 DA range (and the applicable disabled/retiree range). This page is guidance updated 26 March 2024; check subsequent Finance Laws and current form instructions before coding.
- **CACOBATPH:** its official [DAC page](https://www.cacobatph.dz/dac/?lang=fr) publishes paid leave at 12.21% employer-only and weather unemployment at 0.75% total split equally (0.375% employer and 0.375% worker). The calculation base, covered workers, declaration period and exact statutory text still need verification before activation.
- **CNAS:** no sufficiently specific current official rate/base page was verified in this pass; keep all CNAS values pending legal/source review.

## Rule review register

| Subject | Required evidence | Current status |
|---|---|---|
| SNMG and minimum wage | Presidential Decree 26-01, JORA No. 1 of 8 Jan 2026; 24,000 DA/month (173.33 h), effective 1 Jan 2026 | Source verified; legal rule record/tests pending |
| CNAS employee/employer rate and base | Current CNAS/JORA source, category and exclusions | Open |
| CACOBATPH paid leave | CACOBATPH DAC page reports 12.21%, employer-only; exact base/eligibility and legal text to archive | Agency rate located; review pending |
| CACOBATPH weather unemployment | CACOBATPH DAC page reports 0.75% total split equally (0.375% each); exact base/eligibility and legal text to archive | Agency rate located; review pending |
| IRG wage withholding | DGI salary page, CIDTA arts. 69–73 and 104; monthly progressive schedule and abatements | Official guidance located; implementation/tests pending |
| Exemptions and allowances | Exact source per allowance and contribution/tax | Open |
| G50/G29/DAS/DAC | Current official forms, schemas, due dates and scope | Open |

## Governance

Rules are initially draft, require legal/accounting review before activation, and have immutable effective dates/version identifiers. Tests must cover boundary values, rounding, eligibility, retroactivity and historical reproducibility. An update never recalculates already finalized payroll documents automatically.
