# AnaSOP
Analysis Standard Operating Procedure

## 1. Research Objective

### Central Research Question

- Research question: How is road-network provision associated with economic activity across Japan, how does this relationship vary spatially, and how do potential mismatch patterns relate to observed traffic utilization and municipal fiscal context?
- Why it matters: The user-selected transportation problem is potentially excessive road infrastructure in some areas and the continuing public-finance pressure of maintaining it.
- Current support: Five-period road density, population and nighttime radiance are linked nationally. Baseline and expanded pooled and local estimates describe geographically varying conditional associations. Separate exploratory administrative summaries connect potential mismatch with surveyed traffic, realized maintenance expenditure and fiscal-resource measures; these references are not added to the radiance equations.
- Key constructs: Road Length Density represents infrastructure provision; Nighttime Radiance is used as a proxy for broader economic activity; Population, land cover and facilities describe the surrounding context. Radiance is not a calibrated measure of GDP or economic activity in every sector.
- Supporting evidence: Geographically varying road-economy associations with adequate estimation support, together with transparent descriptive comparisons of potential mismatch, surveyed traffic and fiscal context.
- Weakening evidence: Apparent mismatch reflects source definitions, light-proxy limitations, sparse predictor variation, or essential connectivity and public-service functions not captured by local activity.
- Required feasibility check: Verify proxy meaning, source comparability, spatial support and administrative coverage. Association and spatial heterogeneity are the research targets; causal identification is outside scope. No normative excess-road classification is currently defined.

### Supporting Research Questions

#### Supporting Point 1: Road provision and economic activity

- Research question: How is road density associated with economic activity proxied by nighttime radiance, conditional on population and the approved land-cover and facility controls?
- Why it matters: This establishes the empirical road-economy relationship underlying the proposed infrastructure-mismatch story.
- Current support: Same-sample baseline and expanded national pooled regressions have been completed; their road coefficients differ substantially after adding the approved controls.
- Key constructs: Road Length Density, Nighttime Radiance, Population and the selected contextual controls.
- Supporting evidence: An identifiable conditional association with defensible measurement and sample coverage.
- Weakening evidence: The pattern is dominated by road-source inconsistencies or economic activities poorly represented by nighttime lights.
- Required feasibility check: Assess the economic-activity interpretation of the radiance proxy and road-source equivalence. Coefficient attenuation alone does not identify a mechanism or a causal road effect.

#### Supporting Point 2: Spatial heterogeneity and geographic mismatch

- Research question: How do road-economy associations differ across Regions, Prefectures and local neighborhoods, and where do comparable-context meshes exhibit high road density alongside low economic-activity radiance?
- Why it matters: A national association can conceal locations where infrastructure stocks and local economic activity are poorly aligned.
- Current support: Nine regional regressions, forty-seven prefecture attempts and the expanded five-kilometre geographically weighted pooled estimates are available. Failed local fits and omitted constant-control coefficients remain explicitly unestimated.
- Key constructs: Local road-density associations, economic-activity context, population, land cover, facilities and geographic support.
- Supporting evidence: Spatial variation in estimable road coefficients and transparent mismatch summaries, with adequate neighborhood and peer support.
- Weakening evidence: Negative slopes arise from minimal road variation or proxy error, or the roads serve through traffic, access, emergency response or other needs absent from local activity measures.
- Required feasibility check: Check coefficient stability, local support, peer-group coverage and source meaning. Describe mismatch as a relative empirical pattern; a negative coefficient does not by itself identify an excessive or underused road.

#### Supporting Point 3: Traffic utilization and maintenance fiscal context

- Research question: How do surveyed traffic utilization, realized maintenance expenditure shares and fiscal-resource measures differ among municipalities with different potential mismatch fractions, and across land contexts?
- Why it matters: This is the fiscal sustainability concern selected by the user as the story's underlying policy motivation.
- Current support: Exploratory summaries cover 1,741 municipal governments, including 1,734 with usable published surveyed traffic. Actual fiscal-year maintenance and fiscal-resource references are available separately from the five-period radiance model.
- Key constructs: Potential mismatch fraction, Length Weighted 24h Volume, Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale and Single Year Fiscal Revenue Need Ratio. These remain exploratory references rather than additional radiance-regression controls.
- Supporting evidence: Documented municipal rank associations and differences across land contexts, with reported pair counts, source years and survey coverage.
- Weakening evidence: Associations are absent or differ across contexts, or are dominated by proxy limitations, survey selection, administrative aggregation or fiscal institutions. Essential network functions remain relevant to interpreting low local radiance.
- Required feasibility check: Verify code and geography linkage, dates, units and missingness. Distinguish territorial surveyed roads from roads financed by the municipality; this determines the meaning of the observed relationship rather than identifying a causal fiscal effect.

### Scope of Analysis

- Topic: Road provision relative to economic activity, potential infrastructure overprovision, and the fiscal sustainability of road maintenance.
- Target geography and unit: Japan nationwide, standard approximately one-kilometre statistical grids. Available-data coverage does not imply coverage of every land mesh.
- Analytical scope: The baseline common cohort contains 383,390 meshes and 1,916,950 observations. The approved focused extension contains 383,386 meshes and 1,916,930 observations after excluding only four meshes with unavailable land-cover data from extended estimation; original data retain their missing values.
- Geographic scope: Retain eligible islands and the nineteen previously reviewed no-land-overlap classification exceptions. No blanket island or marine-cell exclusion is introduced.
- Candidate road periods: 2002, 2003, 2004, 2010 and 2024. Matched population years are respectively 2000, 2005, 2005, 2010 and 2020; nighttime-light years match road years. The user excluded 1995; acquired historical materials remain archived.
- Temporal matching: Preserve actual source years, nearest-year offsets, the reuse of the 2005 census and the latest four-year census gap. These are irregular snapshots. Historical supplied road density and recent centerline-derived density retain unresolved source-equivalence limitations.
- Contextual scope: Annual land cover is matched to each period. Selected facility editions are repeated across periods under the approved static assumption; they do not reconstruct historical facility change.
- Fiscal scope: Maintenance pressure remains the policy motivation. The authorized administrative trial describes expenditure shares and fiscal resources in relation to potential mismatch. No causal fiscal effect, normative excess-road threshold or additional radiance-regression control is selected.

### Study Design Declaration

- Research type: applied
- Evidential objective: Present relationships and their spatial heterogeneity. Causal estimation is outside the research objective and is not a completion requirement.
- Study design: Transportation empirical research using national pooled OLS, nine transport-statistics regional comparisons, forty-seven prefecture attempts and exploratory geographically weighted pooled regression. Use the approved baseline and focused extension, original units and an intercept, without fixed effects. Administrative pooled inference is mesh-clustered; no local significance inference has been produced.
- Interpretation limit: Nighttime Radiance is an economic-activity proxy observed through nighttime light emissions. The current design estimates conditional associations, not causal road effects, calibrated GDP, transport demand, utilization, excessive provision or fiscal pressure. Potential road overprovision is the user-selected substantive concern to investigate, not a conclusion established by negative coefficients.

## 2. Theoretical Background  /  Conceptual Framework  /  Problem Formulation

### Research Gap

The applied problem is how existing road provision relates to economic activity, how this relationship varies geographically, and how potential mismatch patterns coexist with observed transport utilization and fiscal-resource differences. Potential road overprovision and maintenance pressure motivate the transportation relevance. The study addresses these concerns through association and spatial heterogeneity. A literature-based novelty claim remains to be established.

### Conceptual Framework

Road provision is a persistent infrastructure stock. Economic activity is proxied by nighttime radiance, with population, annual land cover and selected facilities describing the surrounding context. Potentially excessive provision and continuing maintenance commitments provide the policy motivation. The empirical framework describes road-activity associations and geographic variation, supplemented by territorial traffic and realized maintenance/fiscal comparisons. These comparisons characterize observed relationships rather than causal transmission mechanisms or required maintenance obligations.

Local economic activity is not equivalent to all transport demand. Through traffic, network connectivity, essential access and public-service functions can justify roads in meshes with low radiance. Road overprovision therefore requires a benchmark that incorporates relevant functions and needs. A negative conditional slope or high road density with low radiance alone does not establish inefficient infrastructure. Proxy limitations and source comparability remain competing explanations for observed mismatch.

### Problem Formulation

The observation is a geographic mesh at a road-anchored period, retaining the actual years of every input. The approved pooled equations relate Nighttime Radiance to Road Length Density and Population, with the focused extension adding the previously selected land-cover and facility controls. Estimated associations combine between-mesh differences and within-mesh changes; no fixed-effects or causal interpretation is introduced by the narrative revision. Locally constant added controls follow the approved unestimated-coefficient rule, so local retained control sets can differ.

The empirical evidence chain connects national conditional road-economy association, regional and local spatial heterogeneity, comparable-context mismatch patterns, and administrative traffic and fiscal associations. The target is describing these relationships. Five-period pooling does not establish a historical sequence of economic decline, infrastructure oversupply or worsening fiscal stress.

## 3. Data Overview

### Current Dataset Scope

The full source-derived panel contains 972,800 meshes per period, 4,864,000 records and 210 readable fields. There are 65 analytical candidates: three core variables, thirty-eight static facility measures, six annual land-cover shares and eighteen additional national land-information facility counts. The original baseline uses only Nighttime Radiance, Road Length Density and Population. The focused extension below adds selected land-cover and facility controls; the original baseline outputs are preserved.

Numerical completeness of all three core variables across five periods yields 966,400 meshes and 4,832,000 observations. The approved common analytical cohort further requires positive administrative land overlap or one of the nineteen existing reviewed no-overlap exceptions: 383,390 meshes and 1,916,950 observations. The 583,010 remaining numerically complete candidates are outside the current common cohort because they lack an approved administrative assignment. Retain all eligible islands; no blanket island exclusion is applied. All 228,988 previous model meshes and their geographic assignments are preserved.

The common cohort retains 1,048,772 zero-population observations and 191,353 meshes with zero population in every period. A separate eleven-field analysis projection contains the three core variables, mesh and actual source years, and the geographic keys and reviewed-overlap flag. The full augmented source panels remain unchanged by cohort selection.

### Time Coverage and Missingness

Road and light years are 2002, 2003, 2004, 2010 and 2024; census years are 2000, 2005, 2005, 2010 and 2020. These are irregular snapshots. The latest census offset is four years earlier, and the 2005 population snapshot is reused. Within verified census archives, source-unlisted population meshes represent structural zeros. The absent primary census archive leaves 6,400 mesh totals missing per period, or 32,000 observations in the full panel; these are outside numerical completeness.

The user-directed density-only coding makes all analytical road densities finite, including source-unlisted and source-unknown values. It is a coding assumption and does not verify physical absence of roads. Radiance has no numerical missingness in the full target panel. Facility counts have no numerical missingness under acquired archive coverage. Each of the six land-cover shares remains missing in 10,900 full-grid observations, or 2,180 meshes across all five periods, because the corresponding source tile is unpublished. Mask-identified water is retained. Land-cover completeness is not a baseline inclusion criterion.

### Measurement Boundary and Briefing Provenance

Latest road density is calculated from selected ordinary centerlines; historical density is supplied by road-grid products. Equal units and common mesh geometry do not establish equivalent road coverage. No source rescaling or calibration is applied. Latest light aggregation uses year-specific raster geography and area overlap; existing independent geometric and pilot checks remain valid. Nighttime Radiance is used as an economic-activity proxy measured through nighttime light emissions; it is not calibrated GDP or transport demand. The earlier focused briefing summarized four source inputs and twenty-five column entries, with one exploratory distribution plot; it is a historical checkpoint, not the active augmented-data scope. No new time-series visualization is selected.

### Focused Extension Availability Checkpoint

Within the 383,390 baseline meshes, all fifty-six facility candidates are numerically complete. Each of the six annual land-cover shares is unavailable in twenty records belonging to four Minamitorishima meshes. The approved focused estimation projection requires complete selected controls in all five periods and contains 383,386 meshes and 1,916,930 observations. Original augmented data retain those four meshes and their NaN values. This projection is not a blanket island exclusion. It retains 1,048,757 zero-population observations and 505 incomplete-land-cover records, without normalizing their shares or imputing unknown coverage. Static distributions are audited once per mesh; annual availability is checked across all five periods.

Four exact identities relate facility totals to their classified components. The focused equation uses totals rather than simultaneously including their component counts. The six land-cover shares partition accepted coverage; fully covered records sum to one. Their reference-category interpretation is exact for fully covered records. With partial coverage, the omitted remainder also includes unobserved area and cannot be interpreted as Other Land Cover Share alone.

### Exploratory Traffic and Fiscal Reference Audit

The authorized mismatch trial uses the existing focused extension's latest 383,386 meshes with 2024 road/light values, 2020 population and the previously selected static facility context. Screening requires at least thirty distinct meshes per coarse peer group: 374,865 meshes qualify, 8,521 have insufficient peers, and 66,088 are candidates. All original values and zeros are preserved. Of the candidates, 96.8497 percent have zero radiance and 79.7361 percent have dominant forest cover. These features limit interpretation as economic inactivity or excess infrastructure.

New exploratory references include 99,417 basic road segments from the official 2021 survey across all forty-seven prefectures; 3,413 lack published twenty-four-hour traffic. Preserve observed-versus-estimated direction flags and twelve-versus-twenty-four-hour observation codes. The survey covers major roads and selected designated-city roads, not the full local-road network. Fiscal references cover the forty-seven prefecture governments' actual 2023 financial year, despite a 2024 catalog label. They provide Road and Bridge maintenance expenditure, total expenditure and standard fiscal revenue, need and scale. Amount units are independently verified as thousand yen. These references do not change the full source panel's schema or the approved regression controls; they are not replicated across the five-period panel.

A bounded Fukuoka geometry pilot links published road-map identifiers to archived traffic tables and allocates mapped geometry to actual mesh boundaries. Its 1,008 target meshes include thirty-nine candidates; twenty-seven candidates have mapped published traffic. Geometry is a zoom-specific map representation, not an authoritative legal road inventory. Missing tile responses and unmatched traffic remain unavailable rather than zero. The traffic year predates the mesh screen by three years. The national mesh road stock is not classified by responsible road-maintenance government, and prefecture fiscal data do not include consolidated municipal finances. These limitations prevent attribution of candidate road stock to fiscal costs.

### Light-Zero Provenance and Screening Support Audit

The revised exploratory screen retains all 383,386 latest-period meshes and all original core values. Sixty peer groups contain only zero radiance, covering 154 meshes. Every such group already has fewer than thirty distinct meshes, so making their information insufficiency explicit does not change the 66,088 candidates or the 374,865 supported comparisons. Among the 8,521 unsupported meshes, 154 now carry both the all-zero-light and insufficient-peer reasons; the remaining 8,367 carry the insufficient-peer reason alone.

A deterministic diagnostic sample covers 420 meshes across the existing Regions, land contexts and candidate/light states, including additional all-zero-peer contexts. Recalculation uses 4,495 native pixel intersections from the original 2024 raster. The 222 sampled zero-radiance meshes contain only valid zero-valued source pixels; 198 positive-radiance meshes also reproduce the saved means. The maximum absolute radiance difference is approximately 1.42e-14, and no sampled intersection is declared nodata. Source metadata, archive integrity, original metric overlap weights, independent pixel-coordinate intersection membership and stored coverage pass verification. This bounded diagnostic does not estimate a nationwide error rate or audit upstream product detection and filtering.

