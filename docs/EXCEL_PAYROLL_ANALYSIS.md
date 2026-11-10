# Analysis of `real exemples.xlsx`

**Read:** 10 November 2026 using formula and cached-value views. This describes the workbook, not a legal validation. Employee names are masked in the supplied file.

## Inventory

| Worksheet | Size | Purpose | Formula cells |
|---|---:|---|---:|
| `10 Octobre cmpt 2026 ` | 75 × 31 | Monthly payroll calculation and reconciliation, October 2026 | 781 |
| `DAS 2026` | 69 × 40 | Annual DAS worksheet grouped by quarters/months | 485 |
| `Congée 2025-2026` | 62 × 13 | Leave/worked-days and salary-by-post worksheet | 61 |

## 1. October 2026 payroll sheet

Rows 10–73 contain 64 employee records; row 74 is the totals/report row. The sheet combines identifiers and job title with base pay, absences, bonuses, overtime, social deduction, meal allowance, taxable salary, IRG, travel expenses, net payable, CACOBATPH-related amount and a manually entered comparison salary.

| Column | Label | Formula or observed behavior |
|---|---|---|
| D | NJT | Days worked/paid in month, manually entered and not populated for every row |
| I | Sal. de base | Base salary entered manually |
| J | J/ab | Absence days; used by L |
| K | HS | Overtime hours; used by Q |
| L | Mt Absence | `I / 30 × J` |
| M | IEP | `I × D / 100` (D treated as a percentage) |
| N | PRI | `(I − L) × 10%` in visible rows |
| O | Ind Nuis | `(I − L) × 20%` in many rows; observed 10% and 5% in others |
| P | Ind Risque | Mostly manually entered 0; no uniform formula |
| Q | H.Sup | `I / 190 × K` |
| R | Sal.Poste | `I − L + M + N + O + P + Q` |
| S | Ret SS | `R × 9%` |
| T | Jouv | Days for meal allowance, often 26 |
| U | Ind Panier | `120 × T` (120 DZD/day in this workbook) |
| V | Sal Impos. | `R − S + U` |
| W | Ret IRG | Manually entered per employee; no IRG formula visible |
| X | frais Dépl | Manually entered per employee |
| Y | Salaire Unique | Manually entered per employee |
| Z | Net à payer | `V − W + X + Y` |
| AA | cacobatp | Usually `R`, but blank for some records; reference amount, not a contribution calculation |
| AB | Ord | Employee sequence/reference |
| AC | Frais Déplace | Mostly blank; included in AE |
| AD | Net lazhari | Manually entered comparison/target net |
| AE | Différence | `Z + AC − AD` |

### Worked examples (cached Excel results)

**Row 10:** base 40,000 DZD; D=25; no absence/overtime; IEP 10,000; PRI 4,000; nuisance 8,000; R=62,000; SS 5,580; meal 3,120; V=59,540; IRG 0; travel 11,456.09; net Z=70,996.09; target AD=38,000; difference AE=32,996.09. This is a large net-vs-target difference; the target field's meaning needs confirmation.

**Row 11:** base 25,000; D=11; IEP 2,750; PRI 2,500; nuisance 5,000; R=35,250; SS 3,172.50; meal 3,120; V=35,197.50; IRG 2,097.25; travel 23,399.75; net 56,500; target 56,500; difference 0. The net arithmetic is consistent with its inputs.

**Row 67:** base 95,000; D=14; IEP 13,300; PRI 9,500; nuisance 19,000; R=136,800; SS 12,312; meal 3,120; V=127,608; IRG 28,182.40; travel 50,574.40; net 150,000; target 150,000; difference 0.

### Material data and formula issues

- `Nom et Prénom` is repeated as a placeholder in all payroll rows; `N°AS`/`NIN` are repeated huge placeholder numbers. Do not import these as employee master data.
- D, J, K, T, X, W and AD are manual inputs. Missing days/inputs are silently treated as zero by formulas.
- IEP is `base × NJT / 100`. Confirm whether NJT is intentionally a percentage/day factor; D=25 gives 25% of base, not conventional daily prorating.
- Nuisance allowance varies among 20%, 10%, 5% and blank/zero. Eligibility, basis and rate should be a component/rule by worker category, not embedded in formulas.
- Q uses 190 hours as divisor. Overtime base, hourly divisor and premium multipliers are not represented; the formula may omit overtime premiums.
- S applies 9% to all R. It does not visibly exclude meal allowance or any other item; CNAS base needs legal validation and component classification.
- V is `R − SS + meal`. It assumes all R is taxable, SS deductible and meal allowance taxable. Each assumption needs DGI evidence and a separate IRG base.
- IRG is hard-coded. No progressive bracket calculation or annual/monthly adjustment is reproducible.
- Travel and `Salaire Unique` are added to net pay, but eligibility, evidence and tax/social treatment are not captured.
- AA is generally gross R; it does not calculate CACOBATPH paid-leave or weather-unemployment contributions and may mislead users by its label.
- AC is nearly empty but included in AE; clarify its meaning and why it is added to net.
- Row 74 totals: R=2,736,450; SS=246,280.50 (exactly 9% of R); meals=199,680; V=2,689,849.50; IRG=202,084.90; travel=1,039,552.19; net=3,531,816.79. These are workbook sums, not a reconciled payroll register.
- Cached values are Excel snapshots; they do not prove legal correctness or that formulas were recalculated after the last edit.

