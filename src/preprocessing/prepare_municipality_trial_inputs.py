"""Prepare source-audited municipal fiscal and geographic references.

No raw/source overwrite, no model controls added. Existing readable fiscal names
and approved maintenance/expenditure ratios are reused in this exploratory trial.
"""
from pathlib import Path
import json,struct,zipfile,hashlib,warnings,shutil
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/municipality-mismatch-trial';SRC=OUT/'source_snapshots'
DEST=ROOT/'data/processed/national/municipality_mismatch_trial'

def attrs(p):
 with zipfile.ZipFile(p) as z:
  enc=z.read(next(n for n in z.namelist() if n.endswith('.cpg'))).decode().strip() if any(n.endswith('.cpg') for n in z.namelist()) else 'cp932'
  b=z.read(next(n for n in z.namelist() if n.endswith('.dbf')))
 n,h,size=struct.unpack_from('<IHH',b,4);fields=[];k=32
 while b[k]!=13:
  d=b[k:k+32];fields.append((d[:11].split(b'\0')[0].decode(),d[16]));k+=32
 result=[]
 for i in range(n):
  rec=b[h+i*size:h+(i+1)*size]
  if rec[:1]==b'*':continue
  r={};k=1
  for name,width in fields:r[name]=rec[k:k+width].decode(enc).strip();k+=width
  result.append(r)
 return pd.DataFrame(result).drop_duplicates()

def valid_government(d):
 return d['決算年度'].eq('2023') & d['団体区分'].isin(['1','2','3','4','5','8','9']) & d['団体コード '].str.strip().str.fullmatch(r'\d{5,6}').fillna(False)