The remaining limitation is weak differentiation of economic activity within many peer groups. A total of 314,294 supported meshes belong to groups whose lower radiance quartile is zero. Inclusive ties are retained under the existing rule. Forest-context candidates number 52,696, of which 99.9184 percent have zero radiance; urban-context candidates number 1,449, of which 5.4520 percent have zero radiance. Cropland and cropland-mosaic candidates number 1,679 and 1,260, with zero shares of 84.9315 and 88.2540 percent. Other and Water categories and incomplete-coverage cases remain represented. Three existing numerical variables are summarized, and one two-panel context-distribution figure is reviewed. This is a single cross-section; no time-series visualization is selected. Numerical source zeros are preserved and do not establish absent economic activity.

### Municipal Territorial Evidence Availability

The authorized municipal trial links the latest 383,386-mesh screening ledger to 1,741 individual municipal financial governments, including Tokyo special wards and whole designated cities. Reference boundaries are fixed at the start of 2024 and existing Prefecture assignments remain unchanged. Largest identified municipal land overlap within each approved Prefecture provides an exploratory mesh assignment. Cross-boundary meshes number 58,268. All 383,386 meshes remain represented: 383,066 link to financial governments and 320 do not, comprising 35 without identified municipal land overlap and 285 assigned to a boundary municipality absent from the fiscal-government reference. These gaps are unavailable jurisdiction links, not zero roads, zero finance or a new blanket island deletion.

Traffic references retain all 99,417 original basic-segment records. Code-first matching resolves spelling differences, and an earlier official boundary edition validates seven old designated-city ward codes before consolidation to the fiscal parent city. There are 1,734 municipal governments with usable published traffic and seven with unavailable traffic; those values remain missing. Financial data cover actual fiscal year 2023, with complete selected maintenance and fiscal-resource fields for the 1,741 individual governments. Joint administrative organizations are preserved in source materials but do not enter the individual-government comparison. Road and bridge maintenance uses two distinct purpose rows, excluding forest-road and urban-street purpose categories and entrusted-project columns. Units are verified as thousand yen.

Municipal summaries retain actual dates: roads and light in 2024, population in 2020, traffic in 2021 and finance in 2023. They are a linked cross-section and are not replicated across the five-period panel. The focused briefing reads two evidence datasets, summarizes five numerical metrics and produces one distribution figure; no time-series view is selected. Metric coverage does not identify municipality-owned road stocks or calibrate economic activity. Traffic covers major surveyed roads, while fiscal expenditure belongs to the municipality's own accounts. Twenty-eight designated-city-managed survey records occur outside designated-city fiscal territories, underscoring the difference between location and maintenance responsibility.

## 4. Variable Construction  /  Key Variables

Construction history is retained below for provenance. The active coding revisions and Approved Common Baseline Cohort subsection define the current data and sample; earlier pilot and extension statements are historical checkpoints.

### Confirmed Pilot Variables

The user confirmed the road variables, nighttime radiance construction, and total population variables and rules. Complete source-derived processing covers a Fukuoka-area rectangular pilot of 6,400 standard meshes and five candidate periods. Following the user's withdrawal of the preceding offshore exclusion, the active working data retain all 6,400 meshes in each period and 32,000 mesh-period records. The 17 previously excluded meshes are restored across all five periods. The superseded filtered result is preserved as a historical artifact; the final estimation sample remains undecided. Population processing covers the four matched census snapshots: 2000, 2005, 2010, and 2020, each retaining the same 6,400 pilot meshes. The separately preserved population snapshots are now linked to the paired road-light data by mesh identifier under the accepted five-period matching. The complete three-source candidate panel retains 32,000 mesh-period records and the thirteen previously confirmed variable and reference columns. For the current analysis, Nighttime Radiance is the outcome, Road Length Density the main explanatory variable, and Population the control. These roles do not establish cross-period measurement comparability or select a final estimation sample.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| Road Length Density | Road Length Density | main explanatory | \(D_{it}=L_{it}/A_i\), in km/km\(^2\), subject to the source's area and normalization convention. | For historical observations, convert supplied normalized length from m/km\(^2\) to km/km\(^2\) once. For the latest observation, divide allocated ordinary-centerline length by the projected full mesh area. Source inconsistencies remain flagged; the documented 2010 length reconstruction does not alter supplied density. Missing analytical density follows the active zero-coding revision below. | yes |
| Nighttime Radiance | Nighttime Radiance | outcome | \(R_{it}=\sum_{p\in V_{it}} a_{ip}r_{pt}/\sum_{p\in V_{it}}a_{ip}\), where \(a_{ip}\) is pixel-mesh intersection area and \(V_{it}\) contains valid pixels; units are nW/cm\(^2\)/sr. | Align each year's actual raster geographically. Retain genuine zeros, exclude declared nodata and nonfinite inputs, and average over valid intersection area. No imputation or logarithmic transformation. | yes |
| Population | Population | control | \(P_{it}\) is the published total number of residents of both sexes and all ages in mesh \(i\) at the actual census year, measured in persons. | Retain numeric totals without suppression-based deletion or reaggregation. For the active 2000, 2005 and 2010 censuses, encode an absent record within a verified complete first-order archive as zero. Entire-archive coverage gaps and invalid recorded totals remain NaN. Preserve separate presence, coverage and structural-zero flags; no statistical imputation or logarithm. The latest stored candidate is outside this revision. | yes |
| Region | Region | geographic stratum | \(g_i=\arg\max_{g\in\mathcal G}\operatorname{Area}(M_i\cap A_g)\), where \(M_i\) is the mesh footprint, \(A_g\) is the union of administrative polygons belonging to region \(g\), and \(\mathcal G\) is the confirmed set of nine transportation-statistics regions. | Assign the greatest positive land-intersection area in local metric projections using a frozen current administrative reference, and hold the assignment fixed across all four periods. Preserve cross-region flags. Region is a stratification variable, not an extra numeric control. | yes |
| Prefecture | Prefecture | geographic stratum | \(h_i=\arg\max_{h\in\mathcal H}\operatorname{Area}(M_i\cap B_h)\), where \(B_h\) is the union of administrative polygons for prefecture \(h\) and \(\mathcal H\) contains the forty-seven prefectures; \(M_i\) retains its earlier definition. | Refine the existing greatest-land-overlap rule directly to prefectures, hold assignment fixed across periods, and preserve cross-prefecture flags. It is a geographic stratum rather than an additional control. | yes |

### Approved Initial Pilot Estimation Subset

The current national analysis uses the corrected complete-four-period sample documented below: 228,988 meshes and 915,952 records. Retain genuine zeros, qualifying islands, original values and actual matching years. The analytical subset does not overwrite complete processed files. The latest candidate period remains stored for subsequent comparability work. No variable construction or renaming is introduced by the pooled-model choice.

### Reference Variables and Quality Rules

| variable_name | definition and construction | purpose |
| --- | --- | --- |
| Mesh Code | Eight-character standard statistical mesh identifier, stored as text. | Spatial linkage; not a numeric explanatory variable. |
| Road Length | Historical supplied total length converted from metres to kilometres, with the documented 2010 reconstruction exception; latest ordinary-centerline length allocated to mesh interiors and measured in kilometres. | Check the density numerator. |
| Mesh Area | Historical reported mesh area converted to km\(^2\); latest full mesh area measured in a local metre-based projection and converted to km\(^2\). Unknown historical areas remain missing. | Check the density denominator; physical areas vary between meshes. |
| Road Year | Actual road source observation year. | Retain irregular snapshot timing. |
| Nighttime Light Year | Actual nighttime-light observation year. | Retain source timing. |
| Nighttime Light Coverage | \(C_{it}=\sum_{p\in V_{it}}a_{ip}/A_i\), using the full geometric mesh area. Values exceeding one only within numerical tolerance are bounded at one; raw ratios remain in quality records. | Describe valid-pixel support rather than land coverage. |
| Population Year | Actual census snapshot year. | Preserve nearest-year matching and repeated use of the same census snapshot. |
| Disclosure Status | Source classification available for the latest population snapshot: 0 is outside detail suppression, 1 receives suppressed details, and 2 has suppressed details. | Describe detail-variable disclosure treatment; it does not suppress published total population. Earlier metadata are unavailable, not assumed to be 0. |
| Disclosure Destination | Text identifier of the mesh receiving suppressed detail variables, where supplied. | Preserve source disclosure linkage; do not transfer total population. |
| Merged Mesh Codes | Source-supplied text list of meshes whose suppressed detail variables are assigned to a recipient. | Preserve linkage for reference; do not add their total populations to the recipient. |

The earlier rule classified historical unknown road records and source-unlisted meshes as missing. The active density-only revision below now assigns zero to unavailable Road Length Density by human instruction. Unavailable Road Length and source Mesh Area remain NaN; original density missingness and source status remain recorded. Retain Mesh Code and Road Year, preserve separate source-presence and unknown flags for provenance, and retain genuine numeric zeros. This rule does not set available nighttime-light or population attributes to missing. No records are dropped from the complete source-derived files. The active working data retain all complete source-derived records after withdrawal of the offshore exclusion. No values are rescaled to match another period, and statistical outlier correction is not applied.

The published total population is exempt from the latest census table's detail suppression. All 282 pilot meshes flagged for suppressed details therefore retain their disclosed total populations, totaling 1,749 persons. Those detail-disclosure links are not used to reaggregate total population. Earlier basic population tables do not supply disclosure metadata, so their absence is retained explicitly. The four population outputs preserve the original published values and totals; missing counts are 3,586, 3,145, 3,144, and 3,194 meshes respectively. All missing totals in this pilot arise from source-unlisted meshes. This was the earlier source-unlisted-as-missing interpretation; it is superseded for the active historical years by the documented structural-zero rule below. These original pilot files remain historical artifacts.

### Historical Candidate Panel Linkage and Numerical Coverage

The road-anchored periods pair road/population/light years as 2002/2000/2002, 2003/2005/2003, 2004/2005/2004, 2010/2010/2010, and 2024/2020/2024. Actual observation years remain explicit. Population offsets, defined as census year minus road year, are -2, +2, +1, 0, and -4 years; their absolute gaps and the reuse of the 2005 population snapshot are preserved in matching metadata. The two uses of the 2005 snapshot retain identical population values and do not represent independent population observations.

Joint numerical availability requires finite Road Length Density, Population, and Nighttime Radiance. Genuine numeric zeros remain valid. It does not require an inland or mainland location and does not establish road measurement comparability, local model estimability, or final sample eligibility.

| Road year | Population year | Light year | Complete meshes | Jointly numeric meshes |
| --- | --- | --- | --- | --- |
| 2002 | 2000 | 2002 | 6,400 | 2,704 |
| 2003 | 2005 | 2003 | 6,400 | 3,088 |
| 2004 | 2005 | 2004 | 6,400 | 3,098 |
| 2010 | 2010 | 2010 | 6,400 | 3,206 |
| 2024 | 2020 | 2024 | 6,400 | 3,206 |

The five-period intersection contains 2,641 jointly numeric meshes, equivalent to 13,205 mesh-period records if later selected. The intersection of the four historical road periods contains 2,663 meshes. These are coverage diagnostics only. The complete candidate panel retains all 6,400 meshes in each period; no diagnostic completeness rule is applied as a row filter. Source values, missing values, and disclosure metadata survive linkage unchanged. Separate quality records preserve the distinction between unknown road attributes and source-unlisted road or population records. Cross-period road comparability and final model/sample decisions remain pending.

The preceding 17-mesh exclusion is inactive and is not reapplied when the preprocessing workflow is rerun. Island meshes, marine cells, and unknown road values remain in the working data pending final sample decisions. Restoring these records does not establish historical road zeros or resolve source coverage differences.

Following the user's instruction to resolve the 2010 source anomaly, one pilot total length is reconstructed from its eight width-class lengths: 0.003 km becomes 12.143 km. The three nonzero class lengths sum to 12.143 km and their normalized lengths sum to the supplied density of 11.325 km/km\(^2\). Division by the reported area also reproduces that density within source integer rounding. The density and area are retained. A separate erroneous width-class length is reconstructed as 1.453 km by subtracting the other classes from its consistent total; that reference repair does not change the selected grid total length or density. Original fields, source-anomaly flags, and reconstruction provenance are preserved. These are evidence-supported internal reconstructions, not official source corrections. All 3,902 numeric pilot records pass length-normalization and class-total checks after these reference reconstructions.

The latest road construction retains ordinary centerlines in normal, bridge, tunnel, and snow-cover states. Garden paths, footpaths, steps, and construction-state segments are excluded. Unknown width is retained and flagged; no common width threshold has been adopted. Zero allocated length means that the published tile contains no selected ordinary centerline in that mesh, and does not prove the absence of every road.

All five nighttime-light pilot windows provide complete valid-pixel coverage. The mean uses the complete mesh footprint, including sea where present. Existing full-data quality records retain unclassified coastal status. A diagnostic current administrative/coastline reference identifies offshore land intersections for the coverage audit. Following withdrawal of the exclusion decision, it is used as diagnostic evidence only; it has not been adopted as a complete historical land mask or as a national coastal classification rule. Earlier simulated lights remain proxies rather than independent fine-scale satellite measurements.

Length conservation and independent geometric clipping checks passed. The historical and computed mesh areas differ by less than 0.06% in the pilot. These checks establish spatial allocation and unit consistency; they do not establish equivalent road coverage across sources. The initial baseline variable roles are confirmed. Cross-period road comparability and the final national estimation sample remain unresolved. The initial pilot specification and analysis-only subset are confirmed; its estimation status is recorded separately.

### Previous National Extension of Confirmed Variables

Apply the same readable names, source construction, model roles, missing-value rules, and original scales nationwide. The national historical panel retains 972,800 meshes in each of four periods, totaling 3,891,200 records with thirteen columns. Numerical completeness across all four periods selects 134,830 meshes and 539,320 observations for this baseline only. Store the complete data independently of the analysis subset. No national coastal or island mask is applied, and qualifying island meshes remain eligible.

Native-pixel overlap geometry is shared across the four equal-layout rasters. Measure intersections in locally centered metric projections, retaining the existing pilot projection for its tile. This computation preserves the area-weighted mean definition and reproduces the pilot result within 1.6e-10. Three additional 2010 reference length-normalization inconsistencies are retained with flags; supplied Road Length Density is unchanged. No additional correction, imputation, logarithm, or density calibration is applied.

### Confirmed Regional Classification

Use the official nine-region prefecture grouping published for automobile transportation statistics: Hokkaido; Tohoku; Kanto including Yamanashi; Hokuriku-Shinetsu including Niigata, Toyama, Ishikawa, and Nagano; Chubu including Fukui, Gifu, Shizuoka, Aichi, and Mie; Kinki; Chugoku; Shikoku; and Kyushu including Okinawa. These groupings are exhaustive and mutually exclusive across the forty-seven prefectures. The geographic allocation rule is a study-specific construction rather than an official statistical mesh-assignment rule.

