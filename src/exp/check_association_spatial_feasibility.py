"""Read-only focused feasibility audit of the five proposed associational questions.

Complements the bundled text-only helper with existing local Parquet libraries.
Writes exploratory inventories and judgments; does not estimate or change data.
"""
from pathlib import Path
from collections import Counter
import csv, hashlib, importlib.util, json, zipfile
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/feasibility-check/association-spatial-heterogeneity'
PLAN = ROOT / 'docs/AnaSOP.research-question-planning.md'
ANA = ROOT / 'docs/AnaSOP.md'
PATHS = {
 'panel': 'data/processed/national/land_cover_poi_extension/focused_extension_panel_preprocessed.parquet',
 'screen': 'data/exp/road-economy-mismatch-light-zero-audit/revised_mesh_screen_2024.parquet',
 'local': 'data/exp/land-cover-poi-extension/gwpr-local-constant-controls-5km/local_coefficients.parquet',
 'municipal': 'data/exp/municipality-mismatch-trial/municipal_evidence_2024.parquet',
 'geography': 'data/processed/national/municipality_mismatch_trial/mesh_municipality_reference_preprocessed.parquet',
 'traffic': 'data/processed/national/municipality_mismatch_trial/municipal_traffic_reference_preprocessed.parquet',
 'fiscal': 'data/processed/national/municipality_mismatch_trial/municipal_fiscal_reference_preprocessed.parquet',
 'crosswalk': 'data/processed/national/municipality_mismatch_trial/municipal_code_crosswalk_preprocessed.parquet',
}

def sha(p):
 return hashlib.sha256(p.read_bytes()).hexdigest()

