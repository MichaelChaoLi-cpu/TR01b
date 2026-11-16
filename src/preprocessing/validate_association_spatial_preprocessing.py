"""Validate the confirmed, source-preserving three-dataset preprocessing delivery."""
from pathlib import Path
import csv, hashlib, importlib.util, json, re
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/association-spatial-heterogeneity'

def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def sections(s):
 p=re.split(r'(?m)(^## [1-8]\. .+$)',s)
 return {int(p[i][3]):p[i]+p[i+1] for i in range(1,len(p),2)}

def main():
 c=json.loads((OUT/'decisions.json').read_text());assert c['confirmed'] and c['decision_id']=='MILI-D-20261011-004'
 spec=importlib.util.spec_from_file_location('generator',ROOT/'.codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py')
 helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 records=[];formal=[];checked=0
 for src,info in c['datasets'].items():
  source=ROOT/src;dest=ROOT/info['output'];sp,dp=pq.ParquetFile(source),pq.ParquetFile(dest)
  assert sha(source)==c['source_sha256'][src]
  assert sp.metadata.num_rows==dp.metadata.num_rows
  assert sp.schema_arrow.names==dp.schema_arrow.names==[v['readable_name'] for v in info['variables']]
  helper.validate_readable_names(src,info['variables'])
  for v in info['variables']:
   assert not v['preprocessing'] and v['original_name']==v['readable_name']
   a=pd.read_parquet(source,columns=[v['original_name']]).iloc[:,0]
   b=pd.read_parquet(dest,columns=[v['readable_name']]).iloc[:,0]
   pd.testing.assert_series_equal(a,b,check_exact=True);checked+=1
   if v['is_final_variable']=='yes':formal.append(v['readable_name'])
  assert (ROOT/info['script']).is_file()
  records.append({'source':src,'output':info['output'],'script':info['script'],'rows':dp.metadata.num_rows,'columns':len(dp.schema_arrow),'exact_fields_checked':len(info['variables']),'source_sha256':sha(source),'output_sha256':sha(dest)})
 assert len(formal)==len(set(formal))==22 and checked==148
 screen=pd.read_parquet(ROOT/'data/processed/national/association_spatial_heterogeneity/screen_preprocessed.parquet',columns=['Potential Mismatch Candidate','Supported Comparison'])
 assert int(screen['Potential Mismatch Candidate'].isna().sum())==8521 and int(screen['Supported Comparison'].sum())==374865
 assert int(screen['Potential Mismatch Candidate'].eq(True).sum())==66088
 muni=pd.read_parquet(ROOT/'data/processed/national/association_spatial_heterogeneity/municipal_preprocessed.parquet')
 assert len(muni)==1741 and muni['Government Code'].is_unique
 assert int(muni['Length Weighted 24h Volume'].isna().sum())==7
 assert muni[['Maintenance Share of Expenditure','Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio']].notna().all().all()
 before=(OUT/'AnaSOP_before_execution.md').read_text();after=(ROOT/'docs/AnaSOP.md').read_text();a,b=sections(before),sections(after)
 for k in [1,2,3,5,6,7,8]:assert a[k]==b[k],k
 assert b[4].startswith(a[4].rstrip()) and a[4]!=b[4]
 confirmed=(OUT/'AnaSOP_section4_confirmed.md').read_text();assert confirmed in b[4]
 for name in formal:assert f'| {name} |' in confirmed
 assert confirmed.count('| yes |')==22 and 'pending confirmation' not in confirmed
 assert not any(x in confirmed for x in ['source_dataset','original_name','data/raw/','data/processed/','src/'])
 assert not re.search(r'[\u4e00-\u9fff]',after)
 assert after.count('\\[')==after.count('\\]') and after.count('\\(')==after.count('\\)')
 for eq in re.findall(r'\\\[(.*?)\\\]',after,re.S):assert eq.isascii()
 assert 'MILI-D-20261011-004' in (ROOT/'docs/framelog/mili.md').read_text()
 with (OUT/'output_manifest.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 report={'status':'passed','decision_id':c['decision_id'],'datasets_written':3,'field_entries_selected':148,'distinct_formal_substantive_variables':22,'fields_verified_exactly':checked,'names_dtypes_values_order_and_missingness_preserved':True,'source_hashes_unchanged':True,'screen_missing_retained':8521,'municipal_traffic_missing_retained':7,'ana_sections_changed':[4],'all_other_ana_sections_preserved':True,'previous_section4_history_preserved':True,'readable_names_and_English_checked':True,'ASCII_display_math_checked':True,'new_estimations_run':False,'datasets':records}
 (OUT/'delivery_validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='datasets'},indent=2))

if __name__=='__main__':main()