Freeze administrative polygons dated January 1, 2024 solely as classification references. They do not replace historical mesh areas, form a historical land mask, rescale radiance or roads, or change any substantive input. All 134,830 national baseline meshes have a unique positive-overlap assignment; 236 intersect more than one region. Preserve Cross Region Mesh, Region Land Share, land-intersection areas, and Assignment Status for geographic audit. A tied maximum or absence of positive land overlap requires review rather than automatic nearest-region assignment or exclusion. Regional assignment remains unchanged across periods.

### Prefecture Classification Extension

Interpret the requested county-level analysis as Japan's forty-seven prefectures, including the metropolis, circuit, urban prefectures, and ordinary prefectures. Refine the same largest positive administrative land-intersection rule directly to prefectures, without restricting a mesh to its previous Region before allocation. Preserve Prefecture Code as two-character text and Mesh Code as eight-character text, along with English Prefecture names, Cross Prefecture Mesh, land-overlap measures, shares, and assignment status for audit.

The same frozen current administrative reference assigns all 134,830 national baseline meshes uniquely to the forty-seven prefectures. Preserve all 1,999 cross-prefecture meshes. Aggregating the prefecture intersection areas by the official transportation grouping reproduces the prior regional area ledger within numerical tolerance. In this sample every assigned prefecture belongs to the previously assigned Region; no boundary mesh changes its implied Region. Keep the previous Region allocation and all substantive values intact. Current administrative geometry is a classification reference rather than a historical coastline mask.

### Active Historical Population Coding Revision

Restore Population to zero when an eight-digit mesh has no census record within a complete downloaded and checksum-verified first-order archive for the actual matched census year. Preserve all present numeric totals exactly. If the first-order archive is absent, or a present total cannot be interpreted as finite nonnegative population, retain missingness. A record-presence flag, archive-coverage flag, structural-zero flag, archive-gap flag and invalid-record flag distinguish these cases. Population total suppression and detail aggregation do not justify deleting or reaggregating published totals.

The current version separately stores the three corrected census snapshots and the linked four-period historical panel. Variable names, roles, years, matching, original scales and thirteen-column panel structure are unchanged. The complete-four-period rule now selects 228,988 meshes and 915,952 observations; zero population is numerically eligible. The entire-archive gap affects no otherwise eligible four-period mesh. At this earlier population-revision checkpoint, road unknown and unlisted observations remained NaN; the active density-only rule is documented below. No road-zero recoding, source calibration, population interpolation or coastal/island exclusion is introduced.

The prior pilot, national and geographic-classification diagnostics above refer to the preserved earlier population version. Existing regional and prefecture assignments cover its 134,830 meshes; newly admitted meshes need allocation under the same confirmed rule before stratified estimation. No substantive estimates or classification extension are produced by this preprocessing revision.

### Corrected Regional Classification Checkpoint

Extend the same frozen administrative reference and greatest-positive-land-overlap rule to the corrected national sample. Of 228,988 meshes, 228,969 have unambiguous regional assignments and 946 cross regional boundaries. All 134,830 previously classified meshes retain their regional labels and land-area diagnostics. Independent direct clipping verifies nine boundary combinations and nine regional interior cases.

Nineteen meshes have no positive administrative land intersection. All have zero population in the matched censuses but numerical historical road observations. The user approves reviewed nearest-land regional exceptions only for these nineteen cases: ten Kanto, seven Kinki and two Kyushu. Minimum mesh-to-land distance ranges from approximately 68 to 1,372 metres. Preserve No Land Overlap, Region Assignment Method, Nearest Land Distance and nearest-prefecture provenance. The regional approval alone does not establish prefecture assignments; the separately approved prefecture exceptions are recorded below. For the exceptions, measured regional land area and land share remain missing and total land overlap stays zero; these values are not fabricated. The reviewed classification retains all 228,988 national meshes. All other meshes use the original maximum-positive-land-overlap rule, all earlier labels and areas are preserved, and substantive panel values are unchanged.

### Corrected Prefecture Classification

Apply the same direct maximum-positive-prefecture-land-intersection rule to the corrected sample of 228,988 meshes. There are 228,969 normal assignments and 4,476 cross-prefecture meshes. Independently clipped source polygons verify 106 boundary combinations and all forty-seven prefecture interiors. Earlier prefecture labels and land-area diagnostics are reproduced, and grouped prefecture areas reproduce the regional overlap ledger. County-level labels imply the same accepted Region for every mesh, leaving the existing Region data intact.

The user separately approves nineteen reviewed nearest-land prefecture exceptions: five Chiba, five Kanagawa, four Osaka, three Hyogo and two Okinawa. Preserve No Land Overlap, Prefecture Assignment Method and Nearest Land Distance. For these exceptions, Prefecture Land Area and Prefecture Land Share remain missing, Total Land Overlap remains measured zero, and the prefecture label is held constant across all four periods. The reviewed decision does not fabricate historical land or alter any substantive road, light or population value. All 228,988 national sample meshes remain eligible for prefecture regression.

### Current Five-Period Extension

This subsection records the five-period extension before the subsequent density-zero coding revision; its cohort figures describe the existing regression checkpoint. Readable variables, units and substantive roles remain unchanged. The complete five-period panel has 4,864,000 records; the analysis-only complete-five-period subset contains 228,988 meshes and 1,144,940 observations. Every historical substantive value is preserved exactly. Missingness remains in complete data rather than being imputed. The selected cohort includes all 339,785 genuine population-zero records.

For 2020 Population, preserve published total counts, independently verify male plus female totals where numerical, and retain detail-disclosure linkage without reaggregating published totals. Restore absence within a verified complete census archive to zero; archive absence and invalid totals remain missing. Match this census snapshot to the 2024 road and light period, retaining the signed four-year offset.

For 2024 Road Length, retain ordinary centerlines in normal, bridge, tunnel and snow-cover states, including unknown widths with flags. Retain exact-geometry repeated records and flag them. Transform source coordinates into the common mesh datum, allocate projected centerline lengths to mesh interiors with half-open internal boundary ownership, and retain an outside-allocation ledger. Road Length Density divides kilometres by full geometric Mesh Area in square kilometres. Length conservation and pilot equivalence pass. Covered meshes with no selected length receive zero; missing source archives would remain missing. Do not calibrate the latest density to historical density.

For 2024 Nighttime Radiance, rebuild pixel-mesh overlap weights using the year's actual raster origin and extent. Use the confirmed valid-area-weighted mean, retain genuine zero, exclude explicit nodata, and preserve valid-pixel coverage relative to the full mesh area. No logarithm, land clipping or filling is added.

The approved regional and direct prefecture assignments remain identical for all 228,988 meshes and are held fixed across five periods. Retain all nineteen expressly approved nearest-land exceptions, their missing land shares and areas, and their measured zero land overlap. No MODIS, railway or POI variable is constructed for this rerun.

### Confirmed Static Facility Supplement Assumption

Under the user's explicit time-invariance assumption, attach each selected facility snapshot to all five road-anchored periods: 2002, 2003, 2004, 2010 and 2024. For a constructed facility characteristic \(Z_i^{(s)}\) from source edition \(s\), define \(Z_{it}=Z_i^{(s)}\) for every study period \(t\). Retain each actual source edition and an explicit static-assumption flag. These repeated characteristics describe assumed constant spatial context; they are not separately observed historical facilities, historical openings or closures, service intensity, or changes in accessibility.

| Supplementary facility inventory | Retained source edition | Temporal treatment |
| --- | --- | --- |
| Passenger railway stations | 2024 | Hold constructed mesh characteristics fixed across all five periods. |
| Regular bus terminal candidates | 2022 | Hold candidate characteristics fixed; retain candidate identity and coverage flags. |
| Highway bus terminal candidates | 2023 | Hold candidate characteristics fixed; preserve the separate source edition. |
| Airports and terminal buildings | 2021 | Hold passenger-airport characteristics fixed under the operating and scheduled-service filter; count shared terminal points once. |
| Schools | 2023 | Hold constructed classified counts fixed. |
| Medical institutions | 2020 | Hold constructed classified counts fixed; creation edition does not establish a common exact observation date. |
| Logistics hubs | 2013 | Hold constructed classified counts fixed. |
| Visitor and event facilities | 2014 | Hold constructed classified counts fixed; this is not a comprehensive commercial POI inventory. |

Link by Mesh Code without duplicating or dropping mesh-period records. Preserve zero-valued counts where source coverage and the selected facility definition support them, and retain unavailable information as missing with provenance. Temporal replication does not resolve missing coordinates or certify completeness. Existing road, population and nighttime-radiance values and actual observation years remain unchanged. The confirmed constructions below are attached to the panel. Bus identity review remains pending; no augmented regression is implied as completed. This decision applies to the cross-sectional facility supplements and does not select a static land-cover edition.

### Constructed Static Facility Mesh Variables

The approved static supplements are now constructed for the complete 972,800-mesh grid and linked to both five-period datasets. The complete panel retains 4,864,000 rows; the unchanged balanced cohort retains 228,988 meshes and 1,144,940 rows. Each facility-only augmented panel contains 79 columns, including 38 retained analytical facility candidates plus source-year, linkage and quality references. Existing substantive columns are preserved exactly. The candidate role is TBD: retaining a variable does not add it to any regression.