def write_csv(name, rows):
 with (OUT/name).open('w', newline='', encoding='utf-8') as f:
  fields=list(dict.fromkeys(k for row in rows for k in row))
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 owned={p:sha(p) for p in [PLAN,ANA]}
 spec=importlib.util.spec_from_file_location('feasibility_helper',ROOT/'.codex/skills/feasibility-check/scripts/check_feasibility.py')
 helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 questions=helper.extract_research_questions(PLAN.read_text());assert len(questions)==5
 current_questions=helper.extract_research_questions(ANA.read_text());assert len(current_questions)==4
 datasets=[];variables=[];stamps={}
 for name,rel in PATHS.items():
  p=ROOT/rel;stat=p.stat();stamps[p]=(stat.st_size,stat.st_mtime_ns)
  pf=pq.ParquetFile(p)
  datasets.append({'dataset':name,'source_file':rel,'format':'parquet','readable':True,'rows':pf.metadata.num_rows,'columns':len(pf.schema_arrow),'inspection':'Actual Parquet schema and metadata; selected contents independently checked'})
  for field in pf.schema_arrow:
   variables.append({'dataset':name,'source_file':rel,'variable':field.name,'dtype':str(field.type)})
 # Source presence and archive member inventory, without unpacking or modifying raw files.
 raw_roots=[ROOT/'data/raw/roads',ROOT/'data/raw/population',ROOT/'data/raw/lights',ROOT/'data/raw/land-cover',ROOT/'data/raw/nighttime-lights']
 raw_archives=sorted({p for base in raw_roots if base.exists() for p in base.rglob('*.zip')})
 raw_classes={}
 for p in raw_archives:
  key=str(p.relative_to(ROOT/'data/raw')).split('/')[0]
  raw_classes.setdefault(key,[]).append(p)
 for key,paths in raw_classes.items():
  p=paths[0]
  with zipfile.ZipFile(p) as z: members=len(z.infolist())
  datasets.append({'dataset':'raw source: '+key,'source_file':str(p.relative_to(ROOT)),'format':'zip','readable':True,'rows':'','columns':'','inspection':f'{len(paths)} archives present in this class; one representative central directory read ({members} members). Not a nationwide archive integrity re-audit.'})
 # Independently check selected full-panel values in bounded batches.
 pf=pq.ParquetFile(ROOT/PATHS['panel'])
 numeric=['Nighttime Radiance','Road Length Density','Population','Urban Land Cover Share','Forest Land Cover Share','Cropland Land Cover Share','Cropland Mosaic Land Cover Share','Water Land Cover Share','Distance to Railway Station','Distance to Passenger Airport','School Facility Count','Medical Facility Count','Logistics Facility Count','Visitor and Event Facility Count']
 counts=Counter();periods=set();meshes=set();missing=Counter();zero_population=0
 for batch in pf.iter_batches(batch_size=65536,columns=['Mesh Code','Road Year','Population Year','Nighttime Light Year']+numeric):
  d=batch.to_pandas();meshes.update(d['Mesh Code']);missing.update(d[numeric].isna().sum().to_dict());zero_population+=int(d['Population'].eq(0).sum())
  counts.update(d['Road Year'].value_counts().to_dict());periods.update(d[['Road Year','Population Year','Nighttime Light Year']].drop_duplicates().itertuples(index=False,name=None))
 assert len(meshes)==383386 and set(counts)=={2002,2003,2004,2010,2024} and set(counts.values())=={383386}
 assert sum(missing.values())==0 and zero_population==1048757
 s=pd.read_parquet(ROOT/PATHS['screen'],columns=['Mesh Code','Supported Comparison','Potential Mismatch Candidate','Nighttime Radiance','Land Context','Peer All Zero Radiance'])
 local=pd.read_parquet(ROOT/PATHS['local'],columns=['Mesh Code','Road Density Coefficient','Fit Status','Failure Reason','Below 30 Observations'])
 muni=pd.read_parquet(ROOT/PATHS['municipal'])
 geo=pd.read_parquet(ROOT/PATHS['geography'],columns=['Mesh Code','Government Code','Cross Municipality Mesh'])
 traffic=pq.ParquetFile(ROOT/PATHS['traffic']);fiscal=pq.ParquetFile(ROOT/PATHS['fiscal'])
 for d in [s,local,geo]:assert len(d)==383386 and d['Mesh Code'].is_unique and set(d['Mesh Code'])==meshes
 c=s['Potential Mismatch Candidate'].eq(True).fillna(False)
 assert int(s['Supported Comparison'].sum())==374865 and int(c.sum())==66088
 assert int(local['Road Density Coefficient'].notna().sum())==332994
 assert len(muni)==1741 and muni['Government Code'].is_unique and int(muni['Length Weighted 24h Volume'].notna().sum())==1734
 finance=['Maintenance Share of Expenditure','Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio']
 assert muni[finance].notna().all().all()
 assert int(geo['Government Code'].isna().sum())==320 and int(geo['Cross Municipality Mesh'].sum())==58268
 assert traffic.metadata.num_rows==99417 and fiscal.metadata.num_rows==1741
 audit=json.loads((ROOT/'data/exp/road-economy-mismatch-light-zero-audit/delivery_validation.json').read_text())
 assert audit['status']=='passed' and audit['source_meshes_independently_reaggregated']==420
 pooled=json.loads((ROOT/'data/exp/land-cover-poi-extension/pooled_validation.json').read_text())
 assert pooled['status']=='passed' and pooled['estimable_model_counts']=={'national':1,'regional':9,'prefecture':45}
 # Existing diagnostics are evidence reviewed, not newly rerun estimation.
 gwpr=json.loads((ROOT/'data/exp/land-cover-poi-extension/gwpr-local-constant-controls-5km/local_fit_validation.json').read_text())
 assert gwpr['status']=='passed' and gwpr['bandwidth_km']==5
 summaries=[
 ('Central','Testable as an associational evidence chain','Core variables, spatial estimates, screen and municipal context available','No normative road-excess benchmark; no temporal growth claim; literature novelty not checked'),
 ('RQ1','Testable for source-defined pooled association','Complete selected numeric fields; 383386 meshes x five periods; validated national estimates','Historical supplied and 2024 centerline road measures are not proven equivalent; population offsets and static POI assumptions disclosed'),
 ('RQ2','Testable on estimable geographic support','Nine Regions, 45/47 extended Prefectures; 332994/383386 local road coefficients','Tokyo/Nara complete extended vectors fail; 50392 local fits unavailable; extreme/local support diagnostics; no local significance or formal coefficient-difference test'),
 ('RQ3','Testable as relative mismatch description','374865 supported meshes; 66088 relative candidates; bounded zero-source audit','64006 candidate lights are zero; 52696 forest candidates; zero light is not zero economy; inclusive light ties limit ranking; no confirmed excess label'),
 ('RQ4','Testable for territorial cross-sectional associations','1741 municipal fiscal references; 1734 usable traffic outcomes; land-context comparisons available','Road/light 2024, population 2020, traffic 2021, finance FY2023; territory differs from ownership; context fractions use whole-government outcomes; 320 mesh links and seven traffic outcomes unavailable'),
 ]
 rows=[]
 for q,(qid,assessment,evidence,boundaries) in zip(questions,summaries):
  rows.append({'id':qid,'question':q['question'],'status':'partly-testable','focused_assessment':assessment,'evidence':evidence,'interpretation_boundaries':boundaries,'next_step':'Retain the proposed associational scope; carry reviewed definitions and flags into data-preprocessing/output-contract review','new_data_required_for_stated_question':'No mandatory new acquisition identified; stronger normative or temporal claims require additional evidence'})
 assert int((c&s['Nighttime Radiance'].eq(0)).sum())==64006 and int((c&s['Land Context'].eq('Forest')).sum())==52696
 write_csv('dataset_availability.csv',datasets);write_csv('variable_inventory.csv',variables);write_csv('question_feasibility.csv',rows)
 validation={'status':'passed','question_source':str(PLAN.relative_to(ROOT)),'question_source_status':'Five-question proposal checked; not promoted by this read-only skill','active_AnaSOP_questions':len(current_questions),'proposal_questions':5,'parquet_datasets_read':len(PATHS),'raw_archives_present_in_selected_roots':len(raw_archives),'raw_representative_classes_checked':list(raw_classes),'column_entries':len(variables),'distinct_readable_field_names':len({v['variable'] for v in variables}),'status_counts':{'partly-testable':5},'panel_meshes':len(meshes),'panel_rows':sum(counts.values()),'source_year_triplets':sorted(periods),'selected_numeric_missing':dict(missing),'zero_population_records':zero_population,'screen_supported':int(s['Supported Comparison'].sum()),'screen_candidates':int(c.sum()),'local_estimable':int(local['Road Density Coefficient'].notna().sum()),'local_failures':local['Failure Reason'].value_counts().to_dict(),'municipal_rows':len(muni),'municipal_traffic_available':1734,'unlinked_meshes':320,'bundle_text_only_false_negative':'Zero recognized input text tables; archive and Parquet invisibility, not absent research data','statistical_models_rerun':False,'new_variables_selected':False,'reference_validation_status':'Existing passed reports reviewed; this run independently checks selected contents and coverage only'}
 for p,(size,mtime) in stamps.items():assert (p.stat().st_size,p.stat().st_mtime_ns)==(size,mtime)
 for p,h in owned.items():assert sha(p)==h
 validation['source_file_metadata_and_planning_hashes_unchanged']=True
 (OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
 report='''# Association and spatial heterogeneity feasibility check

The five-question proposal is evaluated alongside the active four-question AnaSOP. The proposal has not been promoted by this read-only skill. No raw data, processed data, questions, estimators or figures are changed.

The bundled term-screen script recognizes no CSV/TSV/TXT data under raw/processed and reports five not-yet-testable questions. This is a format-limited false negative: the inputs are Parquet tables and archived geospatial/raster sources. The focused audit reads actual Parquet schemas and selected complete contents, plus representative raw archive directories. Column entries count fields across tables, not independent analytical predictors. No missing package or installation is required.

## Question-level assessment

| Question | Feasibility | Main boundary |
| --- | --- | --- |
'''
 for r in rows:report+=f"| {r['id']} | {r['focused_assessment']} | {r['interpretation_boundaries']} |\n"
 report+='''
## Implication for the planned study

All five questions are partly-testable in the skill vocabulary and testable within their stated descriptive/associational scope. Availability does not predetermine the direction of results. Mixed and near-zero Urban-context findings remain part of the evidence. No causal identification is required by the human-confirmed research target.

The main pooled coefficients describe the assembled, source-defined measurements rather than a proven invariant historical road-density series. Numerical completeness is partly a consequence of the accepted source-unlisted/unknown road-density zero coding; it does not verify physical road absence. The five-period common cohort is a covered national analytical sample rather than every land mesh. Local failures remain unavailable; do not describe all Japan as locally estimable or paint absent coefficients as zero. The expanded five-kilometre surface is the active controlled local result, distinct from the baseline three-kilometre map.

Screening describes a relative high-road/low-radiance pattern. Sampled source-zero radiance is genuine in the supplied product, but does not establish zero economic activity. Forest/urban/agricultural context differences matter. Fiscal spending is observed expenditure, not required maintenance costs; surveyed roads are not an ownership-matched municipal inventory. Actual source years and institutional differences remain disclosed.

## Next workflow step

The skill route is data-preprocessing for confirmation of readable definitions and analytical-input provenance, reusing existing approved inputs rather than automatically rebuilding them. No new acquisition, recoding, imputation or control is selected. The next durable planning task is to review the proposed questions and reconcile formal output coverage through the responsible planning skills; the active formal plan still contains three baseline administrative regression tables. This feasibility audit does not add formal maps or fiscal tables.

## Reproduction

Run the bundled check_feasibility.py with --anasop docs/AnaSOP.research-question-planning.md and the experiment term-screen output directory. Then run python3 src/exp/check_association_spatial_feasibility.py. Local pandas and pyarrow are already installed. Detailed coverage, field inventory and assertions are saved in the adjacent CSV and validation JSON files. Raw archive central-directory checks are bounded source-presence checks, not a full nationwide integrity re-audit. Existing estimation and geometry validation reports are reviewed as dated evidence, not represented as newly rerun models.
'''
 (OUT/'README.md').write_text(report)
 print(json.dumps({k:validation[k] for k in ['status','proposal_questions','parquet_datasets_read','column_entries','distinct_readable_field_names','status_counts','panel_meshes','panel_rows','local_estimable','municipal_rows','municipal_traffic_available']},indent=2))

if __name__=='__main__':main()
