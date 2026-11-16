# Research Output Issues

Review date and resolution verification: 2026-10-11. Scope: the current eight figures and five tables in AnaSOP Section 8, plus three unplanned historical workbooks found in the formal table directory. This review checks consistency and presentation of the existing descriptive evidence; it does not rerun estimation or certify causal identification.

## Issues

No unresolved issues remain from the 2026-10-11 critique. The three consistency issues were resolved under MILI-D-20261011-046; their original descriptions are preserved in `data/exp/output-handoff-reconciliation/issues_before_revision.md`.

| # | item | type | severity | description |
|---|---|---|---|---|

## Resolved Issues

| # | item | original severity | resolution and verification |
|---|---|---|---|
| 1 | Historical baseline-only national, regional and prefecture tables | minor | The three workbooks were archived under `data/exp/figure-table-generation/historical-baseline-tables/`, with original paths, cohort counts, unchanged checksums and workbook readback checks. Five historical producers now export into separate version-specific `regenerated/` directories. The active inventory contains exactly the eight planned figures and five planned tables, with no missing or unplanned outputs. |
| 2 | Potential mismatch map caption and generator | minor | Both the saved caption and its generator now state that current municipal comparisons use validated UMD screening with unchanged geography, fiscal and traffic inputs. A reproducible caption-only command checks source provenance and retains the accepted PNG. The saved caption equals the generated text; the caption and script hashes and additional caption dependencies are recorded. |
| 3 | AnaSOP completion status | minor | Sections 7-8 now report completed generation, human review and critique. The earlier UMD numerical checkpoint explicitly distinguishes its historical state from subsequent accepted outputs. Sections 1-6, the thirteen plan rows, model choices and interpretation limits remain unchanged. Updated text is English. |

## Severity Summary

Counts refer to unresolved issues after verification.

| severity | count |
|---|---|
| critical | 0 |
| major | 0 |
| minor | 0 |

## Resolution Verification

- All eight figure PNGs, five current workbooks and five table previews retain their original hashes. Other captions remain unchanged. No model was rerun and no raw or processed data were modified by the correction workflow.
- Thirty unique current data/estimate dependencies pass independent checksum comparison with accepted generation records. The corrected caption agrees exactly with its current generator and uses the matching independently validated UMD municipal source.
- The archived workbooks retain their original hashes and readback values. Historical export destinations are separate from both the active handoff and the preserved archive originals.
- `data/exp/output-handoff-reconciliation/current_output_manifest.json` explicitly identifies all thirteen active outputs, their captions, dedicated scripts, acceptance records and source hashes. `data/exp/output-handoff-reconciliation/validation.json` records the checks. The local reconciliation script is `src/analyses/reconcile_research_output_handoff.py`.

## Review Coverage and Findings

All eight current PNGs were inspected directly. The five active workbooks and three archived historical workbooks were read using the required local inventory and archive readback workflows. The thirteen dedicated current output scripts and their relevant plotting, geometry, estimator and aggregation dependencies were reviewed. All eighty-four analysis scripts additionally received full-file syntax, import and input-path inspection; historical scripts were not all given a fresh substantive statistical audit. The correction workflow ran the caption-only generator and archive/validation script; no estimation program was run. The five revised historical producers were inspected for export-path changes and preservation of their estimator functions.

The required inventory is `data/exp/critique/output_inventory.json`. Its updated static script records contain eighty-four source hashes and syntax results. All thirteen planned output hashes agree with accepted generation records. All five planned table dimensions agree with Section 8 after excluding display headers and footnotes from the stargazer-style national table. There are no missing planned outputs.