def clean(d):
 d=d[valid_government(d)].copy();d['Government Code']=d['団体コード '].str.strip().str.zfill(6).str[:5];return d

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 c=clean(pd.read_excel(SRC/'municipality_cover.xlsx',dtype=str));assert len(c)==1741 and c['Government Code'].is_unique
 b=clean(pd.read_csv(SRC/'municipality_balance.csv',encoding='cp932',dtype=str));b=b[b['行名称'].eq('令和5年度')];assert len(b)==1741 and b['Government Code'].is_unique
 m=pd.concat([pd.read_csv(SRC/f'municipality_maintenance_{i}.csv',encoding='cp932',dtype=str) for i in range(1,4)],ignore_index=True);m=clean(m)
 assert not m.duplicated(['Government Code','行番号']).any()
 road=m[m['行名称'].eq('道路')].set_index('Government Code');bridge=m[m['行名称'].eq('橋りょう')].set_index('Government Code')
 assert len(road)==len(bridge)==1741
 c=c.set_index('Government Code');b=b.set_index('Government Code');num=lambda d,col:pd.to_numeric(d[col],errors='raise')
 f=pd.DataFrame({'Prefecture':c['県名'],'Government Name':c['団体名'],'Government Type':c['団体区分'],
  'Road Maintenance Thousand Yen':num(road,'001:維持補修費'),'Bridge Maintenance Thousand Yen':num(bridge,'001:維持補修費'),
  'Total Expenditure Thousand Yen':num(b,'002:歳出総額'),'Standard Fiscal Scale Thousand Yen':num(c,'008:標準財政規模（千円）'),
  'Standard Fiscal Revenue Thousand Yen':num(c,'005:基準財政収入額（千円）'),'Standard Fiscal Need Thousand Yen':num(c,'006:基準財政需要額（千円）')}).reset_index()
 f['Prefecture Code']=f['Government Code'].str[:2];f['Fiscal Year']=2023
 f['Road and Bridge Maintenance Thousand Yen']=f['Road Maintenance Thousand Yen']+f['Bridge Maintenance Thousand Yen']
 f['Maintenance Share of Expenditure']=f['Road and Bridge Maintenance Thousand Yen']/f['Total Expenditure Thousand Yen'].where(f['Total Expenditure Thousand Yen']>0)
 f['Maintenance Share of Standard Fiscal Scale']=f['Road and Bridge Maintenance Thousand Yen']/f['Standard Fiscal Scale Thousand Yen'].where(f['Standard Fiscal Scale Thousand Yen']>0)
 f['Single Year Fiscal Revenue Need Ratio']=f['Standard Fiscal Revenue Thousand Yen']/f['Standard Fiscal Need Thousand Yen'].where(f['Standard Fiscal Need Thousand Yen']>0)
 assert f[['Road Maintenance Thousand Yen','Bridge Maintenance Thousand Yen']].ge(0).all().all()
 assert f['Maintenance Share of Expenditure'].between(0,1).all()
 with warnings.catch_warnings():
  warnings.simplefilter('ignore')
  for sheet in ['00','02','20']:
   x=pd.read_excel(SRC/'municipality_template.xlsx',sheet_name=sheet,header=None).astype(str);assert x.apply(lambda s:s.str.contains('千円')).any().any()
 f.to_parquet(DEST/'municipal_fiscal_reference_preprocessed.parquet',index=False);f.to_csv(OUT/'municipal_fiscal_reference.csv',index=False)
 # Code-first linkage retains spelling differences between boundary and finance.
 fiscal_by_code=f.set_index('Government Code');names=f.set_index(['Prefecture Code','Government Name'])
 boundary=pd.read_csv(ROOT/'data/exp/feasibility-check/municipality-analysis/boundary_municipality_attributes.csv',dtype={'Municipality Code':str})
 records=[]
 for _,r in boundary.iterrows():
  code=r['Municipality Code'];pref=code[:2];city=r['Municipality Name'];ward=r['Designated City Ward']
  gc=None;rule=None
  if code in fiscal_by_code.index:gc=code;rule='Exact government code'
  elif pd.notna(ward) and (pref,city) in names.index:
   hit=names.loc[(pref,city)];assert isinstance(hit,pd.Series) and hit['Government Type']=='1';gc=hit['Government Code'];rule='Designated-city ward to source-verified parent city'
  records.append({'Municipality Code':code,'Prefecture Code':pref,'Boundary Municipality Name':city,'Boundary Ward Name':ward,
   'Government Code':gc,'Government Name':fiscal_by_code.loc[gc,'Government Name'] if gc else None,'Linkage Rule':rule or 'No corresponding financial government'})
 cross=pd.DataFrame(records);assert cross['Municipality Code'].is_unique
 # Old seven Hamamatsu wards: authoritative 2021 N03 schema has parent in N03_003.
 old=attrs(SRC/'n03_2021_shizuoka.zip');old=old[old['N03_007'].isin([str(x) for x in range(22131,22138)])]
 assert old['N03_007'].nunique()==7
 for code,z in old.groupby('N03_007'):
  assert z['N03_003'].nunique()==1;city=z['N03_003'].iloc[0];hit=names.loc[('22',city)];assert hit['Government Type']=='1'
  cross.loc[len(cross)]={'Municipality Code':code,'Prefecture Code':'22','Boundary Municipality Name':city,'Boundary Ward Name':';'.join(sorted(z['N03_004'].unique())),
    'Government Code':hit['Government Code'],'Government Name':city,'Linkage Rule':'2021 N03 old Hamamatsu ward to fiscal parent city'}
 cross.to_csv(OUT/'municipal_code_crosswalk.csv',index=False);cross.to_parquet(DEST/'municipal_code_crosswalk_preprocessed.parquet',index=False)
 mesh=pd.read_csv(OUT/'mesh_municipality_assignment.csv',dtype={'Mesh Code':str,'Prefecture Code':str})
 lookup=cross.dropna(subset=['Government Code']).groupby(['Prefecture Code','Boundary Municipality Name']).agg(**{'Government Code':('Government Code',lambda x: x.unique()[0] if x.nunique()==1 else None),'Government Name':('Government Name',lambda x:x.unique()[0] if x.nunique()==1 else None)}).reset_index()
 assert lookup['Government Code'].notna().all()
 mesh=mesh.merge(lookup,left_on=['Prefecture Code','Municipality Name'],right_on=['Prefecture Code','Boundary Municipality Name'],how='left',validate='many_to_one').drop(columns='Boundary Municipality Name')
 mesh.to_parquet(DEST/'mesh_municipality_reference_preprocessed.parquet',index=False)
 unresolved=mesh[mesh['Government Code'].isna()];unresolved.to_csv(OUT/'unresolved_mesh_government_links.csv',index=False)
 t=pd.read_parquet(ROOT/'data/exp/road-economy-mismatch-trial/traffic_segment_reference_2021.parquet')
 # Normalize only a temporary join key; preserve every original traffic field.
 t['Municipality Match Code']=t['Municipality Code'].str.zfill(5)
 match=cross[['Municipality Code','Government Code','Government Name','Linkage Rule']].rename(columns={'Municipality Code':'Municipality Match Code'})
 linked=t.merge(match,on='Municipality Match Code',how='left',validate='many_to_one').drop(columns='Municipality Match Code')
 assert len(linked)==len(t) and linked['Government Code'].notna().all()
 linked.to_parquet(DEST/'municipal_traffic_reference_preprocessed.parquet',index=False)
 # Refresh the readable staged inputs used by the skill-generated scripts.
 stage=ROOT/'data/exp/data-preprocessing/municipality-mismatch-trial';stage.mkdir(parents=True,exist_ok=True)
 for stem in ['municipal_fiscal_reference','municipal_code_crosswalk','mesh_municipality_reference','municipal_traffic_reference']:
  shutil.copyfile(DEST/f'{stem}_preprocessed.parquet',stage/f'{stem}_confirmed_input.parquet')
 mapping=[('団体コード ','Government Code'),('団体名','Government Name'),('001:維持補修費','Road Maintenance Thousand Yen'),('001:維持補修費','Bridge Maintenance Thousand Yen'),('002:歳出総額','Total Expenditure Thousand Yen'),('008:標準財政規模（千円）','Standard Fiscal Scale Thousand Yen'),('005:基準財政収入額（千円）','Standard Fiscal Revenue Thousand Yen'),('006:基準財政需要額（千円）','Standard Fiscal Need Thousand Yen')]
 pd.DataFrame(mapping,columns=['Original Name','Readable Name']).to_csv(OUT/'variable_mapping.csv',index=False)
 report={'status':'passed_with_preserved_geographic_gaps','financial_governments':len(f),'traffic_segments':len(linked),'traffic_governments':linked['Government Code'].nunique(),
  'meshes':len(mesh),'financially_linked_meshes':int(mesh['Government Code'].notna().sum()),'unlinked_meshes':len(unresolved),
  'linked_mesh_governments':mesh['Government Code'].nunique(),'old_hamamatsu_ward_codes_reconciled':7,'fiscal_year':2023,'amount_unit':'Thousand JPY',
  'missing_financial_fields':f.isna().sum().to_dict(),'units_verified_from_official_template':True,
  'zero_financial_denominator_policy':'Keep ratio NaN; no zero fill','maintenance_scope':'Road plus bridge purpose rows only; excludes forestry roads and urban street purpose rows',
  'finance_strength_measure':'Single-year standard revenue/need; not undecoded three-year strength field',
  'unchanged_sources':True,'decision':'MILI-D-20261011-002','unused_snapshot':'municipality_overview.csv is Table 01 intermunicipal membership, not a fiscal overview; not used'}
 (OUT/'input_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
