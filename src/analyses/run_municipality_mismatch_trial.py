"""Municipal mismatch/utilization/fiscal descriptive evidence trial.

No regressions or causal claims. Full mesh ledger retained, missing links explicit,
rank comparisons use available pairs and report their distinct sample counts.
"""
from pathlib import Path
import os,json,hashlib
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/exp/municipality-mismatch-trial';SRC=OUT/'source_snapshots'
PROCESSED=ROOT/'data/processed/national/municipality_mismatch_trial'
SCREEN=ROOT/'data/exp/road-economy-mismatch-light-zero-audit/revised_mesh_screen_2024.parquet'

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def summarize_mesh(z):
 c=z['Potential Mismatch Candidate'].fillna(False);s=z['Supported Comparison']
 return {'Cohort Meshes':len(z),'Supported Meshes':int(s.sum()),'Candidate Meshes':int(c.sum()),
  'Candidate Fraction of Supported Meshes':float(c.sum()/s.sum()) if s.any() else np.nan,
  'Cohort Road Length':float(z['Road Length'].sum()),'Candidate Road Length':float(z.loc[c,'Road Length'].sum()),
  'Candidate Road Stock Share':float(z.loc[c,'Road Length'].sum()/z['Road Length'].sum()) if z['Road Length'].sum()>0 else np.nan,
  'Cohort Population':float(z['Population'].sum()),'Mean Radiance':float(z['Nighttime Radiance'].mean()),
  'Candidate Zero Radiance Fraction':float(z.loc[c,'Nighttime Radiance'].eq(0).mean()) if c.any() else np.nan,
  'Forest Mesh Fraction':float(z['Land Context'].eq('Forest').mean()),'Urban Mesh Fraction':float(z['Land Context'].eq('Urban').mean()),
  'Cross Municipality Meshes':int(z['Cross Municipality Mesh'].sum())}

def summarize_traffic(z):
 valid=z['Published 24h Volume'].notna()&z['Segment Length'].gt(0);length=float(z['Segment Length'].sum());published=float(z.loc[valid,'Segment Length'].sum())
 return {'Survey Segment Rows':len(z),'Surveyed Segment Length':length,'Published Volume Length':published,
  'Published Volume Length Coverage':published/length if length>0 else np.nan,
  'Length Weighted 24h Volume':float(np.average(z.loc[valid,'Published 24h Volume'],weights=z.loc[valid,'Segment Length'])) if published>0 else np.nan,
  'Includes Estimated Direction Length':float(z.loc[valid&z['Volume Status'].eq('Includes estimated direction'),'Segment Length'].sum())}

def corr(z,x,y,scope):
 pairs=z[[x,y]].replace([np.inf,-np.inf],np.nan).dropna();n=len(pairs)
 rho=float(pairs[x].rank(method='average').corr(pairs[y].rank(method='average'))) if n>1 and pairs[x].nunique()>1 and pairs[y].nunique()>1 else np.nan
 return {'Scope':scope,'Predictor':x,'Outcome':y,'Municipalities':n,'Spearman':rho,'Inference':'Descriptive, unadjusted; no significance or causal claim'}