For observed selected facility locations \(\mathcal{F}_k^{(s)}\), define \(C_{ik}^{(s)}=\sum_{j\in\mathcal{F}_k^{(s)}}\mathbf{1}\{p_j\in M_i\}\). Allocate points to the common mesh datum and use south/west-inclusive, north/east-exclusive boundaries. For a mesh centre \(c_i\), define \(d_{ik}^{(s)}=\min_{j\in\mathcal{F}_k^{(s)}}\operatorname{dist}_{\mathrm{GRS80}}(c_i,p_j)/1000\), in kilometres. Distances represent geographic proximity to observed representative points, rather than network travel time.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| School Facility Count | School Facility Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Primary School Count | Primary School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Junior High School Count | Junior High School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Secondary School Count | Secondary School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| High School Count | High School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Technical College Count | Technical College Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Junior College Count | Junior College Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| University Count | University Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Kindergarten Count | Kindergarten Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Special Needs School Count | Special Needs School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Integrated Early Childhood Centre Count | Integrated Early Childhood Centre Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Compulsory Education School Count | Compulsory Education School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Miscellaneous School Count | Miscellaneous School Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Specialized Training College Count | Specialized Training College Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions. | yes |
| Medical Facility Count | Medical Facility Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed hospital and general/dental clinic records; merge exact name/geometry/type duplicates. Suspended and in-company records remain included. | yes |
| Hospital Count | Hospital Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed hospital and general/dental clinic records; merge exact name/geometry/type duplicates. Suspended and in-company records remain included. | yes |
| General Clinic Count | General Clinic Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed hospital and general/dental clinic records; merge exact name/geometry/type duplicates. Suspended and in-company records remain included. | yes |
| Dental Clinic Count | Dental Clinic Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed hospital and general/dental clinic records; merge exact name/geometry/type duplicates. Suspended and in-company records remain included. | yes |
| Logistics Facility Count | Logistics Facility Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Container Terminal Count | Container Terminal Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Air Cargo Terminal Count | Air Cargo Terminal Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Freight Railway Station Count | Freight Railway Station Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Bonded Facility Count | Bonded Facility Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Truck Terminal Count | Truck Terminal Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Wholesale Market Count | Wholesale Market Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes. | yes |
| Visitor and Event Facility Count | Visitor and Event Facility Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Cinema Count | Cinema Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Public Assembly Hall Count | Public Assembly Hall Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Theatre Count | Theatre Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Exhibition Venue Count | Exhibition Venue Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Spectator Venue Count | Spectator Venue Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Other Visitor Facility Count | Other Visitor Facility Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce. | yes |
| Railway Station Count | Railway Station Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Official passenger-station groups; use the designated station sections to locate each group. Preserve the one missing designated-code flag and use its sole observed section. | yes |
| Distance to Railway Station | Distance to Railway Station | TBD | \(d_{ik}^{(s)}\), km, repeated unchanged across five periods. | Official passenger-station groups; use the designated station sections to locate each group. Preserve the one missing designated-code flag and use its sole observed section. | yes |
| Passenger Airport Count | Passenger Airport Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Operating airports with jet or propeller scheduled services, represented by linked terminal points. Shared terminal identifiers are counted once. | yes |
| Distance to Passenger Airport | Distance to Passenger Airport | TBD | \(d_{ik}^{(s)}\), km, repeated unchanged across five periods. | Operating airports with jet or propeller scheduled services, represented by linked terminal points. Shared terminal identifiers are counted once. | yes |
| Bus Terminal Candidate Count | Bus Terminal Candidate Count | TBD | \(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods. | Name-screened candidate stop locations; merge only exact original name/coordinate duplicates across both sources. Keep all screening flags and pending facility-identity review. | yes |
| Distance to Bus Terminal Candidate | Distance to Bus Terminal Candidate | TBD | \(d_{ik}^{(s)}\), km, repeated unchanged across five periods. | Name-screened candidate stop locations; merge only exact original name/coordinate duplicates across both sources. Keep all screening flags and pending facility-identity review. | yes |

School, medical, logistics and visitor/event category counts partition their corresponding total counts. Retaining a total and all its categories does not imply simultaneous use in a model because these columns are exactly collinear. Quantity variables enumerate deduplicated observed functional records or locations; they do not independently certify all distinct operating institutions.

All 284 selected source ZIPs remain checksum- and CRC-verified. All selected geocoded facilities lie within the study grid; no missing coordinates were filled. Count zero denotes no selected observed record in a mesh under the complete downloaded archive coverage, and does not certify the absence of every real facility. Source omissions and changing historical coverage are not resolved by the static assumption. Retain all five periods, population zeros, islands and existing road missingness.

The bus supplement contains 778 exact-name-coordinate candidate locations from 1,736 source records. Retain peripheral, air-related, port-related, freight-related and abbreviation flags, plus explicit coverage-limited and identity-review-pending fields. The separately documented 63 unlocated ordinary-stop records cannot be located or filled. Bus candidates are not a verified terminal inventory. Airport selection contains 87 eligible airport reference sites represented by 86 distinct terminal service points; one shared terminal reference is counted once. The railway supplement contains 9,048 official station groups and preserves one source representative-code inconsistency. Independent exhaustive geodesic checks agree within one millimetre.

Preserve actual source editions and the Facility Static Assumption field on every augmented record. Annual land-cover data are acquired and constructed in the separate supplement described below. Existing national, regional, prefecture and local estimates retain their prior road/population specification; this data construction does not refit those models.

### Constructed Annual MODIS Land Cover

The following construction checkpoint precedes the active water-retention revision below. Its original quality exclusion and cohort counts are historical.

The confirmed land-cover supplement uses annual MCD12Q1 Collection 6.1 observations matched separately to 2002, 2003, 2004, 2010 and 2024. This follows the previously selected exemption from the facility snapshot restriction. Land Cover Year equals the road/light period; a contemporary land-cover snapshot is not replicated into historical periods. Facility characteristics retain their confirmed static source editions.

For every year, construct variables on the complete 972,800-mesh grid. The combined annual mesh table contains 4,864,000 mesh-year records and 17 readable fields: six retained analytical candidates and eleven key, year, product, area and quality references. Append sixteen fields to each facility-augmented panel, preserving its previous 79 columns exactly. The complete augmented panel contains 4,864,000 rows and 95 columns; the unchanged balanced cohort contains 228,988 meshes, 1,144,940 rows and 95 columns. No row or island is removed.

Let \(M_i\) be mesh \(i\), \(P_p\) a native MODIS pixel, \(a_{ip}=\operatorname{area}(M_i\cap P_p)\), and \(A_i=\operatorname{area}(M_i)\). Use the same native spherical equal-area sinusoidal projection for numerator and denominator. Densify mesh meridians and intersect actual pixel boundaries; do not use a centre pixel, interpolate category codes or assume a literal one-square-kilometre mesh. Land Cover Mesh Area is a separate reference and does not replace the existing road Mesh Area.

For the set \(\mathcal P_t\) of source-available pixels with valid IGBP class labels and accepted quality codes \(\{0,2,4,5,6,7,8,9\}\), construct \(\ell_{itk}=\sum_{p\in\mathcal P_t}a_{ip}\mathbf{1}\{c_{pt}\in\mathcal C_k\}/A_i\), where \(c_{pt}\) is the original class and \(\mathcal C_k\) is the confirmed class group. Define valid coverage \(V_{it}=\sum_{p\in\mathcal P_t}a_{ip}/A_i\). The six contributions satisfy \(\sum_k\ell_{itk}=V_{it}\), without redistributing unknown area or forcing partial coverage to sum to one.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| Urban Land Cover Share | Urban Land Cover Share | TBD | \(\ell_{itk}\), fraction of full projected mesh area. | IGBP urban and built-up class 13. Retain NaN where no valid pixels exist. | yes |
| Forest Land Cover Share | Forest Land Cover Share | TBD | \(\ell_{itk}\), fraction of full projected mesh area. | IGBP forest classes 1-5. Retain NaN where no valid pixels exist. | yes |
| Cropland Land Cover Share | Cropland Land Cover Share | TBD | \(\ell_{itk}\), fraction of full projected mesh area. | IGBP cropland class 12. Retain NaN where no valid pixels exist. | yes |
| Cropland Mosaic Land Cover Share | Cropland Mosaic Land Cover Share | TBD | \(\ell_{itk}\), fraction of full projected mesh area. | IGBP cropland/natural-vegetation mosaic class 14, kept separate. Retain NaN where no valid pixels exist. | yes |
| Water Land Cover Share | Water Land Cover Share | TBD | \(\ell_{itk}\), fraction of full projected mesh area. | IGBP water class 17, requiring a valid classification. Retain NaN where no valid pixels exist. | yes |
| Other Land Cover Share | Other Land Cover Share | TBD | \(\ell_{itk}\), fraction of full projected mesh area. | IGBP shrubland, savanna, grassland, wetland, snow/ice and barren classes 6-11 and 15-16. Retain NaN where no valid pixels exist. | yes |

Retain Land Cover Source Coverage, Land Cover Coverage, Land Cover Unclassified Share, Land Cover No Data Share, Land Cover Adjusted Share, Land Cover Incomplete Coverage and Land Cover No Valid Pixels, plus Land Cover Year, Land Cover Product and Land Cover Mesh Area. Source coverage measures published, downloaded native pixels. Valid coverage excludes unclassified quality codes 1 and 3, no-data code 10, fill/invalid labels and unpublished tiles. The adjusted share identifies retained valid product corrections with quality codes 4-9; it is not a mean of categorical quality codes.

The valid, unclassified and no-data area contributions partition the full mesh area. No valid coverage produces NaN in all six class contributions. Partial-coverage values describe observed area contributions only; the unknown remainder is not assigned to any class. Retain genuine observed zeros, apply no statistical filling, rescaling or logarithm, and preserve all missingness flags. Tiny floating-point roundoff is bounded in quality fractions only.

The h32v06 tile near Minami-Torishima is absent from all five official annual catalogues. Preserve 2,315 meshes intersecting that unpublished source tile, including 2,180 entirely within it, with source-coverage and missingness information. Do not infer a water class or remove an island because an archive is absent.

Within the unchanged balanced cohort, 27 mesh-period observations have no valid land-cover classification, affecting 9 distinct meshes; 1,191 observations have positive but partial valid coverage. All remain in the augmented dataset. Per-period quality profiles are retained separately; no complete-case regression cohort has been selected.

The six groups exhaust the accepted IGBP classes and partition valid coverage. Their retention does not imply simultaneous inclusion with coverage in a model. Candidate roles remain TBD and no augmented regression specification is selected. Urban-labelled pixel area does not measure exact buildings or impervious-surface fraction; cropland/natural-vegetation mosaic area is not decomposed into actual crop and vegetation fractions. Annual classifications provide broad context and their differences are not direct measurements of real land-cover change.

Product processing identifiers and original response checksums are verified against official Collection 6.1 catalogues. Overlapping downloads, independent small-region pixel positions and independent polygon intersections pass. Existing national, regional, prefecture and local regression outputs retain their earlier road/population specification; this supplement does not refit them.

### Constructed Eighteen Additional KSJ Snapshot Counts

This construction checkpoint precedes the density-zero coding revision below. The confirmed additional supplement constructs eighteen analytical count candidates on the existing 972,800-mesh grid. The complete augmented panel retains 4,864,000 observations and the balanced cohort retains 228,988 meshes and 1,144,940 observations. Both now contain 208 readable columns: their previous 95 fields are preserved exactly, and the supplement adds eighteen counts and 95 source-year, coverage, duplicate, geometry, datum and static-assumption references. Candidate regression roles remain TBD; this construction does not select or refit a regression.

For selected deduplicated units of category \(k\) in snapshot \(s\), let \(\mathcal{P}_j^{(s)}\) contain the native point locations of unit \(j\). Define \(C_{ik}^{(s)}=\sum_{j\in\mathcal{F}_k^{(s)}}\mathbf{1}\{\mathcal{P}_j^{(s)}\cap M_i\ne\varnothing\}\). Each unit contributes at most once per mesh. Ordinary point units occupy one mesh; native multi-location tourism resources may occupy multiple meshes. Under the approved static assumption, \(C_{itk}=C_{ik}^{(s)}\) in 2002, 2003, 2004, 2010 and 2024.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| Fuel Station Count | Fuel Station Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed station locations; exact address, coordinates and official class. | yes |
| Roadside Station Count | Roadside Station Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named stations; retain all official functional flags as duplicate partitions. | yes |
| Expressway Junction Count | Expressway Junction Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Current 2025 records with end year 9999 and start year at most 2025; retain official types 1-4 and inconsistent relation IDs. | yes |
| Port Count | Port Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed representative port points; preserve both official classifications. | yes |
| Fishing Port Count | Fishing Port Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed representative fishing-port points; retain official class. | yes |
| Passenger Route Port Count | Passenger Route Port Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named passenger-route port nodes; route lines remain references. | yes |
| Heliport Count | Heliport Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named landing locations; preserve official type and category. | yes |
| Welfare Facility Count | Welfare Facility Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named welfare functional records; retain the three-level classification. | yes |
| Cultural and Sports Facility Count | Cultural and Sports Facility Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed cultural and sports records; retain official class and closed-status references. | yes |
| Municipal and Meeting Facility Count | Municipal and Meeting Facility Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed municipal offices and meeting facilities; retain official class. | yes |
| National and Prefectural Institution Count | National and Prefectural Institution Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed national and prefectural institution points; retain official class. | yes |
| Police Facility Count | Police Facility Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed police facility points by official class; jurisdiction polygons remain references. | yes |
| Fire Facility Count | Fire Facility Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed fire-service facility points by official class; jurisdiction polygons remain references. | yes |
| Post Office Count | Post Office Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed postal facility points by official class; retain suspended facilities. | yes |
| Research Institution Count | Research Institution Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named research institutions; preserve operator class. | yes |
| Local Industry Facility Count | Local Industry Facility Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named local-industry functional records; retain four functional flags as partitions. | yes |
| Urban Park Count | Urban Park Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Observed named representative urban-park points; retain official park class. | yes |
| Tourism Resource Count | Tourism Resource Count | TBD | \(C_{ik}^{(s)}\), replicated unchanged across five periods. | Native Point and MultiPoint resources; count a deduplicated parent at most once per occupied mesh. Preserve lines and polygons as excluded references. | yes |

Merge records only within a category when the original nonmissing name or address, native coordinate geometry and agreed official class or function partition match exactly. Preserve anonymous records individually. Apply no name normalization, proximity merge, cross-category merge or additional operating-status filter. All original attributes, source identifiers, duplicate memberships and reference geometries remain traceable in the source and construction ledgers. No combined total across categories is defined.

Use each file datum where available and the documented official product datum where its projection file is absent; retain the latter as a mesh quality flag. Transform locations to the established JGD2000 common-grid datum and preserve the established boundary convention. Every selected point is located within this grid. All 294 original archives remain checksum-verified and unchanged. Source text decoding is verified against the complete native character-field byte inventory before name-based duplicate decisions.

The selected records yield 697,404 deduplicated units after removing 36 duplicate count contributions. The expressway supplement retains 2,384 current records and flags three inconsistent relation IDs without collapsing their distinct names, classes or locations. The tourism supplement retains 17,245 deduplicated point-based resources and 17,293 resource-mesh memberships, excluding 85 line and 1,797 polygon source features from the point count while retaining them as reference geometries. Jurisdiction polygons, port boundaries, passenger routes and expressway lines do not add facility counts.

Retain actual source editions: fuel stations use archive 2015 and reference 2016; roadside stations use edition 2018 with reference date 2019-01-01; expressway nodes use 2025; ports use 2014; fishing ports use 2006; passenger-route ports use 2012; heliports use 2013; welfare facilities use 2023; cultural and sports facilities use 2013; municipal/meeting facilities and national/prefectural institutions use 2022; police and fire facilities use 2012; post offices use 2013; research and local-industry facilities use 2012; urban parks use 2011; tourism resources use 2014. These editions remain explicit throughout temporal replication, including the 2025 expressway edition. They are not historical observations in each study period.

Count zero means that no selected observed unit is allocated to the mesh under completed downloaded archive coverage. It does not establish exhaustive real-world coverage or absence of all facilities. The tourism indicator is explicitly point-based. Retain unavailable source coverage as missing if encountered; no such archive-coverage gap occurs in these selected inputs. Apply no imputation, rescaling, logarithm, row deletion or island exclusion. Existing population zeros, road missingness, annual land-cover values and prior national, regional, prefecture and local estimates are preserved.

### Active Density-Only Zero Coding Revision

The user now directs all missing Road Length Density values to be coded as zero in the analytical dataset, including historical source-unlisted meshes and source-unknown records. This supersedes the density component of the earlier missing-road rule. For the source-derived density \(D_{it}\), define \(D_{it}^{*}=D_{it}\) when finite and \(D_{it}^{*}=0\) when unavailable. This is an explicit analytical coding assumption, including for unknown values; it does not establish verified physical absence of roads.

Retain Road Density Originally Missing and Road Density Source Status as readable provenance references. They distinguish source-unlisted, source-unknown and observed values. Earlier missing-density data remain separately preserved. Every finite observed density is retained exactly; Road Length and Mesh Area are not filled or recomputed. Population, Nighttime Radiance, facilities, annual land cover and actual matching years are unchanged. No raw archive is modified.

The revision codes 2,882,853 missing densities as zero: 2,074,500 source-unlisted and 808,353 source-unknown records. The year-specific counts are 723,789 in 2002, 722,287 in 2003, 720,962 in 2004 and 715,815 in 2010; 2024 already has no numerical density missingness.

The full updated dataset retains 972,800 meshes and 4,864,000 observations. Its 210 readable fields consist of the previous 208 fields plus two provenance references; 207 prior fields are preserved exactly and only Road Length Density changes. The count of analytical candidates remains 65.

Reapplying the existing finite-density, population and radiance criterion across all five periods yields 966,400 meshes and 4,832,000 observations. All 228,988 previous core-balanced meshes remain eligible; 737,412 additional meshes enter this numerical completeness cohort. Population archive gaps remain missing and no land, coastline, island or administrative filter is introduced. Land-cover missingness and incomplete coverage remain present; the expanded core-balanced cohort is not an all-covariate-complete cohort.

Existing national, regional, prefecture and local model outputs remain associated with the earlier 228,988-mesh cohort and have not been refitted. Existing reviewed administrative classifications are preserved; no geographic assignment for newly eligible meshes or additional nearest-land exception is inferred in this variable-construction step. The expanded cohort is a newly constructed data product, rather than a completed new regression result.

### Active MODIS Mask-Identified Water Retention

The user rejects exclusion of source pixels identified as water by the product water mask. Retain the original IGBP water class for these pixels even when annual spectral classification is unavailable. This revises only the earlier exclusion of mask-identified unclassified water. Unclassified land, invalid labels and genuinely unavailable source areas retain their prior handling. No water label is inferred where the source tile is absent.

Use the same IGBP grouping: urban and built-up land; five forest classes; cropland; cropland/natural-vegetation mosaic; water; and other shrubland, savanna, grassland, wetland, snow/ice and barren classes. These are six fractions of the complete projected mesh area, derived from the original 17-class product, rather than a newly trained classification. Annual matching, native pixel intersections, class groups and all six readable names are unchanged.

Land Cover Coverage now includes mask-identified water area. The six shares partition this accepted coverage; no accepted coverage still gives six NaNs. Land Cover Unclassified Share retains its original quality meaning, including both unclassified land and the now-retained unclassified water. Consequently it overlaps accepted coverage and must not be added to coverage as a disjoint area component. Land Cover No Data Share, source coverage, product adjustment references and original source checksums remain preserved. Completeness and no-valid-pixel flags are recalculated from the updated coverage.

The revision restores six numerical shares for 2,198,585 mesh-period records and leaves 10,900 full-grid records without source-supported coverage. In a fully water-covered mesh the water share is one and the five other shares are zero. Partial source coverage and unresolved land areas are not redistributed or statistically imputed.

The active full panel retains 972,800 meshes and 4,864,000 records. The core-balanced panel retains 966,400 meshes and 4,832,000 records. Both retain 210 readable fields and 65 analytical candidates. All 201 columns outside the six shares and three coverage/completeness fields are preserved exactly, including road zero coding, population, radiance, facilities and original land-cover quality references. No model is refitted by this construction revision.

### Approved Common Baseline Cohort

Use the same 383,390 meshes in national, nine-region, forty-seven-prefecture and local pooled models, with five complete core records per mesh. The cohort contains 383,371 positive-overlap meshes and nineteen previously reviewed nearest-land exceptions. Assign each Prefecture by greatest positive prefectural land overlap and each Region by greatest summed overlap across its member Prefectures; freeze both across the five periods. All earlier assignments match the new geometry audit. Retain eligible islands and the reviewed exception flags; do not add new nearest-land exceptions. The selection changes analytical membership but preserves every retained core value exactly. Density zero coding remains in force; no new transformation or land-cover complete-case restriction is introduced.

### Approved Focused Land-Cover and POI Extension

The human accepts the recommended focused extension and the execution order national, nine Regions, forty-seven Prefectures, then geographically weighted pooled regression. Nighttime Radiance, Road Length Density and Population retain their definitions, original units, observed zeros and source-year offsets. The following current roles supersede earlier TBD roles for these selected controls only. Retain all other constructed candidates and quality references in the source panels without adding them to this equation.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| Urban Land Cover Share | Urban Land Cover Share | control | Annual full-mesh-area contribution of the confirmed urban class. | Existing annual construction; no rescaling, filling or logarithm. | yes |
| Forest Land Cover Share | Forest Land Cover Share | control | Annual full-mesh-area contribution of the confirmed forest classes. | Existing annual construction; preserve quality references. | yes |
| Cropland Land Cover Share | Cropland Land Cover Share | control | Annual full-mesh-area contribution of the confirmed cropland class. | Existing annual construction; preserve observed zeros. | yes |
| Cropland Mosaic Land Cover Share | Cropland Mosaic Land Cover Share | control | Annual full-mesh-area contribution of the confirmed mosaic class. | Existing annual construction; preserve observed zeros. | yes |
| Water Land Cover Share | Water Land Cover Share | control | Annual full-mesh-area contribution of confirmed water, including accepted mask-identified water. | Existing active water-retention construction. | yes |
| Other Land Cover Share | Other Land Cover Share | retained reference | Annual contribution of the remaining confirmed classes. | Retained in data but omitted from the focused equation. | yes |
| Distance to Railway Station | Distance to Railway Station | control | Existing distance in kilometres to the selected passenger-station representatives. | Replicate the confirmed snapshot unchanged across five periods. | yes |
| Distance to Passenger Airport | Distance to Passenger Airport | control | Existing distance in kilometres to the selected passenger-airport representatives. | Replicate the confirmed snapshot unchanged across five periods. | yes |
| School Facility Count | School Facility Count | control | Existing total count of selected school records or campuses in the mesh. | Use the total without simultaneous school-type components. | yes |
| Medical Facility Count | Medical Facility Count | control | Existing total count of selected medical records in the mesh. | Use the total without simultaneous medical-type components. | yes |
| Logistics Facility Count | Logistics Facility Count | control | Existing total count of selected freight-related facilities in the mesh. | Use the total without simultaneous logistics-type components. | yes |
| Visitor and Event Facility Count | Visitor and Event Facility Count | control | Existing total count of selected visitor and event facilities in the mesh. | Use the total without simultaneous facility-type components. | yes |

Require complete selected variables over all five records of a mesh only for this extension. Preserve the original unavailable land-cover values and every original baseline record. Other Land Cover Share remains a data category, not a deleted category. Partial coverage remains flagged and is not redistributed. The already approved facility time-invariance assumption continues; these controls do not reconstruct historical facility opening dates or historical transport accessibility. Baseline comparisons are reestimated on this identical extension sample so that changes in slopes and joint fit are not attributed to the four-mesh availability difference.

### Municipal Exploratory Reference Metrics

The user accepts municipal summaries of potential mismatch, surveyed traffic utilization and maintenance fiscal burden. These references support the exploratory trial and are not new controls in the approved pooled or local regressions. Existing screening values, source years and fiscal names are retained. Detailed municipal allocation and linkage conventions are agent-specified for this trial, rather than newly human-selected final geography standards.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| Government Code | Government Code | exploratory jurisdiction reference | Five-digit code of the individual municipal financial government. | Code-first linkage; designated-city wards consolidate to their verified parent; unavailable mesh links remain missing. | no |
| Candidate Fraction of Supported Meshes | Candidate Fraction of Supported Meshes | exploratory mismatch reference | Candidate meshes divided by supported comparison meshes assigned to the government. | Reuse the approved light-support screen; retain unavailable source rows and denominator counts. | no |
| Candidate Road Stock Share | Candidate Road Stock Share | exploratory stock reference | Road Length in candidate mesh footprints divided by Road Length in all assigned mesh footprints. | Whole-mesh allocation approximation; not clipped municipal or municipality-owned road stock. | no |
| Length Weighted 24h Volume | Length Weighted 24h Volume | exploratory utilization reference | Source-segment-length-weighted published daily vehicle volume in the coded municipal territory. | Retain manager, road class and estimation flags; unavailable published traffic stays missing. | no |
| Maintenance Share of Expenditure | Maintenance Share of Expenditure | exploratory fiscal reference | The same municipal government's Road and Bridge maintenance spending divided by total expenditure. | Actual fiscal year 2023; amounts in thousand yen; zero denominator would leave the ratio unavailable. | no |
| Maintenance Share of Standard Fiscal Scale | Maintenance Share of Standard Fiscal Scale | exploratory fiscal reference | The same municipal maintenance numerator divided by standard fiscal scale. | Same year and government; no calibration to candidate kilometres. | no |
| Single Year Fiscal Revenue Need Ratio | Single Year Fiscal Revenue Need Ratio | exploratory capacity reference | Standard fiscal revenue divided by standard fiscal need for the same government and year. | Single-year amount ratio; do not interpret as the encoded three-year strength index. | no |

Original source amounts, actual dates, government types, screening support, boundary flags and unmatched jurisdiction records remain available for audit. Summaries by annual land context use the same municipal traffic and fiscal context, not separately measured traffic or costs inside each land-cover class. Tokyo special wards retain their values and institutional distinction. No trimming, imputation, logarithm or additional excess-road threshold is selected.

### Confirmed Active Analytical Variables

Decision MILI-D-20261011-004 confirms fifteen substantive panel variables and seven descriptive mismatch, traffic and fiscal variables. The latter are used in descriptive spatial and administrative comparisons, without being added to the radiance equations. Geographic strata, identifiers, actual source years, coverage, denominators and quality references remain available separately. UMD roles below revise the panel variables under the latest user decision. Decision MILI-D-20261011-027 updates mesh-level mismatch and Land Context to UMD using unchanged screening rules. Current municipal candidate fractions and land-context summaries have now been reconciled to the validated UMD screen using unchanged government assignments and verified fiscal/traffic references. Historical IGBP evidence remains preserved. This subsection defines the active formal roles; earlier exploratory role assignments are retained as construction history.

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
| --- | --- | --- | --- | --- | --- |
| Nighttime Radiance | Nighttime Radiance | outcome | Area-weighted mean source radiance over valid pixel intersections, in nW/cm2/sr; proxy for broader economic activity. | Retain valid source zeros; exclude declared nodata during existing construction. No new filling, clipping or logarithm. | yes |
| Road Length Density | Road Length Density | main explanatory | Source-defined road length per full mesh area, in km/km2; historical supplied densities and recent centerline-derived densities retain distinct provenance. | Reuse accepted density-only zero coding for source-unlisted/unknown values and preserve its source-status flags. No source rescaling. | yes |
| Population | Population | control | Published mesh total residents at the actual matched census year, with archive-covered source-unlisted meshes retaining accepted structural zeros. | Retain accepted structural zeros, archive-coverage provenance and actual census offsets. No statistical imputation. | yes |
| Urban Land Cover Share | Urban Land Cover Share | control | Annual full-mesh-area share of the confirmed urban land-cover category; partial coverage remains flagged and is not normalized. | Reuse accepted annual class aggregation and quality flags; no rescaling or filling. | yes |
| Forest Land Cover Share | Forest Land Cover Share | control | Annual full-mesh-area share of the confirmed forest land-cover category; partial coverage remains flagged and is not normalized. | Reuse accepted annual class aggregation and quality flags; no rescaling or filling. | yes |
| Cropland Land Cover Share | Cropland Land Cover Share | control | Annual full-mesh-area share of the confirmed cropland land-cover category; partial coverage remains flagged and is not normalized. | Reuse accepted annual class aggregation and quality flags; no rescaling or filling. | yes |
| Shrublands and Grasslands | Shrublands and Grasslands | control | Annual full-mesh-area share of the confirmed UMD classes 6-10; partial coverage remains flagged and is not normalized. | Reuse accepted annual class aggregation and quality flags; no rescaling or filling. | yes |
| Water Land Cover Share | Water Land Cover Share | omitted reference | Annual full-mesh-area share of the confirmed water land-cover category; partial coverage remains flagged and is not normalized. | Reuse accepted annual class aggregation and quality flags; no rescaling or filling. | yes |
| Distance to Railway Station | Distance to Railway Station | control | Existing distance in kilometres to selected passenger-station representatives. | Reuse the approved static source edition across five periods, without reconstructing historical facility openings or adding category components. | yes |
| Distance to Passenger Airport | Distance to Passenger Airport | control | Existing distance in kilometres to selected passenger-airport representatives. | Reuse the approved static source edition across five periods, without reconstructing historical facility openings or adding category components. | yes |
| School Facility Count | School Facility Count | control | Existing count of selected school records or campuses in the mesh. | Reuse the approved static source edition across five periods, without reconstructing historical facility openings or adding category components. | yes |
| Medical Facility Count | Medical Facility Count | control | Existing count of selected medical facilities in the mesh. | Reuse the approved static source edition across five periods, without reconstructing historical facility openings or adding category components. | yes |
| Logistics Facility Count | Logistics Facility Count | control | Existing count of selected freight-related facilities in the mesh. | Reuse the approved static source edition across five periods, without reconstructing historical facility openings or adding category components. | yes |
| Visitor and Event Facility Count | Visitor and Event Facility Count | control | Existing count of selected visitor and event facilities in the mesh. | Reuse the approved static source edition across five periods, without reconstructing historical facility openings or adding category components. | yes |
| Barren | Barren | control | Annual full-mesh-area share of the confirmed UMD class 15; partial coverage remains flagged and is not normalized. | Reuse accepted annual class aggregation and mask-identified water; retain Barren and incomplete coverage. Water Land Cover Share is omitted from the focused equation. | yes |
| Potential Mismatch Candidate | Potential Mismatch Candidate | descriptive mismatch indicator | True for supported meshes with positive Road Length Density above the peer upper quartile and Nighttime Radiance at or below the peer lower quartile; unavailable screening remains missing. | Recompute 2024 peer quartiles using confirmed UMD Land Context; keep all other peer dimensions, at least thirty distinct meshes, positive peer maximum radiance, linear quartiles and original strict road/inclusive radiance comparisons. No filling. | yes |
| Land Context | Land Context | descriptive context | Dominant 2024 full-mesh UMD share among Urban, Forest, Cropland, Water, Shrublands and Grasslands, and Barren. | Retain tied largest shares within absolute tolerance 1e-12 as Tied dominant classes; Incomplete coverage overrides dominance. Do not normalize shares. Retain all observed contexts. Historical IGBP municipal contexts remain separately identified. | yes |
| Candidate Fraction of Supported Meshes | Candidate Fraction of Supported Meshes | descriptive mismatch measure | Current UMD candidate meshes divided by supported comparison meshes in the assigned government or land context; preserve denominator counts. | Reaggregate the validated UMD screen using unchanged mesh-government assignments and parent-city consolidation. Retain all source rows, unavailable links and zero-denominator contexts; no filling. | yes |
| Length Weighted 24h Volume | Length Weighted 24h Volume | descriptive utilization measure | Published daily vehicle volumes averaged with positive source-segment-length weights; unavailable traffic remains missing. | Reuse existing source-derived values; no additional transformation or filling. | yes |
| Maintenance Share of Expenditure | Maintenance Share of Expenditure | descriptive fiscal measure | The same government Road and Bridge maintenance spending divided by total expenditure; preserve actual fiscal year and amounts. | Reuse existing source-derived values; no additional transformation or filling. | yes |
| Maintenance Share of Standard Fiscal Scale | Maintenance Share of Standard Fiscal Scale | descriptive fiscal measure | The same government Road and Bridge maintenance spending divided by standard fiscal scale. | Reuse existing source-derived values; no additional transformation or filling. | yes |
| Single Year Fiscal Revenue Need Ratio | Single Year Fiscal Revenue Need Ratio | descriptive fiscal-resource measure | Single-year standard fiscal revenue divided by standard fiscal need; distinct from the encoded three-year strength index. | Reuse existing source-derived values; no additional transformation or filling. | yes |

Reference fields preserve mesh and government identifiers, actual source years, supported and candidate counts, source coverage, missing-status flags and source amounts. Candidate Road Stock Share remains a reference measure of roads in flagged mesh footprints, not excessive length or government-owned inventory. All original mesh and government records remain represented.

Municipal assignment uses largest identified municipal land overlap within the already frozen Prefecture. Administrative wards of designated cities link to the verified financial parent. Unavailable jurisdiction links remain missing; this is an allocation approximation rather than clipped official road ownership. Context-specific candidate fractions are compared with whole-government outcomes. Current source dates remain road/light 2024, population 2020, surveyed traffic 2021 and finance actual FY2023.

The panel retains 1,916,930 records from 383,386 meshes and five road/light periods, with matched population years unchanged. The validated UMD screen retains 383,386 meshes: 376,219 supported comparisons, 66,097 candidates and 7,167 unavailable candidate indicators. The historical IGBP screen remains preserved. Municipal evidence retains 1,741 governments, seven unavailable traffic outcomes and complete selected fiscal ratios. The underlying jurisdiction ledger retains 320 unavailable government links. No filling, deletion, clipping, logarithm or additional screen threshold is introduced. The source-defined association interpretation and true-zero/missing distinctions remain in force.

### Confirmed UMD Land-Cover Reconstruction

The user selects University of Maryland land cover to reconstruct the five-period land context. This classification is read from its own annual source labels; it is not a recoding of IGBP labels. Six area shares are retained:

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
|---|---|---|---|---|---|
| Urban Land Cover Share | Urban Land Cover Share | control | Urban intersection area / full projected mesh area | UMD class 13 | yes |
| Forest Land Cover Share | Forest Land Cover Share | control | Forest intersection area / full projected mesh area | UMD classes 1-5 | yes |
| Cropland Land Cover Share | Cropland Land Cover Share | control | Cropland intersection area / full projected mesh area | UMD class 12 | yes |
| Water Land Cover Share | Water Land Cover Share | omitted reference | Water intersection area / full projected mesh area | UMD class 0 | yes |
| Shrublands and Grasslands | Shrublands and Grasslands | control | Group intersection area / full projected mesh area | UMD classes 6-10; includes closed and open shrublands, woody savannas, savannas and grasslands | yes |
| Barren | Barren | control | Barren intersection area / full projected mesh area | UMD class 15; includes bare soil, sand, rock and permanent snow/ice | yes |

Shrublands and Grasslands and Barren are numerical area proportions despite their shorter confirmed names. Native pixel/mesh intersection weights and the complete mesh-area denominator are reused exactly. Annual matching uses 2002, 2003, 2004, 2010 and 2024. A six-share sum equals accepted coverage rather than being normalized to one when coverage is partial. Observed class absence is zero; all six shares are NaN when no accepted source pixels cover the mesh. Unavailable source area and unresolved land are not statistically filled.

Accept the source's classified and adjusted quality states, and retain mask-identified water. Exclude unclassified land even where its fallback source label is Barren. Land Cover Unclassified Share continues to record both unresolved land and mask-identified water, so it overlaps the accepted-water reference and is not a disjoint residual. Land Cover Mask Identified Water Share makes this overlap explicit. The genuine unavailable-data reference is the residual after accepted coverage and unresolved land. Native source edition, published-tile availability and independent probe checks pass.

The reconstructed full panel retains 4,864,000 records and 211 readable columns; the core-balanced panel retains 4,832,000 records. All unrelated source columns and mesh-period keys are preserved exactly. The baseline-eligible candidate panel retains 383,390 meshes and 1,916,950 records, including 20 records without accepted land cover. Missing records are retained for model selection rather than automatically removed.

This reconstruction supersedes the IGBP land-cover construction for the new UMD dataset. Water Land Cover Share is the confirmed reference in the UMD extension. The five other shares and the six previously selected facilities enter the equation. Constant or redundant added controls may be omitted while their slopes remain unavailable; unidentified mandatory roads or population invalidate a fit. Sections 5-7 describe the authorized rerun. Previously accepted regression figures now use the validated UMD estimates. The active mesh screen and land-context display use the UMD reconstruction under MILI-D-20261011-027; earlier IGBP mesh and municipal evidence is preserved. The municipal UMD reconciliation now passes independent verification; earlier IGBP outputs remain historical evidence.

### Confirmed UMD Mismatch Context Checkpoint

Decision MILI-D-20261011-027 changes the land-context classification, without changing the peer-group structure or screening thresholds. Observed contexts contain Forest 248,182 meshes; Shrublands and Grasslands 60,455; Urban 33,747; Cropland 22,705; Water 18,159; Barren 34; and Incomplete coverage 104. No tied-dominance context is observed. Core values, geographic assignments, Population Band, Facility Presence and Rail Proximity Band agree exactly with the audited IGBP screen. All 1,499 UMD peer groups pass independent quartile and membership checks. The mesh screen is current UMD evidence. Current municipal fractions now use the same UMD screening, while the original IGBP municipal measures remain preserved for provenance.

### Validated UMD Municipal Context Checkpoint

All 383,386 mesh records and their existing government allocations remain retained. The ledger links 383,066 meshes to 1,741 governments and leaves 320 unavailable government links explicit. Of 66,097 UMD candidates, 66,059 are linked and thirty-eight remain unlinked. Every government has a supported candidate-fraction denominator. Seven governments lack traffic; selected fiscal values remain complete. Fiscal amounts, ratios, surveyed traffic values and source years agree exactly with the independently verified earlier inputs. All 1,741 government counts and thirty-two overall/context outcome correlations pass independent checks. Barren and Incomplete coverage remain in the overall aggregation even though omitted from the accepted land-context bar figure.

## 5. Identification Strategy

### Evidence Target and Design

The human-confirmed target is the road-economy association and its spatial heterogeneity. Nighttime Radiance proxies broader economic activity; Road Length Density measures source-defined provision. Potential overprovision and continuing maintenance pressure motivate the transportation question. The evidence comprises conditional level associations, relative comparable-context mismatch and descriptive municipal traffic and fiscal relationships. Causal identification is outside scope.

Supporting Point 1 uses same-sample national baseline and extended pooled models. Supporting Point 2 uses nine regional comparisons, forty-seven prefecture attempts, the extended local surface, latest mesh screening and land-context comparisons. Supporting Point 3 uses municipal scatter and overall and context-specific rank correlations. Spatial Distribution of Key Variables and Analytical Variables and Sample Coverage provide the foundation. Section 8 covers these questions through eight figures and five tables, including a main-text local coefficient map and a separate appendix estimation-support map.

### Common Cohort and Measurement

Formal comparisons use 383,386 meshes and 1,916,930 records, with identical area-specific baseline and extension samples. The earlier 383,390-mesh core cohort is preserved but is not substituted into this comparison. Four meshes with unavailable land cover are outside the extension; eligible islands and nineteen approved no-land-overlap exceptions remain.

Road/light periods are 2002, 2003, 2004, 2010 and 2024; matched census years are 2000, 2005, 2005, 2010 and 2020. Retain irregular timing, repeated 2005 population, the latest four-year gap, annual land cover and static facility replication. Reuse approved density-only zero coding and population structural zeros with provenance. No new filling, deletion, rescaling or analytical logarithm is selected.

Recent density comes from ordinary centerlines; historical density comes from supplied road-grid attributes. Common units do not establish source equivalence. Partial land coverage remains unnormalized; the omitted remainder includes unobserved area. Source definitions and proxy meaning qualify the associations.

### Models and Estimability

Use original-scale pooled OLS with an intercept and no fixed effects. Compare roads and population with the approved five land-cover shares and six facility controls. Administrative uncertainty uses mesh-clustered CR1 and normal 95 percent intervals. Ordinary R-squared measures joint fit. Individual intervals are unadjusted and do not test between-area coefficient differences.

The UMD rerun uses Water Land Cover Share as the omitted reference. Administrative and local fits omit constant or redundant added controls only, retain their coefficient values as unavailable, and record the omitted terms. A nuisance-control basis preserves the complete supported control column space. Mandatory Road Length Density and Population must remain identifiable conditional on that space; otherwise the coefficient vector is unavailable. No arbitrary core slope is assigned by deleting a conflicting control. GWPR repeats the approved three-to-fifty-kilometre integer grouped holdout search and fits the selected fixed-distance bisquare radius. No ridge, fallback radius or local significance procedure is introduced.

### Mismatch and Municipal Context

Reconstruct Potential Mismatch Candidate using the confirmed UMD Land Context and unchanged non-land peer bands, peer-size, all-zero-light support and quartile rules. Distinguish supported noncandidates, valid radiance zeros and unavailable screening. The companion land-context map colors only candidate meshes, linking screening locations directly to their backgrounds. Candidate composition does not establish higher within-context prevalence. Negative local slopes do not define candidates.

Municipal comparisons use Candidate Fraction of Supported Meshes, Length Weighted 24h Volume, Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale and Single Year Fiscal Revenue Need Ratio. Retain largest municipal land overlap within fixed Prefecture and verified designated-city parent consolidation. Preserve 320 unlinked meshes. The comparison contains 1,741 governments, 1,734 with usable traffic. The municipal scatter figure adds original-scale, single-predictor OLS fitted lines with an intercept as descriptive trend summaries; these are distinct from the conditional radiance models. Pearson correlations and conventional two-sided zero-correlation p values accompany the three overall scatter panels. Their reference test assumes independent bivariate-normal observations and does not account for spatial dependence; no causal interpretation follows.

Road/light 2024, population 2020, traffic 2021 and actual FY2023 finance form a linked cross-section. Territorial surveyed major-road traffic differs from own-government fiscal accounts. Land-context fractions are compared with whole-government outcomes. These relationships do not establish ownership-matched costs, deferred need, normative excessive provision or a causal fiscal effect.

Earlier IGBP estimates are retained for provenance. New UMD regression estimates must pass validation before they supply formal regression figures and tables. The active mesh mismatch and land-context outputs now use the separately authorized UMD reconstruction. Earlier IGBP mesh and municipal outputs retain their source identity. The separately authorized municipal reconciliation now supplies validated UMD candidate fractions, with unchanged geographic assignments, traffic and fiscal values; this update is distinct from the regression rerun. The fourth basic-map panel uses retained source-location points for the four facility categories already specified in the plan. No aggregate facility variable is constructed. All outputs are now specified.

## 6. Main Estimation Framework

Spatial heterogeneity is assessed through the existing nine-region and forty-seven-Prefecture pooled comparisons and the geographically weighted pooled coefficient surface. Existing failure mode diagnostics retain unavailable mandatory-core fits, omitted constant or redundant controls, local observation and effective-mesh support, and the common predictable support of bandwidth validation. The appendix estimation-support map documents these limitations alongside the main-text local surface. These are the confirmed heterogeneity analyses and estimability diagnostics, not additional robustness specifications or new computation.

### Descriptive Foundation

Compute equal-weight mesh means for the three core variables:

\[
\overline V_i=\frac{1}{5}\sum_{t\in\mathcal T}V_{it}.
\]

Here \(i\) indexes meshes, \(\mathcal T\) the five road/light periods, \(t\) an observed period, \(V_{it}\) Road Length Density, matched Population or Nighttime Radiance, and \(\overline V_i\) its five-observation mean. Use the census matches in Section 5. These are observation means, not continuous annual averages or regression transformations. Facilities use selected static snapshots. The facility panel displays accepted source-location points for School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count, with categories and source years distinguished; it does not create a facility total.

Analytical Variables and Sample Coverage summarizes twenty-two confirmed substantive variables. Use panel records for time-varying variables, distinct meshes for static facilities and screening, and governments for municipal measures. Report units, source dates, valid counts, missing percentages and numerical moments. Land Context receives category counts and proportions. Spatial Distribution of Key Variables uses actual mesh footprints and three means; the fourth panel shows the selected source-location points.

### National and Administrative Pooled Models

Use the combined baseline and extension specification:

\[
R_{it}=\beta_{0,a,b}+\beta_{D,a,b}D_{it}+\beta_{P,a,b}P_{it}
+b\left[\sum_{j=1}^{5}\delta_{j,a,b}\ell_{itj}
+\sum_{m=1}^{6}\eta_{m,a,b}Z_{im}^{(s_m)}\right]+e_{it,a,b}.
\]

Here \(R_{it}\), \(D_{it}\) and \(P_{it}\) are Nighttime Radiance, Road Length Density and Population; \(a\) indexes the national sample, Region or Prefecture containing mesh \(i\); \(b\) is zero for baseline and one for extension; \(\beta_{0,a,b}\) is the intercept, \(\beta_{D,a,b}\) and \(\beta_{P,a,b}\) the core slopes, and \(e_{it,a,b}\) the residual. The shares \(\ell_{itj}\), indexed by \(j\), are Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands and Barren; \(\delta_{j,a,b}\) are their slopes. Water Land Cover Share is the omitted reference subject to partial coverage. The controls \(Z_{im}^{(s_m)}\), indexed by \(m\), are Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count; \(s_m\) is the source edition and \(\eta_{m,a,b}\) its slope. In the baseline the bracketed terms are absent and their slopes unestimated. Earlier mesh and time definitions apply.

Estimate national, regional and prefecture models independently on identical area-specific samples. Apply mesh-clustered CR1:

\[
c_{a,b}=\frac{G_a}{G_a-1}\frac{N_a-1}{N_a-K_{a,b}}.
\]

Here \(c_{a,b}\) is the covariance correction, \(G_a\) mesh count, \(N_a\) record count and \(K_{a,b}\) the actual retained parameter count including intercept: three in the baseline and at most fourteen in the extension. Cluster all five mesh records together, use normal 95 percent intervals and preserve unidentified core-model vectors. Omitted constant or redundant control slopes and their intervals remain unavailable.

Report centered pooled fit:

\[
R_{a,b}^2=1-\frac{\sum_{i\in\mathcal I_a,t\in\mathcal T}\widehat e_{it,a,b}^2}
{\sum_{i\in\mathcal I_a,t\in\mathcal T}(R_{it}-\overline R_a)^2}.
\]

Here \(\mathcal I_a\) is the area's mesh set, \(\widehat e_{it,a,b}\) the fitted residual, \(\overline R_a\) its mean radiance and \(R_{a,b}^2\) joint fit. The comparison shares the denominator.

Outputs are National Road Associations, Regional Road Association Comparison, Prefecture Road Association Comparison and Regional Road Associations and Prefecture Road Associations. The two administrative figures pair baseline/extended forest estimates with maps of the extended road coefficient using the frozen administrative areas. Use one zero-centered diverging map scale across the two figures and distinguish unavailable fits from zero. Colors display area estimates, not local coefficients or significance. Administrative tables have six columns, combine coefficients and intervals, and state five-times-mesh record counts in notes. Attempt all forty-seven Prefectures, including Tokyo and Nara, under the confirmed constant/redundant-control rule.

When an additional control is redundant, retained nuisance coefficients are parameters of the selected basis and do not all have a common water-reference interpretation. Roads and population are reported only when uniquely identifiable against the complete nuisance span.

### Extended Geographically Weighted Pooled Model

Let \(\mathbf x_{it}\) contain the intercept and thirteen extended predictors. Estimate:

\[
\widehat{\boldsymbol\vartheta}_{A(s,h)}
=\arg\min_{\boldsymbol\vartheta_{A(s,h)}}\sum_{i,t}w_i(s,h)
[R_{it}-\mathbf x_{it,A(s,h)}^\top\boldsymbol\vartheta_{A(s,h)}]^2.
\]

Here \(s\) is the focal centroid, \(h\) bandwidth in kilometres, \(A(s,h)\) the retained parameter set, \(\boldsymbol\vartheta_{A(s,h)}\) its coefficient vector, the hat its estimate, \(\mathbf x_{it,A(s,h)}\) the retained design, \(w_i(s,h)\) mesh weights and \(\top\) transpose. Retain intercept, mandatory roads and population, and varying added controls.

Use bisquare weights:

\[
w_i(s,h)=[1-(d(s,s_i)/h)^2]^2\mathbf1\{d(s,s_i)<h\}.
\]

Here \(s_i\) is the mesh centroid, \(d(s,s_i)\) great-circle distance using radius 6371.0088 kilometres and \(\mathbf1\) an indicator. All five records share mesh weights. Final fits include their focal mesh.

An added control is constant when its range is no greater than \(\tau\) times the larger of one and its maximum absolute training value; \(\tau=10^{-12}\) is the existing tolerance. Keep its slope unavailable and absorb its constant contribution into the intercept. Build a deterministic independent nuisance basis in the listed control order using twice-reorthogonalized residuals. A normalized residual norm at most \(10^{-10}\) denotes redundant information. Keep omitted slopes unavailable. Constant mandatory predictors or a rank-deficient retained design leave fits unavailable. This preserves the nuisance span rather than resolving core/control aliasing by dropping a substantive control. Numerical centering and scaling preserve original units and do not introduce fixed effects. The smallest eigenvalue of the centered column-normalized design Gram matrix must exceed \(10^{-12}\).

Repeat the integer search over three to fifty kilometres, holding out all five records of each validation mesh and comparing:

\[
\operatorname{CV}(h)=
\frac{\sum_{q\in\mathcal V}\omega_q[\frac15\sum_{t\in\mathcal T}
(R_{qt}-\widehat R_{qt}^{(-q,h)})^2]}
{\sum_{q\in\mathcal V}\omega_q}.
\]

Here \(q\) indexes validation meshes, \(\mathcal V\) the identical predictable and estimable center set, \(\omega_q\) tile-expansion weights, \(\widehat R_{qt}^{(-q,h)}\) held-out prediction excluding all records of mesh \(q\), and \(\operatorname{CV}(h)\) weighted radiance-level mean squared error. A held-out control differing from an omitted training constant or affine redundancy relation leaves prediction unavailable. Use the same predictable center set for all radii, retain tile-expansion weights and report the fraction of validation support represented. Changing-support scores do not rank radii.

The completed UMD search evaluates forty-eight integer radii using 985 identical predictable validation centers, representing 75.252636 percent of tile-expansion weight. The conditional minimum is 5 kilometres with radiance-level RMSE 1.774688; this is not a proven national optimum. The full UMD surface contains 357,316 estimable and 26,070 unavailable focal vectors. Earlier IGBP estimates retain their source identity. Retain all 383,386 focal meshes, including failures and fewer-than-thirty-record support flags; report positive-weight and effective-weight meshes separately. Local Road Associations across Japan shows the coefficient surface in the main text. Local Road Association Estimation Support separately documents model availability and small-neighborhood flags in the appendix. Both use the same unchanged local results. No local significance inference is selected. Local training fit differs from national pooled fit and validation error.

### Accepted Comparable-Context Screen

Reconstruct UMD peers defined by Region; Population bands zero, 1-9, 10-49, 50-199, 200-999, 1000-4999 and at least 5000; Land Context; presence of any four selected facility totals; and Distance to Railway Station bands below one, one to below five, and at least five kilometres. Retain incomplete coverage and any tied dominance in Land Context. Distance to Passenger Airport is not matched. Do not reoptimize peer rules.

Use:

\[
S_i=\mathbf1\{n_{g(i)}\geq30\}\mathbf1\{\max_{j:g(j)=g(i)}R_j>0\},
\qquad
C_i=\begin{cases}
\mathbf1\{D_i>0\}\mathbf1\{D_i>Q_{D,g(i)}(0.75)\}
\mathbf1\{R_i\leq Q_{R,g(i)}(0.25)\},&S_i=1,\\
\text{undefined},&S_i=0.
\end{cases}
\]

Here \(g(i)\) is the peer stratum, \(n_{g(i)}\) its distinct-mesh count, \(S_i\) support, \(C_i\) Potential Mismatch Candidate, and \(D_i\) and \(R_i\) latest road density and radiance. The quantities \(Q_{D,g(i)}(0.75)\) and \(Q_{R,g(i)}(0.25)\) are empirical quartiles; \(j\) indexes peers in the maximum. Retain existing linear-interpolation quartiles, strict road and inclusive light comparisons. Undefined status stays missing. Positive-constant and zero lower-quartile groups receive diagnostics without new exclusions.

The validated UMD screen has 376,219 supported meshes, 66,097 candidates and 7,167 unavailable indicators. All 1,499 peer groups pass independent checks. There are 172 meshes in all-zero-radiance groups, all already below thirty peers. Spatial Distribution of Potential Mismatch maps candidate/support states in panel a and UMD Land Context only for candidate meshes in panel b. Other analytical meshes remain muted background in panel b; all observed contexts remain in its legend with candidate counts, including zero counts. Potential Mismatch by Land Context shows candidate percentages among supported meshes and source-zero-radiance percentages among candidates with both denominators for five displayed contexts: Forest, Shrublands and Grasslands, Urban, Cropland and Water. Barren and Incomplete coverage are omitted from this figure only under MILI-D-20261011-031; their records and the complete summary remain retained. Retain seven observed UMD contexts: Urban, Forest, Cropland, Shrublands and Grasslands, Water, Barren and Incomplete coverage. Tied dominance remains a separate context if observed. These are relative patterns, not measured economic inactivity or excessive length.

### Municipal Descriptive Associations

For overall and context-specific scope use:

\[
q_{u,c}=\frac{\sum_{i\in\mathcal I_{u,c}:S_i=1}C_i}
{\sum_{i\in\mathcal I_{u,c}}S_i}.
\]

Here \(u\) indexes governments, \(c\) overall scope or Land Context, \(\mathcal I_{u,c}\) assigned meshes and \(q_{u,c}\) Candidate Fraction of Supported Meshes. Prior support definitions apply; zero supported denominators stay unavailable.

Retain:

\[
v_u=\frac{\sum_{k\in\mathcal K_u}l_k t_k}{\sum_{k\in\mathcal K_u}l_k},
\qquad b_u^E=m_u/e_u,\qquad b_u^S=m_u/z_u,\qquad f_u=r_u/n_u.
\]

Here \(\mathcal K_u\) contains territory-coded segments with positive source length and available daily traffic; \(k\) indexes segments, \(l_k\) length, \(t_k\) published twenty-four-hour volume and \(v_u\) Length Weighted 24h Volume. The amounts \(m_u\), \(e_u\), \(z_u\), \(r_u\) and \(n_u\) denote own-government road-plus-bridge maintenance, total expenditure, standard fiscal scale, standard fiscal revenue and standard fiscal need in actual FY2023, in thousand yen. The ratios \(b_u^E\), \(b_u^S\) and \(f_u\) are Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale and Single Year Fiscal Revenue Need Ratio. Empty or zero denominators stay missing. Source amounts explain existing constructions rather than add controls.

For each outcome compute:

\[
\rho_{c,o}=\operatorname{Corr}_{u\in\mathcal U_{c,o}}
(\operatorname{rank}(q_{u,c}),\operatorname{rank}(Y_{u,o})).
\]

Here \(o\) selects \(v_u\), \(b_u^E\), \(b_u^S\) or \(f_u\), \(Y_{u,o}\) is that whole-government outcome, \(\mathcal U_{c,o}\) the available pair set and \(\rho_{c,o}\) its Spearman correlation using average-tie ranks. Report pair counts: overall traffic 1,734, fiscal outcomes 1,741, and varying context counts. The user subsequently selects conventional Pearson p values for the three overall scatter panels; the rank-correlation table remains descriptive. No temporal replication is selected.

For the three overall scatter outcomes, compute Pearson correlation and its conventional two-sided p value on the same original-scale available pairs:

\[
r_o=\operatorname{Corr}_{u\in\mathcal U_{\mathrm{all},o}}(q_{u,\mathrm{all}},Y_{u,o}),
\qquad t_o=r_o\sqrt{\frac{N_o-2}{1-r_o^2}},
\qquad p_o=2\Pr\left(T_{N_o-2}\geq |t_o|\right).
\]

Here \(r_o\) is the Pearson coefficient, \(N_o\) the available pair count, \(t_o\) the zero-correlation test statistic, \(T_{N_o-2}\) a Student t reference variable with \(N_o-2\) degrees of freedom and \(p_o\) the two-sided p value. Previously defined outcomes and available pairs apply. The test assumes independent bivariate-normal observations, uses no spatial or multiple-comparison correction and does not test the Spearman coefficient. Report the Pearson coefficient beside its p value; display values with \(p_o<0.001\) as "p < 0.1%" and retain exact computed values in the verification record. Treat these as conventional reference tests rather than evidence of a causal effect or spatially adjusted uncertainty.

For the three overall municipal scatter panels, fit the original-scale descriptive line:

\[
(\widehat{a}_o,\widehat{d}_o)=\operatorname*{argmin}_{a_o,d_o}
\sum_{u\in\mathcal U_{\mathrm{all},o}}
\left(Y_{u,o}-a_o-d_o q_{u,\mathrm{all}}\right)^2,
\qquad \widehat{Y}_{u,o}=\widehat{a}_o+\widehat{d}_o q_{u,\mathrm{all}}.
\]

Here \(a_o\) and \(d_o\) are the outcome-specific intercept and slope, and hats denote their OLS estimates. Reuse the available pair set and previously defined outcomes, selecting only \(v_u\), \(b_u^E\) and \(f_u\) for this figure. All fits use unweighted individual governments and original values without a logarithm. Display candidate fractions and maintenance shares as percentages; this changes display units only. Draw dashed fitted lines over the observed predictor range, retain all finite observations and use linear axes. These lines summarize unconditional linear association; they add no controls, confidence bands or causal interpretation. The separately displayed p values concern Pearson zero correlation, not the Spearman coefficient. Unconstrained lines can cross below zero within the observed predictor range; retain those segments transparently as a limitation of the linear summary, rather than interpret them as plausible outcome predictions.

The candidate fractions have been reconciled to the validated UMD screen using the accepted jurisdiction ledger and unchanged existing outcomes. Historical IGBP results remain provenance. All 1,741 government counts and thirty-two overall/context outcome correlations pass independent checks; unavailable screening and zero supported denominators remain missing. Municipal Mismatch, Traffic and Fiscal Context plots overall fractions against traffic, maintenance/expenditure and fiscal revenue/need. Municipal Mismatch, Traffic and Fiscal Correlations includes overall plus seven contexts, four outcomes and paired counts. Context-specific fractions remain paired with whole-government outcomes.

## 7. Analytical Workflow

### Evidence-to-Output Sequence

Connect confirmed inputs to Section 6 specifications and exact Section 8 titles. UMD regression evidence and the separately authorized UMD mesh screen have passed numerical validation. Earlier IGBP numerical evidence remains historical. UMD municipal reconciliation passes independent verification. All eight figures and five tables have completed visual and human review. The output critique identified three minor provenance/status inconsistencies, resolved under the confirmed handoff revision. Support statements concern descriptive claims, and output acceptance does not resolve measurement or inference limits.

| step | variables used | formula/model used | generated figure/table title | theory or claim evaluated | support status |
| --- | --- | --- | --- | --- | --- |
| Verify coverage and dates | Twenty-two Confirmed Active Analytical Variables; Region and Prefecture | Section 4 construction and Section 5 cohort | Analytical Variables and Sample Coverage | Measurements are traceable at the stated units | Coverage verified; table accepted; source equivalence remains limited |
| Show spatial foundation | Road Length Density, Population, Nighttime Radiance; School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count as facility categories represented by retained source points | Five-observation mesh means and selected source-location points | Spatial Distribution of Key Variables | Spatial concentration frames the road-economy question | Three mesh means and a category-specific source-point panel completed and accepted |
| Compare national association | Nighttime Radiance, Road Length Density, Population and eleven added controls named in Section 6 | National pooled models, CR1 and centered fit | National Road Associations | Supporting Point 1: association conditional on observed context | Conditional association supported descriptively; same-sample baseline and extended table accepted |
| Compare administrative association | Same pooled variables; Region and Prefecture | Separate same-sample area models | Regional Road Association Comparison; Prefecture Road Association Comparison; Regional Road Associations and Prefecture Road Associations | Supporting Point 2: geographic variation | UMD geographic variation described; nine Regions and all forty-seven Prefectures represented in accepted maps and tables; no formal difference test |
| Verify and map local association | Same extended predictors and Nighttime Radiance; mandatory Road Length Density and Population | Repeated three-to-fifty-kilometre holdout validation and selected UMD local model | Local Road Associations across Japan; Local Road Association Estimation Support | Supporting Point 2: variation beyond administrative averages | Main-text coefficient map and appendix support map accepted; descriptive variation on estimable neighborhoods; coefficient precision and significance remain unestablished |
| Locate relative mismatch | Potential Mismatch Candidate, Land Context, Road Length Density and Nighttime Radiance; Population, Region, land shares, four facility counts and Distance to Railway Station define peers | Validated UMD nullable support/quartile screen; candidate/support map and candidate-only thematic land-context map | Spatial Distribution of Potential Mismatch | Supporting Point 2: high provision with low activity-proxy values in coarse contexts | Relative pattern supported by the accepted candidate and land-context maps; normative overprovision untested |
| Compare land backgrounds | Potential Mismatch Candidate, Land Context and Nighttime Radiance | Supported-candidate and candidate-zero-radiance proportions | Potential Mismatch by Land Context | Supporting Point 2: context and proxy-information differences | Context contrasts documented in the accepted bar figure; economic inactivity unestablished |
| Compare municipal outcomes | Candidate Fraction of Supported Meshes, Length Weighted 24h Volume, Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale, Single Year Fiscal Revenue Need Ratio and Land Context | Available-pair Spearman; overall Pearson and conventional two-sided p values; original-scale single-predictor OLS dashed lines in scatter | Municipal Mismatch, Traffic and Fiscal Context; Municipal Mismatch, Traffic and Fiscal Correlations | Supporting Point 3: mismatch, utilization and fiscal context | Accepted scatter and full correlation table partially support the contextual story; urban contrasts limit uniform generalization; owner-matched costs untested |

### Checkpoints

Verify current samples, definitions, source years, static replication and zero/missing coding before rendering. Reuse existing validated pooled coefficients and covariance, local vectors, screening and ratios when provenance agrees. This planning step does not rerun estimation.

Both national models use the 383,386-mesh extension cohort. Administrative partitions recover nine Regions and forty-seven Prefectures. Use UMD control bases for all Prefectures, including Tokyo and Nara; retain omission/failure records and six-column tables. Joint fit is reported alongside road association.

The main-text local coefficient map and separate appendix estimation-support map use the validated expanded UMD surface at its selected radius. Earlier IGBP and core-only surfaces retain their original identity. Retain all focal meshes, omitted controls, failed vectors and small-neighborhood flags in both independent figures. Distinguish fitted zero and unavailable slopes. If a limited visual scale is required for extreme slopes, disclose its limits and preserve full values.

Reconcile 383,386 UMD-screened meshes, 376,219 supported cases, 66,097 candidates and 7,167 unavailable indicators. Keep all seven contexts in screening data and the complete audit summary, with both percentage denominators. Display only the five confirmed contexts in Potential Mismatch by Land Context; omitting its Barren and Incomplete coverage rows does not alter the analytical sample or other outputs. Do not exclude source-zero radiance, population zeros, forests or eligible islands.

Reconcile 1,741 governments, seven unavailable traffic values and 320 unlinked mesh records. Thirty-eight current UMD candidate meshes lack financial-government links and are not reassigned; the earlier forty-unlinked-candidate IGBP count remains historical. Report each pair count, weak or opposite urban associations and small incomplete-coverage samples. Present the full context comparison.

The chain supports a traceable national association, spatial heterogeneity, relative mismatch and qualified municipal context. It only partially supports the overprovision and maintenance-pressure policy narrative because normative excess stock and flagged-road maintenance liabilities are unmeasured. Causal identification remains outside the objective.

### Handoff

Sections 3-4 specify the data and final variables needed for the confirmed descriptive evidence chain. The UMD regression rerun, nuisance-basis verification and grouped bandwidth search are complete. UMD mesh screening and municipal reconciliation are independently validated. The current formal comparisons use the 383,386-mesh extended cohort; older baseline-only tables from the 383,390-mesh cohort remain historical evidence outside the active handoff. Earlier IGBP results retain their historical identity. Source-location points provide the accepted facility display without a new aggregate. No new model, sample rule, variable or estimation run is selected by the handoff revision.

The approved generation sequence is complete: eight figures, followed by five tables, each generated and reviewed individually. Analytical Variables and Sample Coverage supplies the descriptive table foundation; the local coefficient map and estimation-support map are separate main-text and appendix outputs. The critique and confirmed corrections reconcile the active output inventory, municipal caption provenance and workflow completion statements. The next step is construction of the manuscript content dictionary, carrying forward the exact evidence dependencies and interpretation boundaries. No output is marked complete solely because an exploratory counterpart exists.

### Validated UMD Regression Checkpoint

The UMD rerun retains 383,386 meshes and 1,916,930 records. National, nine regional and forty-seven Prefecture comparisons use the same baseline and extended area samples, the confirmed Water Land Cover Share reference and mesh-clustered CR1 with actual retained rank. The grouped holdout search selects 5 kilometres on identical estimable validation support. The local result retains 357,316 estimable and 26,070 unavailable focal vectors. All focal identifiers, omitted-control references and small-neighborhood flags are preserved. At the original numerical checkpoint, formal regeneration and review had not yet occurred, and the regression rerun itself did not update screening. Subsequent formal regression figures and tables have been generated from these validated UMD estimates and accepted. The separately authorized UMD screen passes validation with 66,097 candidates, and municipal reconciliation supplies validated UMD fractions with unchanged traffic/fiscal values and geography. The screening and municipal figures and tables are also accepted. Earlier IGBP outputs remain historical. All thirteen current outputs are complete; the confirmed consistency corrections do not change their analytical values.

### Validated UMD Municipal Association Checkpoint

Overall candidate-fraction associations have descriptive Spearman correlations of -0.591 with territorial surveyed traffic (1,734 pairs), +0.269 with Maintenance Share of Expenditure, +0.280 with Maintenance Share of Standard Fiscal Scale and -0.484 with Single Year Fiscal Revenue Need Ratio (1,741 pairs for each fiscal outcome). The overall pattern is consistent with lower surveyed traffic, a higher realized maintenance-spending share and lower standard fiscal-resource coverage where candidate fractions are larger. This partially supports the contextual transport/fiscal story, without identifying excess-road costs, causality or ownership-matched liabilities. Urban-context correlations remain weak and differ in sign: +0.045 for traffic, -0.062 for maintenance/expenditure and +0.098 for revenue/need. Barren has no supported context fractions; Incomplete coverage has only ten traffic pairs and thirteen fiscal pairs. Preserve these unavailable and small-sample contexts in the complete summaries and planned correlation table.

## 8. Figure and Table Plan

The confirmed plan links the central research question and its three supporting points through basic spatial distributions, national conditional association, administrative and local spatial heterogeneity, potential mismatch, and municipal traffic and fiscal context. The plan contains eight figures and five tables. Spatial Distribution of Key Variables, Regional Road Associations, Prefecture Road Associations, Local Road Associations across Japan and Local Road Association Estimation Support are accepted and complete. The two independent local maps appear in the main text and appendix respectively. Spatial Distribution of Potential Mismatch, Potential Mismatch by Land Context and Municipal Mismatch, Traffic and Fiscal Context are also accepted and complete. All eight figures and all five tables are accepted and complete. The formal output set has completed critique. The confirmed consistency revision resolves the historical-table inventory, municipal caption provenance and workflow status; the active set is ready for construction of the manuscript content dictionary. This presentation revision preserves the model, variables and estimation results.

### Figures

| title | what it expresses | figure type | subpanels | key variables | status |
| --- | --- | --- | --- | --- | --- |
| Spatial Distribution of Key Variables | Establish the spatial context of road provision and economic activity using five-period mesh means of Road Length Density, Population and Nighttime Radiance, plus source-location points for the four selected facility snapshots. | mesh map and point map | 4 | Nighttime Radiance, Road Length Density, Population, School Facility Count, Medical Facility Count, Logistics Facility Count, Visitor and Event Facility Count | done |
| Regional Road Associations | Compare baseline and extended road-density coefficients with individual mesh-clustered 95 percent intervals across nine Regions in a forest panel and locate the extended associations in an administrative-area map; distinguish unavailable estimates. | forest and administrative map | 2 | Nighttime Radiance, Road Length Density, Population, Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands, Barren, Water Land Cover Share, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count, Visitor and Event Facility Count, Region | done |
| Prefecture Road Associations | Compare baseline and extended road-density coefficients with individual mesh-clustered 95 percent intervals across forty-seven Prefectures in a forest panel and locate the extended associations in an administrative-area map; distinguish unavailable estimates. | forest and administrative map | 2 | Nighttime Radiance, Road Length Density, Population, Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands, Barren, Water Land Cover Share, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count, Visitor and Event Facility Count, Prefecture | done |
| Local Road Associations across Japan | Main-text figure showing spatial variation in extended geographically weighted pooled road-density coefficients, distinguishing unavailable fits from zero slopes. | mesh map | 1 | Nighttime Radiance, Road Length Density, Population, Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands, Barren, Water Land Cover Share, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count, Visitor and Event Facility Count | done |
| Local Road Association Estimation Support | Appendix figure documenting estimable neighborhoods, fewer-than-thirty-record support flags and unavailable local fits for the same local association surface. | mesh map | 1 | Nighttime Radiance, Road Length Density, Population, Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands, Barren, Water Land Cover Share, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count, Visitor and Event Facility Count | done |
| Spatial Distribution of Potential Mismatch | Locate supported potential mismatch candidates in 2024, distinguish unsupported screening from supported noncandidates, and color candidate meshes only by their UMD land context in the companion map. | mesh map | 2 | Potential Mismatch Candidate, Land Context, Road Length Density, Nighttime Radiance | done |
| Potential Mismatch by Land Context | Compare candidate fractions among supported meshes and valid zero-radiance fractions among candidates for Forest, Shrublands and Grasslands, Urban, Cropland and Water; omit Barren and Incomplete coverage from this figure only. | bar | 2 | Potential Mismatch Candidate, Land Context, Nighttime Radiance | done |
| Municipal Mismatch, Traffic and Fiscal Context | Describe how current UMD municipal candidate fractions relate to surveyed traffic, maintenance shares of expenditure and fiscal resources in three scatter panels arranged on a two-by-two canvas with the fourth slot empty; show original-scale OLS dashed lines, pairwise available counts, descriptive Spearman correlations, and Pearson coefficients with conventional two-sided p values. | scatter | 3 | Candidate Fraction of Supported Meshes, Length Weighted 24h Volume, Maintenance Share of Expenditure, Single Year Fiscal Revenue Need Ratio | done |

### Tables

| title | what it expresses | rows | columns | row meaning | column meaning | status |
| --- | --- | --- | --- | --- | --- | --- |
| Analytical Variables and Sample Coverage | Document the units, actual source periods, coverage, missingness and distributions of the twenty-two confirmed substantive variables, separating panel, mesh-screen and government units. | 22 | 9 | One confirmed substantive variable per row; categorical distributions are described in notes rather than assigned numeric moments | Variable; unit; source periods; statistical unit; valid count; missing percentage; mean; standard deviation; median | done |
| National Road Associations | Compare same-sample baseline and extended national pooled associations in a stargazer-style model-column table, with mesh-clustered standard errors and significance stars. | 34 | 3 | Fourteen paired coefficient and parenthesized standard-error lines, with the intercept last, followed by six diagnostic rows | Term or diagnostic; Baseline model; Extended model; full numerical coefficients and 95 percent intervals are retained separately | done |
| Regional Road Association Comparison | Provide a compact comparison of baseline and extended road associations for the nine transportation-statistics Regions. | 9 | 6 | One Region per row | Region; baseline Road Length Density coefficient with significance stars and its 95 percent interval; extended Road Length Density coefficient with significance stars and its 95 percent interval; mesh count; baseline centered R-squared; extended centered R-squared | done |
| Prefecture Road Association Comparison | Provide the complete forty-seven-Prefecture comparison in a compact appendix table, retaining unavailable extended estimates. | 47 | 6 | One Prefecture per row, including those with unavailable extended estimates | Prefecture; baseline Road Length Density coefficient with significance stars and its 95 percent interval; extended Road Length Density coefficient with significance stars and its 95 percent interval; mesh count; baseline centered R-squared; extended centered R-squared | done |
| Municipal Mismatch, Traffic and Fiscal Correlations | Compare descriptive Spearman associations overall and by land context using both maintenance-share denominators and actual pairwise available samples. | 8 | 9 | Overall plus seven retained land contexts; each context-specific fraction is paired with whole-government outcomes | Scope; Spearman coefficient and paired government count for each of Length Weighted 24h Volume, Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale and Single Year Fiscal Revenue Need Ratio | done |

### Variable Coverage and Display Rules

Every currently specified substantive input and geographic stratum is present in Section 4 with its latest final-variable assignment set to yes. Regression coefficients, confidence intervals, fit statistics, screening denominators, estimation status and summary percentages are output statistics or retained diagnostics rather than new explanatory variables.

Spatial Distribution of Key Variables uses a two-by-two layout with actual mesh footprints and consistent geographic extents and island insets. Road Length Density, Population and Nighttime Radiance use equal-weight means over the five observed road/light periods: 2002, 2003, 2004, 2010 and 2024. Population retains the matched 2000, 2005, 2005, 2010 and 2020 snapshots, including repeated use of 2005. These are averages of observations rather than annual averages over the intervening years. Static facilities use their selected source snapshots. Display scaling must retain a distinct zero category and missing category and must not alter analytical values.

The fourth panel of Spatial Distribution of Key Variables displays retained source-location points corresponding to School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count, distinguished by category and actual source edition. Use the same approved analytical mesh footprint as the three mean panels. Retain the accepted within-category selection and duplicate rules without combining categories into a new total, moving points to mesh centroids or jittering coordinates. The point coordinates are retained geographic references, not additional regression variables. No aggregate facility-count variable is required.

National Road Associations and both administrative comparison tables use the same approved extended cohort for the baseline and extended models. Under MILI-D-20261011-040, the national table uses three stargazer-style columns with a shared Nighttime Radiance outcome heading, numbered model columns, coefficients above parenthesized mesh-clustered CR1 standard errors, the intercept last and diagnostic rows below. Use serif type, a white background and horizontal rules without vertical gridlines. Stars use the existing two-sided normal-reference coefficient p values: one for \(p<0.10\), two for \(p<0.05\) and three for \(p<0.01\). Retain six-decimal display precision to keep small coefficients and standard errors visible. Preserve full numerical details and 95 percent intervals separately; no model, sample, uncertainty estimator or other planned table is changed. Regional Road Associations and Prefecture Road Associations show these same comparisons in separate figures. Each combines a forest panel for both models with an administrative-area map of the extended road coefficient. Use the frozen administrative reference, the accepted nine-region grouping, geographic island insets and a shared continuous diverging map scale centered on zero. Unavailable extended estimates remain distinctly gray. Administrative color fills represent area-level coefficients, not mesh-specific estimates or complete within-area data coverage. Forest intervals retain their original values without truncation; maps do not encode significance. Individual map colors do not identify excessive provision. The two administrative tables have six columns, combining each road coefficient with its confidence interval. Under MILI-D-20261011-042, Regional Road Association Comparison adds stars directly to each road coefficient, using the existing two-sided normal-reference p values and the national-table thresholds: one for \(p<0.10\), two for \(p<0.05\) and three for \(p<0.01\). These are individual coefficient tests without multiple-testing adjustment; retain the 95 percent intervals and six-column layout. Prefecture Road Association Comparison follows the same significance-marker convention when the approved sequence proceeds under MILI-D-20261011-043; retain all forty-seven rows and disclose omitted constant or redundant controls in notes. Under MILI-D-20261011-044, display all forty-seven Prefectures in one continuous six-column table image rather than separate page images; retain the complete workbook sheet and unchanged numerical estimates. Observation counts are reported in notes as five times the mesh count for the verified balanced cohort; any departure must be reported explicitly. Codes, administrative levels and estimation status are removed as separate columns. Attempt Tokyo and Nara under the approved UMD constant/redundant-control rule; disclose omitted controls and any remaining unavailable core estimates in table notes. Individual intervals do not constitute a formal test of between-area coefficient differences.

Local Road Associations across Japan presents the approved extended geographically weighted pooled road-density coefficient surface as an independent main-text figure. Local Road Association Estimation Support is a separate appendix figure using the same focal meshes, selected bandwidth and model results. Both use actual mesh footprints and distinguish unavailable local fits from zero slopes; the appendix additionally shows estimable neighborhoods below thirty observation records. Neither single-map figure carries a panel letter. Local significance shading is not selected because local uncertainty estimates have not been produced. Model outputs and support diagnostics remain distinct from Potential Mismatch Candidate. The UMD fit and its support rules have passed numerical verification; both independent local maps have passed visual and human review.

Spatial Distribution of Potential Mismatch and Potential Mismatch by Land Context use the validated 2024 UMD reconstruction under MILI-D-20261011-027, without changing the accepted peer-group structure or screening thresholds. Candidate fractions use supported comparison meshes as the denominator; unsupported cases remain unavailable. Valid zero-radiance values remain visible and are not interpreted as measured zero economic activity. Forest, Shrublands and Grasslands, Urban, Cropland, Water, Barren and Incomplete coverage remain represented. Any tied-dominance context must also be retained if observed. For Potential Mismatch by Land Context, MILI-D-20261011-031 selects five displayed contexts: Forest, Shrublands and Grasslands, Urban, Cropland and Water. Barren and Incomplete coverage are omitted from that bar figure only, retained in source data, the complete screening summary and the previously accepted mesh map. Within-context numerators and denominators are unchanged. Under MILI-D-20261011-028, panel a maps supported candidates, supported noncandidates and unavailable screening; panel b colors only candidate meshes by UMD Land Context, with all other analytical meshes shown as muted geographic background. Its legend reports candidate counts by context, including zero-candidate contexts; these counts are not within-context candidate rates. Both maps retain the same extents, actual mesh footprints, island insets and 600 dpi export.

Municipal Mismatch, Traffic and Fiscal Context and Municipal Mismatch, Traffic and Fiscal Correlations retain the approved government assignments, pairwise available counts and source dates: road/light 2024, matched population 2020, surveyed traffic 2021 and fiscal year 2023. Context-specific candidate fractions are compared with whole-government traffic and fiscal outcomes. The seven unavailable traffic outcomes remain missing. Both Maintenance Share of Expenditure and Maintenance Share of Standard Fiscal Scale are included in the correlation table; the scatter figure uses Maintenance Share of Expenditure. The validated UMD aggregation supplies current municipal fractions. Under MILI-D-20261011-034, the three scatter panels occupy a two-by-two canvas with the bottom-right slot empty. Retain all available observations, including zero maintenance values, and use linear axes for all outcomes. Add original-scale, single-predictor OLS fitted lines with an intercept, drawn as dashed lines over each observed predictor range. Under MILI-D-20261011-035, show actual available counts, descriptive Spearman correlations, and Pearson coefficients with conventional two-sided p values, without confidence bands. The p values refer only to Pearson zero correlation and are unadjusted for spatial dependence and multiple comparisons. Under MILI-D-20261011-036, show p values below 0.1 percent as "p < 0.1%" rather than scientific notation; preserve exact calculations in the verification record. Source values and the planned rank-correlation table are unchanged. Small context-specific samples must be identified. The comparisons describe relationships and spatial heterogeneity relevant to the road-maintenance policy motivation.

### Table Input Coverage

Analytical Variables and Sample Coverage uses the twenty-two variables in the Confirmed Active Analytical Variables subsection of Section 4, including Barren as a control and Water Land Cover Share as the omitted reference. Mesh-level descriptive mismatch and Land Context now use UMD. Current municipal candidate fractions and land-context summaries now use the validated UMD reconciliation. Earlier IGBP outputs remain historical. Fiscal and surveyed-traffic values and actual source years are unchanged. Numerical statistics use each variable's stated statistical unit; Land Context receives category counts and proportions in notes.

National Road Associations, Regional Road Association Comparison and Prefecture Road Association Comparison use Nighttime Radiance, Road Length Density, Population, Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands, Barren, Water Land Cover Share, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count. Region and Prefecture define the corresponding geographic strata.

Municipal Mismatch, Traffic and Fiscal Correlations uses Candidate Fraction of Supported Meshes, Length Weighted 24h Volume, Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale, Single Year Fiscal Revenue Need Ratio and Land Context.

### Execution Order

Estimation-framework-planning has reconciled Sections 5-7 with the confirmed output selection and validated estimation and screening contracts. The eight figures and five tables were generated and reviewed individually in the approved sequence. Critique and the confirmed consistency corrections are complete; there are no pending planned outputs. Proceed to construction of the manuscript content dictionary, preserving the accepted titles, evidence boundaries and main-text/appendix allocation. No figure or table is marked done merely because an exploratory counterpart exists.
