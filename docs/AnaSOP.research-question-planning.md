# AnaSOP
Analysis Standard Operating Procedure

## 1. Research Objective

### Central Research Question

- Research question: How does the alignment between road-network provision and economic activity vary spatially across Japan, and what traffic-utilization and maintenance-fiscal characteristics accompany potential mismatch?
- Why it matters: Persistent transport infrastructure can coexist with very different levels of local economic activity. Spatially differentiated evidence can inform discussion of road-network maintenance and potential overprovision.
- Current data support: The approved national analytical cohort links five road/light periods, matched population, annual land cover and selected static facilities. National, regional, prefectural and geographically weighted pooled analyses are completed. A separate latest-period screen and municipal traffic/fiscal summaries provide complementary descriptive evidence.
- Key readable constructs: Road Length Density, Nighttime Radiance as a proxy for broader economic activity, Population, the approved land-cover and facility controls, potential mismatch fractions, surveyed traffic and maintenance/fiscal ratios.
- What would verify the proposed account: Road-activity associations vary geographically on estimable support, relative mismatch patterns can be described transparently, and municipal comparisons characterize their observed traffic and fiscal context.
- What would weaken the proposed account: Spatial patterns are uniform, unstable or driven predominantly by measurement/support artifacts; mismatch shows little association with traffic or fiscal context. Mixed or near-zero findings remain informative rather than being excluded.
- Required feasibility check: Confirm the evidence coverage and measurement meaning for each supporting question. The target is association and spatial heterogeneity; causal identification is outside scope.

### Supporting Research Questions

#### Supporting Point 1: National conditional road-activity association

- Role relative to the central question: Establish the national relationship before examining spatial variation.
- Research question: How is road density associated with economic activity proxied by nighttime radiance, conditional on population, and how does the estimated association differ after adding the approved land-cover and facility context?
- Why it matters: The national reference allows subsequent spatial patterns to be interpreted relative to a common aggregate relationship.
- Current data support: The same-sample baseline and extended national pooled equations use 383,386 meshes and 1,916,930 records. The estimated road coefficient is approximately 0.226693 in the baseline and 0.019558 in the extension. These are existing observations, not predetermined expected answers.
- Key readable variables: Nighttime Radiance, Road Length Density, Population, five included Land Cover Share variables, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count. Other Land Cover Share remains the reference and is retained in the data.
- What would verify it: Report the estimated sign, magnitude, uncertainty and same-sample baseline/extension comparison with traceable units and coding.
- What would weaken it: Source transitions, zero-coding assumptions or poor light-proxy representation dominate interpretation. Increased joint model fit does not demonstrate a stronger separate road contribution.
- Required feasibility check: Review actual source years, road-source comparability and conditional-variable definitions. Describe coefficient attenuation as specification sensitivity, without assigning a mechanism.

#### Supporting Point 2: Spatial heterogeneity in the estimated relationship

- Role relative to the central question: Describe how the association differs across spatial scales.
- Research question: How do the direction and magnitude of the conditional road-activity association vary across Regions, Prefectures and local neighborhoods?
- Why it matters: A national average may conceal spatially distinct transport-development relationships relevant to differentiated road planning and maintenance discussion.
- Current data support: Nine regional and forty-seven prefectural extended equations have been attempted; forty-five prefectural models are estimable. The extended five-kilometre local model estimates 332,994 of 383,386 focal meshes. Failed fits and locally constant added-control coefficients remain explicitly unestimated.
- Key readable variables: The approved road-activity variables and controls, Region, Prefecture and mesh geography, with local support and omitted-control diagnostics.
- What would verify it: Describe regional, prefectural and local coefficient distributions and geographic patterns on their actual estimable support. Geographic differences in numerical estimates are descriptive evidence; separate significance labels are not formal tests of coefficient differences.
- What would weaken it: Apparent variation depends heavily on low predictor variation, extreme numerical condition, changing local support or source-definition differences. Failed areas remain part of coverage reporting.
- Required feasibility check: Confirm the active extended coefficient surface, spatial support and interpretation of locally constant controls. Baseline and extended surfaces must retain their distinct model identities. No local significance procedure or new bandwidth search is selected by this question plan.

#### Supporting Point 3: Geography and context of potential mismatch