def main():
 d=pd.read_parquet(SCREEN);original_hash=sha(SCREEN)
 geo=pd.read_parquet(PROCESSED/'mesh_municipality_reference_preprocessed.parquet')
 # Existing approved prefecture labels must agree exactly; geometry does not edit them.
 joined=d.merge(geo.drop(columns='Prefecture Code'),on='Mesh Code',how='left',validate='one_to_one')
 assert len(joined)==len(d) and joined['Mesh Code'].is_unique
 for col in d:pd.testing.assert_series_equal(joined[col],d[col])
 joined.to_parquet(OUT/'municipal_mesh_ledger_2024.parquet',index=False)
 fiscal=pd.read_parquet(PROCESSED/'municipal_fiscal_reference_preprocessed.parquet')
 rows=[]
 for code,z in joined.dropna(subset=['Government Code']).groupby('Government Code'):
  rows.append({'Government Code':code,**summarize_mesh(z)})
 meshes=pd.DataFrame(rows);assert len(meshes)==1741
 t=pd.read_parquet(PROCESSED/'municipal_traffic_reference_preprocessed.parquet')
 totals=pd.DataFrame([{'Government Code':code,**summarize_traffic(z)} for code,z in t.groupby('Government Code')])
 types=pd.DataFrame([{'Government Code':k[0],'Road Manager':k[1],'Road Type':k[2],**summarize_traffic(z)} for k,z in t.groupby(['Government Code','Road Manager','Road Type'])])
 types.to_csv(OUT/'municipal_traffic_manager_type_summary.csv',index=False)
 designated=pd.DataFrame([{'Government Code':code,**summarize_traffic(z)} for code,z in t[t['Road Manager'].eq(3)].groupby('Government Code')])
 designated=designated.rename(columns={c:'Designated Managed '+c for c in designated if c!='Government Code'})
 a=fiscal.merge(meshes,on='Government Code',how='left',validate='one_to_one').merge(totals,on='Government Code',how='left',validate='one_to_one').merge(designated,on='Government Code',how='left',validate='one_to_one')
 assert len(a)==1741 and a['Government Code'].is_unique
 a['Road Year']=2024;a['Nighttime Light Year']=2024;a['Population Year']=2020;a['Traffic Year']=2021
 a.to_parquet(OUT/'municipal_evidence_2024.parquet',index=False);a.to_csv(OUT/'municipal_evidence_2024.csv',index=False)
 strata=[]
 for (code,context),z in joined.dropna(subset=['Government Code']).groupby(['Government Code','Land Context']):
  strata.append({'Government Code':code,'Land Context':context,**summarize_mesh(z)})
 strata=pd.DataFrame(strata).merge(fiscal[['Government Code','Government Name','Prefecture','Government Type']],on='Government Code',validate='many_to_one')
 strata.to_csv(OUT/'municipal_land_context_summary.csv',index=False)
 x='Candidate Fraction of Supported Meshes';outcomes=['Length Weighted 24h Volume','Maintenance Share of Expenditure','Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio']
 correlations=[corr(a,x,y,'All municipal governments') for y in outcomes]
 for context,z in strata.groupby('Land Context'):
  contextual=z.merge(a[['Government Code']+outcomes],on='Government Code',validate='one_to_one')
  correlations.extend(corr(contextual,x,y,'Land context: '+context) for y in outcomes)
 # The managed-road label identifies a class in the territory; it is not owner-ID proof.
 dcity=a[a['Government Type'].eq('1')]
 correlations.append(corr(dcity,x,'Designated Managed Length Weighted 24h Volume','Designated cities; designated-managed surveyed roads in territory'))
 cor=pd.DataFrame(correlations);cor.to_csv(OUT/'municipal_context_rank_correlations.csv',index=False)
 statscols=[x,'Candidate Road Stock Share','Length Weighted 24h Volume','Maintenance Share of Expenditure','Single Year Fiscal Revenue Need Ratio']
 a[statscols].describe().to_csv(OUT/'municipal_summary_statistics.csv')
 chart_y=[outcomes[0],outcomes[1],outcomes[3]];labels=['Surveyed traffic (vehicles / 24h)','Road + bridge maintenance / expenditure (%)','Standard fiscal revenue / need']
 fig,axs=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
 for ax,y,label in zip(axs,chart_y,labels):
  pairs=a[[x,y]].dropna();values=pairs[y]*100 if y==outcomes[1] else pairs[y]
  ax.scatter(pairs[x]*100,values,s=9,alpha=.3,color='#397b92',rasterized=True)
  if y==outcomes[0]:ax.set_yscale('log')
  r=cor[(cor.Scope=='All municipal governments')&cor.Outcome.eq(y)].iloc[0]
  ax.set_title(f'n={int(r.Municipalities):,}; Spearman={r.Spearman:.3f}',fontsize=11);ax.set_xlabel('Candidate fraction of supported meshes (%)');ax.set_ylabel(label);ax.grid(alpha=.15)
 fig.suptitle('Municipal territorial associations: exploratory, unadjusted',fontsize=14)
 fig.savefig(OUT/'municipal_evidence_scatter.png',dpi=170);plt.close(fig)
 unlinked=joined[joined['Government Code'].isna()];c=joined['Potential Mismatch Candidate'].fillna(False)
 inventory=[]
 for meta in sorted(SRC.glob('*.metadata.json')):
  m=json.loads(meta.read_text());stem=meta.name.removesuffix('.metadata.json');files=[p for p in SRC.glob(stem+'.*') if p!=meta];assert len(files)==1;p=files[0];assert sha(p)==m['sha256']
  inventory.append({'File':str(p.relative_to(ROOT)),**m,'Role':'Unused intermunicipal membership table' if stem=='municipality_overview' else 'Official source reference'})
 pd.DataFrame(inventory).to_csv(OUT/'source_inventory.csv',index=False)
 report={'status':'completed_exploratory_boundary_limited','municipal_governments':len(a),'mesh_ledger_rows':len(joined),
  'financially_linked_meshes':int(joined['Government Code'].notna().sum()),'unlinked_meshes':len(unlinked),
  'unlinked_candidate_meshes':int(unlinked['Potential Mismatch Candidate'].fillna(False).sum()),'all_candidates':int(c.sum()),
  'linked_candidates':int(a['Candidate Meshes'].sum()),'government_candidate_fraction_missing':int(a[x].isna().sum()),
  'governments_with_published_traffic':int(a['Length Weighted 24h Volume'].notna().sum()),
  'missing_traffic_governments':a.loc[a['Length Weighted 24h Volume'].isna(),['Government Code','Government Name']].to_dict('records'),
  'territories_with_designated_managed_traffic':int(a['Designated Managed Length Weighted 24h Volume'].notna().sum()),
  'designated_road_records_outside_designated_city_governments':int(t[t['Road Manager'].eq(3)&~t['Government Code'].isin(dcity['Government Code'])].shape[0]),
  'national_municipal_correlations':cor[cor.Scope=='All municipal governments'].drop(columns=['Inference']).to_dict('records'),
  'source_snapshots_verified':len(inventory),'screen_sha256':original_hash,'source_screen_unchanged':sha(SCREEN)==original_hash,
  'source_values_and_prior_results_preserved':True,'fixed_effects_added':False,'new_regression_run':False,
  'year_alignment':{'roads_and_lights':2024,'population':2020,'traffic':2021,'fiscal':2023},
  'metric_interpretation':'Candidate mesh fraction and stock in allocated meshes are territorial; not confirmed excess and not municipality-owned inventory',
  'missing_policy':'All source meshes retained; unlinked mesh and unavailable traffic values remain missing; pairwise descriptive comparisons report counts'}
 save(OUT/'trial_validation.json',report)
 headline=cor[cor.Scope=='All municipal governments'][['Outcome','Municipalities','Spearman']].to_string(index=False)
 note=f'''# Municipality mismatch-utilization-fiscal trial\n\nHuman decision: MILI-D-20261011-002. Existing models and source inputs are preserved. This is an exploratory territorial analysis, not a road-overprovision or causal fiscal model.\n\n## Scope and linkage\n\nThere are 1,741 individual financial governments: cities, towns, villages and Tokyo special wards. Designated-city administrative wards are consolidated to the parent city. The original 383,386-mesh latest screen remains in a full ledger. {report['financially_linked_meshes']:,} meshes link to individual government records; {len(unlinked)} do not, including unidentified land intersections or absence of a corresponding fiscal government. They remain in the ledger. Their {report['unlinked_candidate_meshes']} candidates are not attributed to a government or set to zero. Existing Prefecture assignments are unchanged.\n\nMunicipal assignment selects the largest positive identified municipal land-intersection area within the approved Prefecture, in local metric projections, with cross-boundary and unavailable-status flags. Full mesh values and road lengths are attributed to the selected territory; this is a mesh-based approximation, not clipped municipal road length or official municipal population totals. The rule is an agent-specified exploratory implementation convention and is not a newly selected final geography standard. Seven unmatched 2021 Hamamatsu ward codes are verified using the official 2021 N03 archive and linked to the financial parent city. Code-first matching preserves differences in municipal-name spelling. No unsupported nearest-boundary or code-prefix fill is used.\n\n## Dates and fiscal meaning\n\nRoads and lights use 2024; population uses 2020; traffic uses 2021; fiscal sources report actual FY2023 despite the 2024 catalog label. Neither traffic nor finance is repeated across the five-period panel. The three maintenance files split purpose rows and are combined without duplicate rows. Road plus bridge maintenance uses only the maintenance column and those two disjoint child rows. Units are thousand JPY, verified from official templates. Forestry-road and urban-street purpose rows, capital construction and entrusted project columns are excluded from this numerator. Realized spending does not measure maintenance need, deferred work or the cost of excess roads.\n\nFinancial capacity is the single-year standard revenue/need ratio. The encoded three-year strength field is retained only in the source and is not decoded or used. Zero denominators would leave derived ratios missing; the current selected financial fields and derived ratios are complete. Joint administrative organizations and union accounts are excluded from the individual-government analytical scope, with sources retained. Tokyo special wards have a distinct financial arrangement; their values are preserved rather than silently assumed institutionally equivalent to all municipalities.\n\n## Results\n\n{report['linked_candidates']:,} of the original 66,088 candidates are assigned to fiscal governments. {report['governments_with_published_traffic']:,} governments have usable published surveyed traffic; unmatched surveyed traffic remains NaN. Descriptive rank correlations, each with its own pair count:\n\n```\n{headline}\n```\n\nThe primary candidate denominator is supported comparison meshes, excluding unavailable screening status without dropping source rows. Summed candidate Road Length is stock in flagged mesh footprints, not excessive length or government-owned stock. Both whole-territory and separate land-context fractions are saved; land-context comparisons describe urban, cropland, mosaic, forest, water, Other and incomplete coverage separately. They do not control all context differences or establish a mechanism. No significance test, new control, fixed effect or within-municipality regression is introduced.\n\n## Transport and ownership limits\n\nTraffic means are weighted by source basic-segment length within the coded municipality. Original CSV municipality location codes are as of 2021-04-01; this aggregation does not perform nationwide traffic-geometry clipping. Segment lengths and duplicate volume estimates are preserved for distinct basic segments. Road manager and road type are retained in separate summaries. The survey excludes most ordinary municipal roads. {report['territories_with_designated_managed_traffic']} territories contain manager-code-3 surveyed traffic; this code describes designated-city management rather than management by every municipality. There are {report['designated_road_records_outside_designated_city_governments']} manager-code-3 records coded outside a designated-city financial territory; their true responsible city is not identified here. Only the twenty designated cities are used in the additional manager-class descriptive comparison, with no claim that every segment's owner is proven. Most surveyed national/prefectural roads are financed by other governments. Thus territorial traffic and own-government fiscal expenditure do not represent an ownership-matched road-cost relationship.\n\n## Reproduction and outputs\n\nRun `python3 src/preprocessing/construct_municipality_trial_geography.py` (GDAL/GEOS, NumPy; separate from Arrow), `python3 src/preprocessing/prepare_municipality_trial_inputs.py` (pandas, NumPy, pyarrow, openpyxl), and `python3 src/analyses/run_municipality_mismatch_trial.py` (also matplotlib). Inputs and official snapshots are checksum-preserved; source acquisition is handled by `src/exp/acquire_municipality_trial_sources.py`. Independent geometry checks use `src/preprocessing/validate_municipality_trial_geometry.py`. No host-only table API, new dependency installation, Git or DVC operation is required.\n\nCore outputs: municipal_evidence_2024.csv/.parquet; municipal_mesh_ledger_2024.parquet; municipal_land_context_summary.csv; municipal_context_rank_correlations.csv; municipal_traffic_manager_type_summary.csv; municipal_evidence_scatter.png; code and unresolved-link ledgers; numerical validation JSON. Prepared reference files are saved under data/processed/national/municipality_mismatch_trial. The source inventory identifies one unused membership-table snapshot. These exploratory results are not promoted to the formal figure/table plan.\n'''
 note+='''\n## Context contrast and independent checks\n\nForest-context candidate fractions correlate with whole-municipality surveyed traffic at -0.221, maintenance/expenditure at +0.193 and standard fiscal revenue/need at -0.158. Urban-context fractions show +0.042, -0.060 and +0.094 respectively. Cropland and mosaic fractions show the same directional pattern as the forest comparison. These outcomes refer to the entire municipality, not traffic or maintenance measured within each land category. Urban associations are near zero and do not support a uniform pattern across land contexts.\n\nThe input preparation script also refreshes four staged readable reference inputs for the corresponding `preprocess_*_reference_trial.py` skill-generated scripts. Original traffic municipality codes are preserved; zero-padding is applied only to a temporary matching key. Run `python3 src/exp/brief_municipality_mismatch_trial.py` for the focused numerical briefing and distribution figure. Run `python3 src/analyses/validate_municipality_mismatch_trial.py` for independent source-field, fiscal-amount, aggregation, rank-correlation, protected-input hash and AnaSOP section checks; the saved delivery_validation.json records their outcome. Independent geometry checks cover 94 meshes. Their numerical area tolerance allows union-order differences from nonlinear projection (maximum 3.52 square meters); all assigned municipal identities agree.\n'''
 (OUT/'README.md').write_text(note);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
