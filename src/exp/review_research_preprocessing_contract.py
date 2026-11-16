"""Inventory existing research inputs and prepare a reviewable preprocessing proposal.

Uses the bundled variable-discovery functions on the eight explicitly reviewed tables.
Full-column missingness is checked in bounded Parquet batches. No data are transformed,
no pending variable choice is marked confirmed, and AnaSOP is not overwritten.
"""
from pathlib import Path
from collections import Counter
import hashlib, importlib.util, json
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/association-spatial-heterogeneity'

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 feasibility=module('focused_feasibility','src/exp/check_association_spatial_feasibility.py')
 discovery=module('discovery','.codex/skills/data-preprocessing/scripts/prepare_variable_list.py')
 generator=module('generator','.codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py')
 # An explicit source list prevents rediscovery of unrelated historical experiments.
 # The local coefficient table is inventoried as a result reference, not a new input.
 discovery.discover_data_files=lambda root:[ROOT/p for p in feasibility.PATHS.values()]
 discovery.OUTPUT_DIR=str((OUT/'sample-discovery').relative_to(ROOT))
 import sys
 saved=sys.argv;sys.argv=['prepare_variable_list.py','--root',str(ROOT),'--pretty']
 try:discovery.main()
 finally:sys.argv=saved
 approved=json.loads((ROOT/'data/exp/land-cover-poi-extension/execution_contract.json').read_text())
 core=set([approved['outcome']]+approved['explanatory']+[approved['land_cover_reference']])
 proposed_screen={'Potential Mismatch Candidate','Land Context'}
 proposed_municipal={'Candidate Fraction of Supported Meshes','Length Weighted 24h Volume','Maintenance Share of Expenditure','Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio'}
 finance_ref={'Road Maintenance Thousand Yen','Bridge Maintenance Thousand Yen','Total Expenditure Thousand Yen','Standard Fiscal Scale Thousand Yen','Standard Fiscal Revenue Thousand Yen','Standard Fiscal Need Thousand Yen'}
 rows=[];groups={};stats=[];stamps={};contract={'confirmed':False,'scope':'Existing approved variables plus seven proposed descriptive-analysis variables; review required','datasets':{}}
 definitions={
  'Potential Mismatch Candidate':('descriptive mismatch indicator','True for supported meshes with positive Road Length Density above the peer upper quartile and Nighttime Radiance at or below the peer lower quartile; unavailable screening remains missing.'),
  'Land Context':('descriptive context','Existing dominant annual land-cover classification used by the screening peer groups; retain Other, Water and incomplete-coverage cases.'),
  'Candidate Fraction of Supported Meshes':('descriptive mismatch measure','Candidate meshes divided by supported comparison meshes in the assigned government or land context; preserve denominator counts.'),
  'Length Weighted 24h Volume':('descriptive utilization measure','Published daily vehicle volumes averaged with positive source-segment-length weights; unavailable traffic remains missing.'),
  'Maintenance Share of Expenditure':('descriptive fiscal measure','The same government Road and Bridge maintenance spending divided by total expenditure; preserve actual fiscal year and amounts.'),
  'Maintenance Share of Standard Fiscal Scale':('descriptive fiscal measure','The same government Road and Bridge maintenance spending divided by standard fiscal scale.'),
  'Single Year Fiscal Revenue Need Ratio':('descriptive fiscal-resource measure','Single-year standard fiscal revenue divided by standard fiscal need; distinct from the encoded three-year strength index.'),
 }
 for label,rel in feasibility.PATHS.items():
  source=ROOT/rel;st=source.stat();stamps[source]=(st.st_size,st.st_mtime_ns)
  pf=pq.ParquetFile(source);null=Counter();samples={c:[] for c in pf.schema_arrow.names};dtypes={}
  for batch in pf.iter_batches(batch_size=65536):
   df=batch.to_pandas()
   for col in df:
    s=df[col];null[col]+=int(s.isna().sum());dtypes[col]=str(s.dtype)
    if len(samples[col])<3:
     values=s.dropna().drop_duplicates().head(3-len(samples[col])).tolist()
     for x in values:
      val=str(x)
      if val not in samples[col]:samples[col].append(val)
  nr=pf.metadata.num_rows;dsrows=[];selected=[]
  for col in pf.schema_arrow.names:
   if label=='panel' and col in core:
    state='Previously confirmed';final='yes';role='outcome' if col==approved['outcome'] else ('retained land-cover reference' if col==approved['land_cover_reference'] else 'explanatory/control')
   elif (label=='screen' and col in proposed_screen) or (label=='municipal' and col in proposed_municipal):
    state='Proposed; awaiting human confirmation';final='pending';role=definitions[col][0]
   else:state='Existing audit/reference field';final='no';role='result reference' if label=='local' else 'identifier/source-year/quality/reference'
   status='partly-testable' if col in core|proposed_screen|proposed_municipal|finance_ref else 'unknown'
   r={'source_dataset':rel,'dataset_role':label,'original_name':col,'dtype':dtypes[col],'non_null_count':nr-null[col],'null_count':null[col],'null_pct':round(null[col]/nr*100,6),'sample_values':'; '.join(samples[col]),'feasibility_status':status,'readable_name':col,'full_name':col,'is_final_variable':final,'confirmation_state':state,'role':role}
   rows.append(r);dsrows.append(r)
   # A final prepared projection retains the complete audit ledger of each source.
   selected.append({'original_name':col,'readable_name':col,'full_name':col,'is_final_variable':'yes' if final in ['yes','pending'] else 'no','role':role,'preprocessing':[],'confirmation_state':state})
  if label in {'panel','screen','municipal'}:
   info={'output':f'data/processed/national/association_spatial_heterogeneity/{label}_preprocessed.parquet','script':f'src/preprocessing/preprocess_association_spatial_{label}.py','variables':selected}
   generator.validate_readable_names(rel,selected)
   contract['datasets'][rel]=info
  groups[rel]=dsrows;stats.append({'dataset':label,'source':rel,'rows':nr,'columns':len(dsrows),'original_field_count_preserved':True})
 pd.DataFrame(rows).to_csv(OUT/'variable_list.csv',index=False)
 pd.DataFrame(stats).to_csv(OUT/'dataset_summary.csv',index=False)
 # The standard helper's full grouped table is followed by scope/decision notes.
 discovery.write_readme(OUT,groups,[])
 note='''\n## Current review scope\n\nEight existing tables and all their fields are inventoried. The GWPR coefficient table is a result reference only. The panel, screen and municipal evidence are proposed source-preserving analytical projections; four existing geography, traffic, fiscal and code-crosswalk references are reused without additional copies. Full-column null percentages above are computed over every source row, not the first 1,000 sample rows used by the bundled helper. Names are existing English-readable names; no renaming is proposed. The focused feasibility labels are mapped explicitly to analytical constructs; unknown labels on quality/identifier fields do not mean missing data.\n\nFifteen previously confirmed panel variables (including Other Land Cover Share as retained reference) are reused. Two mesh-screen variables and five municipal metrics are proposed for formal descriptive analysis, without adding them to the radiance equation. Local coefficients remain outputs, not new regression inputs. Candidate Road Stock Share remains a secondary reference rather than a selected headline measure. All source-year, coverage, support, failed-link and denominator fields remain in the saved projections.\n\nNo additional numerical conversion, filling, deletion, clipping, logarithm, categorical conversion or name normalization is proposed. Accepted road-density zero coding, structural population zeros, true light zeros and unavailable screening/traffic/jurisdiction values retain their existing meanings and flags. Municipal geometry follows the existing largest identified municipal land-overlap convention within the frozen Prefecture; designated-city wards consolidate to the source-verified financial parent. These detailed conventions are proposed for the formal descriptive inputs, pending confirmation.\n\nDecisions are a proposal only (decisions.proposed.json), not confirmed decisions. No processing script or output projection is generated until the seven-variable selection and existing-section update are confirmed. Proposed outputs are in a new processed subfolder, preserving the current model inputs and previous results. The proposed Section 4 addition is written separately for review.\n'''
 with (OUT/'README.md').open('a') as f:f.write(note)
 (OUT/'decisions.proposed.json').write_text(json.dumps(contract,indent=2)+'\n')
 section='''### Descriptive Mismatch, Traffic and Fiscal Variables — Proposed Formal Roles\n\nThe fifteen approved panel variables retain their existing definitions and roles. The following seven variables are proposed for descriptive spatial and administrative analysis, without being added to the radiance equations. Existing readable names, units, source years and coding are reused.\n\n| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |\n| --- | --- | --- | --- | --- | --- |\n'''
 for col,(role,meaning) in definitions.items():section+=f'| {col} | {col} | {role} | {meaning} | Reuse existing source-derived values; no additional transformation or filling. | yes, pending confirmation |\n'
 section+='''\nReference fields preserve mesh and government identifiers, actual source years, supported and candidate counts, source coverage, missing-status flags and source amounts. Candidate Road Stock Share remains a reference measure of roads in flagged mesh footprints, not excessive length or government-owned inventory. All original mesh and government records remain represented.\n\nMunicipal assignment uses largest identified municipal land overlap within the already frozen Prefecture. Administrative wards of designated cities link to the verified financial parent. Unavailable jurisdiction links remain missing; this is an allocation approximation rather than clipped official road ownership. Context-specific candidate fractions are compared with whole-government outcomes. Current source dates remain road/light 2024, population 2020, surveyed traffic 2021 and finance actual FY2023.\n'''
 (OUT/'AnaSOP_section4_proposed.md').write_text(section)
 for p,(size,mtime) in stamps.items():assert (p.stat().st_size,p.stat().st_mtime_ns)==(size,mtime)
 summary={'status':'inventory_complete_pending_variable_selection','tables':len(stats),'column_entries':len(rows),'distinct_readable_names':len({r['original_name'] for r in rows}),'previously_confirmed_panel_variables':len(core),'proposed_new_formal_descriptive_variables':7,'source_files_unchanged':True,'new_processed_files_written':0,'scripts_generated':0,'AnaSOP_updated':False,'all_proposed_readable_names_validated':True,'sample_helper_output':'sample-discovery','full_inventory':'variable_list.csv','datasets':stats}
 (OUT/'review_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k!='datasets'},indent=2))

if __name__=='__main__':main()