| Current item | Checks and assessment |
|---|---|
| Spatial Distribution of Key Variables | Four panels display mean road density, population and radiance, and the four selected source-location facility categories. Display transformations and zero colors are disclosed. Source checks verify that the retained basic-map cohort and non-land variables agree exactly with the UMD model cohort. |
| Regional Road Associations | Nine transportation-statistics regions; narrow forest panel and larger map; both models use the same regional sample. Coefficients and full individual confidence intervals are legible. The stepped connectors are visual comparisons, not tests of model differences. |
| Prefecture Road Associations | All forty-seven prefectures are represented. Current UMD estimates include Tokyo and Nara. Nuisance-control omissions are disclosed; unavailable omitted slopes are not assigned zero. Forest and map layout matches the regional figure. |
| Local Road Associations across Japan | Current extended geographically weighted pooled coefficients at the selected five-kilometre radius. Actual mesh rectangles, unavailable fits, true zero slopes and color saturation are distinguished in the caption. No local significance surface is claimed. |
| Local Road Association Estimation Support | Separate appendix map preserves the same footprint. It distinguishes estimable neighborhoods with at least thirty records, twenty-four estimable neighborhoods below that threshold, and 26,070 unavailable fits. Thirty records correspond to six five-period meshes, not thirty independent spatial units. |
| Spatial Distribution of Potential Mismatch | Both maps retain the full analytical footprint; the second colors only the 66,097 candidates by UMD context. Supported comparisons, unavailable screening, true radiance zeros and candidate denominators are disclosed. The previously stale municipal-status sentence is now synchronized with validated UMD municipal results. |
| Potential Mismatch by Land Context | Candidate fractions use supported meshes as denominators; zero-radiance fractions use candidates. Five displayed contexts match the accepted plan. Barren and Incomplete coverage are omitted only from this figure and remain in underlying evidence. |
| Municipal Mismatch, Traffic and Fiscal Context | Three original-scale scatter panels on a two-by-two canvas. Dashed fitted lines, Spearman coefficients, Pearson coefficients, conventional p values and pairwise sample counts are present. The fourth slot is intentionally empty. The caption explains the limitations of these descriptive fits and p values. |
| Analytical Variables and Sample Coverage | Twenty-two rows and nine columns; final variable roles, units, source timing and coverage are represented. Historical source construction remains distinguishable from the active UMD role selection. |
| National Road Associations | Thirty-four semantic body rows and three columns. Baseline and extension use the same cohort. Coefficients, mesh-clustered standard errors, significance notation, sample sizes and ordinary pooled R-squared are present. Empty baseline control cells denote excluded terms, not zero estimates. |
| Regional Road Association Comparison | Nine rows and six columns; two road coefficients with confidence intervals, mesh counts and model-specific R-squared. Full regional coverage agrees with the plan. |
| Prefecture Road Association Comparison | Forty-seven rows on one table, six columns. Every prefecture is retained. Constant/redundant added-control omissions are recorded without suppressing identifiable road slopes. |
| Municipal Mismatch, Traffic and Fiscal Correlations | Eight rows and nine columns; overall and seven land-context scopes. Four Spearman correlations have outcome-specific paired-government counts. Barren correlations remain unavailable with zero pairs. Context fractions are related to whole-government outcomes, as stated in the notes. |

Current administrative estimation uses original-scale pooled OLS with an intercept and no fixed effects. Baseline and extension have identical area-specific samples. Mesh-clustered CR1 uses actual retained rank. The UMD local estimator identifies mandatory roads and population against the supported nuisance span and records unavailable fits and omitted controls. The inspected code does not resolve core/control aliasing by silently deleting a substantive nuisance direction.

Some formal generators load validated, hash-protected parquet or coefficient snapshots under `data/exp/umd-*` rather than directly estimating from processed parquet. This is a frozen-results rendering workflow, not a numerical defect. The content dictionary must reference and preserve those exact intermediate dependencies, including the upstream processed data and estimation scripts; the final images and workbooks alone are insufficient for reproduction.

## Interpretation Boundaries to Carry into Writing

These are already disclosed limitations, not additional defects or requests for new analyses.

- The results describe associations and spatial heterogeneity. Negative conditional road slopes do not identify excessive roads, and individual regional confidence intervals do not establish statistically significant differences between regions.
- Nighttime Radiance proxies broader economic activity. Of 66,097 candidates, 64,034 have valid numerical zero radiance. A remote-sensing zero is not proof of zero economic activity or an unused road. Candidate membership is a relative, comparable-context screening result.
- Road-source comparability between historical supplied mesh attributes and 2024 centerlines remains a measurement boundary. Approved missing-density zero coding remains an analytical assumption, not independently verified absence of roads.
- Irregular snapshots, nearest available census years, repeated 2005 population, the 2024/2020 timing gap and replicated static facilities limit temporal interpretation.
- The five-kilometre bandwidth minimizes the approved grouped holdout criterion over forty-eight candidate radii on 985 common predictable centers, representing about 75.25 percent of tile-expansion weight. It is a conditional approximate selection, not a proven optimum for every part of Japan.
- The local surface has 357,316 estimable meshes and 26,070 unavailable vectors. Some coefficients are extreme: the stored minimum is about -9,404.49, whereas the displayed scale saturates at +/-0.30. The caption reports this distinction. Numerical estimability, neighborhood records and training fit do not establish local coefficient precision; no local significance claim is supported.
- Municipal traffic describes surveyed major roads within territories. Maintenance ratios describe own-government realized FY2023 spending, not maintenance need, deferred work or ownership-matched costs of flagged roads. The figures do not demonstrate that candidate roads caused fiscal pressure.
- Municipal Pearson p values use a conventional independence reference and do not account for spatial dependence. Land-context correlations use whole-government outcomes and varying available-pair samples; they are descriptive context comparisons rather than within-context mechanisms.

## Recommended Next Steps

- 三项轻微一致性问题均已解决，当前没有未关闭问题。可以进入 `build-content-dictionary`，将八张图、五张表、实际数据依赖、研究问题和解释边界组织为英文 `docs/actionbrief.yaml`，供后续写作使用。
- 交付以 `data/exp/output-handoff-reconciliation/current_output_manifest.json` 的十三项清单和 AnaSOP 第8节为准。三张历史表仅用于出处追溯；历史脚本重新生成的结果也保留在独立试验目录。
- 写作应围绕“道路配置与经济活动的关联具有空间差异，部分可比背景中出现高道路—低活动的潜在失配，并伴随自治体交通利用和财政背景差异”。把道路过剩及维护压力作为研究动机和待核实含义，避免写成已证实的因果结论。