## 2. DAS 2026 worksheet

Four quarterly blocks each contain three monthly absence/salary pairs, paid-days total and quarter salary:

| Quarter | Months | Absence columns | Salary columns | Paid-days total | Quarter salary |
|---|---|---|---|---|---|
| T1 | Jan–Mar | G, I, K | H, J, L | M = 90 − G − I − K | N = H + J + L |
| T2 | Apr–Jun | O, Q, S | P, R, T | U = 90 − O − Q − S | V = P + R + T |
| T3 | Jul–Sep | W, Y, AA | X, Z, AB | AC = 90 − W − Y − AA | AD = X + Z + AB |
| T4 | Oct–Dec | AE, AG, AI | AF, AH, AJ | AK = 90 − AE − AG − AI | AL = AF + AH + AJ |
| Annual | — | — | — | — | AM = N + V + AD + AL |

The constant 90 presumes 30 days/month for a quarter. It is not automatically actual calendar days, paid workdays, contract days or correct for every entry/exit date. Absences are manual; salary cells are manual/values rather than linked to monthly payroll.

**Major reconciliation warning:** rows 57–61 have totals and comparisons with large negative differences and inconsistent signs. Cached row 57 has H=989,067.35, J=1,028,093.83, L=1,046,363.48, N=3,063,524.66; row 59 has H=7,389,569.35, J=7,461,003.43, L=7,208,776.95, N=22,059,349.73. Row 61 uses `H57-H59` (−6,400,502) but `N59-N57` (+18,995,825.07), reversing the sign for quarter totals. Similar inconsistencies occur in T2/T3. Identify what rows 57/59 represent and repair the reconciliation before relying on DAS totals.

The sheet does not visibly calculate annual taxable salary or IRG; it aggregates monthly salary amounts. DAS legal definitions, coverage and official export schema still need mapping.

## 3. Leave 2025–2026 worksheet

Rows 6–57 contain four employee groups and totals. Fields include hire date, a second date, NJT, social-security number, name, job, base salary, annual leave days (`J/ab`), monthly days (`J MOIS`), worked days (`j trv`) and `Sal.Poste`.

- Worked days are `L = K − J`.
- M is often a manually entered amount. Examples show differing ratios (21,500 → 31,390 for 26 days; 26,000 → 33,800; 24,000 → 31,200), so no single universal formula can be inferred.
- Group subtotals use `SUBTOTAL(9, ...)`. Grand total row 58 gives L=994 and M=1,178,197.62. Row 60 uses `SUM(M6:M57)` and returns 2,356,395.24, double the subtotal because it includes group subtotal rows. This is a **double-counting formula defect**.
- Rows 6–17 repeat the same masked employee/job; likely period segments, but their meaning is not explicit.
- Dates and NJT values are incomplete/inconsistent. Leave accrual, carry-forward, calendar vs working days and salary reference period are undocumented.

## What Sotrama should model after review

1. Import employee references by stable HRMS Employee ID, never name alone; retain source row and period for audit.
2. Store monthly inputs structurally: attendance, absences, overtime by category, components, meal days, documented expenses and approved adjustments.
3. Maintain independent effective-dated component classifications for CNAS, CACOBATPH paid leave, CACOBATPH weather unemployment and IRG.
4. Use pure backend functions, Decimal, explicit rounding and validated day/hour denominators. Persist input and rule-version snapshots.
5. Treat October as a baseline comparison and generate row-level variance. Do not turn hard-coded IRG/travel/target values into legal rules automatically.
6. Correct DAS row 57/59 reconciliation and leave subtotal double counting in a separate clean workbook before using totals as acceptance criteria.

## Accounting/payroll questions to resolve

- What exactly is NJT, and why does IEP use `/100`?
- What are the definitions/rates for IEP, PRI, nuisance, risk, overtime, meal, travel and `Salaire Unique` by job/contract?
- Is 190 hours the right divisor for each worker type? Which overtime multipliers apply?
- Does `AD Net lazhari` mean agreed target net, fixed monthly net or reconciliation value?
- Why is CACOBATPH represented by gross R in AA? Which contributions are actually withheld or employer-paid?
- Are rows 57/59 in DAS actual vs expected/previous year? Why does row 61 reverse annual-quarter sign?
- Is the 1.30/1.46 salary factor a leave salary rule, bonus or manual amount? Why does row 60 double row 58?