- Role relative to the central question: Describe road supply relative to local economic-activity levels, complementing coefficient heterogeneity.
- Research question: Within the existing comparable-context groups, where do high-road-density and low-radiance meshes occur, and how are these potential mismatch patterns distributed across geographic and land-cover contexts?
- Why it matters: The level of infrastructure relative to activity and the local regression slope are different empirical properties. A negative slope is not the definition of a high-road/low-activity mesh.
- Current data support: The latest-period screen retains 383,386 meshes, supports comparisons for 374,865 and identifies 66,088 relative candidates under the existing rule. About 96.85 percent of candidates have zero radiance and 79.74 percent have dominant forest cover. A bounded source audit verifies the numerical provenance of sampled zeros.
- Key readable variables: Road Length Density, Nighttime Radiance, Population, Region, dominant land context, the approved facility/rail context and the existing peer-support/candidate flags.
- What would verify it: Describe candidate locations, fractions and contextual composition using the existing supported denominator and retaining unsupported meshes with their reasons.
- What would weaken it: Extensive light ties, poor activity differentiation or essential forestry, access and network functions make the pattern less informative as potential transport mismatch. Source-zero light does not establish absent economic activity.
- Required feasibility check: Review peer-group support, light ties and context-specific measurement meaning. Keep Urban, Forest, agricultural, Water, Other and incomplete-coverage cases visible. No new screen threshold or confirmed excess-road classification is selected.

#### Supporting Point 4: Municipal traffic and maintenance-fiscal associations

- Role relative to the central question: Add transportation and public-finance context to the spatial mismatch pattern.
- Research question: Across municipalities, how is the fraction of potentially mismatched meshes associated with surveyed traffic utilization, realized road-and-bridge maintenance expenditure shares and fiscal-resource measures, and how do these associations differ when candidate fractions are defined within different land contexts?
- Why it matters: This connects the geographic relationship to the user's transportation maintenance concern while retaining an associational objective.
- Current data support: The linked cross-section covers 1,741 individual municipal financial governments, with usable published traffic in 1,734. Existing unadjusted rank correlations are approximately -0.591 for traffic, +0.266 for maintenance/expenditure and -0.483 for standard fiscal revenue/need. Forest and agricultural candidate fractions show the same directional pattern, whereas Urban-context associations are near zero or have opposite signs.
- Key readable variables: Candidate Fraction of Supported Meshes, Length Weighted 24h Volume, Maintenance Share of Expenditure, Maintenance Share of Standard Fiscal Scale and Single Year Fiscal Revenue Need Ratio. These are existing exploratory references, not newly selected radiance-regression controls.
- What would verify it: Report observed directions, magnitudes, available-pair counts and context contrasts, including null and differing patterns. Context-specific candidate fractions are compared with whole-municipality outcomes; they do not directly measure traffic or spending within each land class.
- What would weaken it: The association is absent, reverses across contexts or is dominated by survey coverage, municipality size/composition, source-year differences or fiscal institutions. Municipal correlations do not establish a relationship for every road or mesh.
- Required feasibility check: Confirm boundary/code linkage, units, actual years, missingness and the distinction between territorial roads and government-financed roads. Road/light use 2024, population 2020, traffic 2021 and finance actual FY2023. Preserve unavailable traffic and jurisdiction links rather than coding them as zero. No causal fiscal model is required.

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

The empirical focus is the spatial alignment of persistent road provision with economic activity, and the observed transport-utilization and maintenance-fiscal context of potential mismatch. The available national and spatial estimates motivate this question, but do not by themselves establish literature novelty. Any final claim about what prior transportation research has overlooked requires a separate literature assessment.

### Conceptual Framework

Road-network provision is an infrastructure stock, while economic activity is represented by nighttime radiance. Population, annual land cover and selected facilities describe observed context. The national relationship provides a reference; regional, prefectural and local equations describe geographic variation; the comparable-context screen describes relative levels of road supply and activity; municipality summaries describe associated traffic and fiscal characteristics.

Potential overprovision and continuing maintenance pressure provide the policy motivation. The empirical claims concern relationships and spatial heterogeneity. Realized maintenance spending is an observed fiscal allocation, not a direct measurement of required maintenance obligations or excess-road costs. Through traffic, essential access, forestry and public-service functions remain relevant when interpreting low local light.

Regression coefficient heterogeneity and high-road/low-radiance screening remain distinct evidence. The former describes a local conditional slope; the latter describes a relative mesh-level combination. Municipal aggregation adds another scale and can reveal relationships different from those visible in individual meshes. No universal sign or uniform urban-rural pattern is presupposed.

### Problem Formulation

Use the approved five-period pooled road-activity equations, with the baseline and focused extension retained separately, to describe national and spatial associations. Actual input years, static-facility assumptions, local support, omitted constant controls and failed estimates remain explicit. The existing latest-period screen and municipal references form a complementary linked cross-section; traffic and finance are not repeated as five historical observations.

The intended evidence sequence is national association, spatial heterogeneity, relative mismatch geography, and municipal traffic/fiscal associations. No temporal-change model, new control, interaction, screen threshold, formal significance procedure or causal estimand is selected by this proposal. Mixed and near-zero results are part of the account, especially the observed contrast between Urban and forest/agricultural contexts. Confirmed road overprovision remains a separate normative interpretation that the current descriptive metrics do not directly measure.
