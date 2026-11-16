"""Independent saved municipal delivery verification; no estimator changes."""
from pathlib import Path
import json,hashlib,re
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/exp/municipality-mismatch-trial';SRC=OUT/'source_snapshots';P=ROOT/'data/processed/national/municipality_mismatch_trial'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def rawclean(d):
 keep=d['決算年度'].eq('2023')&d['団体区分'].isin(['1','2','3','4','5','8','9'])&d['団体コード '].str.strip().str.fullmatch(r'\d{5,6}').fillna(False)
 d=d[keep].copy();d['code']=d['団体コード '].str.strip().str.zfill(6).str[:5];return d

def main():
 d=pd.read_parquet(OUT/'municipal_mesh_ledger_2024.parquet');screen=pd.read_parquet(ROOT/'data/exp/road-economy-mismatch-light-zero-audit/revised_mesh_screen_2024.parquet')
 for col in screen:pd.testing.assert_series_equal(d[col],screen[col])
 assert len(d)==383386 and d['Mesh Code'].is_unique
 a=pd.read_parquet(OUT/'municipal_evidence_2024.parquet').set_index('Government Code');assert len(a)==1741 and a.index.is_unique
 # Recompute counts and stock independently from original candidate flags.
 grouped=d.dropna(subset=['Government Code']).groupby('Government Code');checks=0
 for code,z in grouped:
  cand=z['Potential Mismatch Candidate'].eq(True).fillna(False);supported=z['Potential Mismatch Candidate'].notna()
  assert int(a.loc[code,'Candidate Meshes'])==int(cand.sum())
  assert int(a.loc[code,'Supported Meshes'])==int(supported.sum())
  assert np.isclose(a.loc[code,'Candidate Fraction of Supported Meshes'],cand.sum()/supported.sum())
  assert np.isclose(a.loc[code,'Candidate Road Length'],z.loc[cand,'Road Length'].sum())
  checks+=1
 assert int(a['Cohort Meshes'].sum())+int(d['Government Code'].isna().sum())==383386
 assert int(a['Candidate Meshes'].sum())+int(d.loc[d['Government Code'].isna(),'Potential Mismatch Candidate'].eq(True).sum())==66088
 # Financial source amounts checked directly by original government identifier.
 cover=rawclean(pd.read_excel(SRC/'municipality_cover.xlsx',dtype=str)).set_index('code')
 balance=rawclean(pd.read_csv(SRC/'municipality_balance.csv',encoding='cp932',dtype=str));balance=balance[balance['行名称'].eq('令和5年度')].set_index('code')
 maintenance=rawclean(pd.concat([pd.read_csv(SRC/f'municipality_maintenance_{i}.csv',encoding='cp932',dtype=str) for i in range(1,4)]))
 for name,label in [('Road Maintenance Thousand Yen','道路'),('Bridge Maintenance Thousand Yen','橋りょう')]:
  raw=maintenance[maintenance['行名称'].eq(label)].set_index('code');np.testing.assert_array_equal(a[name],pd.to_numeric(raw.loc[a.index,'001:維持補修費']))
 for label,raw,col in [('Total Expenditure Thousand Yen',balance,'002:歳出総額'),('Standard Fiscal Scale Thousand Yen',cover,'008:標準財政規模（千円）'),('Standard Fiscal Revenue Thousand Yen',cover,'005:基準財政収入額（千円）'),('Standard Fiscal Need Thousand Yen',cover,'006:基準財政需要額（千円）')]:
  np.testing.assert_array_equal(a[label],pd.to_numeric(raw.loc[a.index,col]))
 np.testing.assert_allclose(a['Maintenance Share of Expenditure'],(a['Road Maintenance Thousand Yen']+a['Bridge Maintenance Thousand Yen'])/a['Total Expenditure Thousand Yen'],rtol=1e-13)
 t=pd.read_parquet(P/'municipal_traffic_reference_preprocessed.parquet');old=pd.read_parquet(ROOT/'data/exp/road-economy-mismatch-trial/traffic_segment_reference_2021.parquet')
 for col in old:pd.testing.assert_series_equal(t[col],old[col])
 assert t['Government Code'].notna().all() and len(t)==99417
 for code,z in t.groupby('Government Code'):
  valid=z['Published 24h Volume'].notna()&z['Segment Length'].gt(0);den=z.loc[valid,'Segment Length'].sum()
  if den>0:
   value=(z.loc[valid,'Published 24h Volume']*z.loc[valid,'Segment Length']).sum()/den
   assert np.isclose(value,a.loc[code,'Length Weighted 24h Volume'],rtol=1e-13)
 # All correlation exports checked with an independent centered-rank dot product.
 cor=pd.read_csv(OUT/'municipal_context_rank_correlations.csv');land=pd.read_csv(OUT/'municipal_land_context_summary.csv',dtype={'Government Code':str})
 for _,r in cor.iterrows():
  if r.Scope=='All municipal governments':z=a
  elif r.Scope.startswith('Land context: '):
   z=land[land['Land Context'].eq(r.Scope.removeprefix('Land context: '))].set_index('Government Code');z=z.join(a[[r.Outcome]],validate='one_to_one')
  else:z=a[a['Government Type'].eq('1')]
  pairs=z[[r.Predictor,r.Outcome]].dropna();assert len(pairs)==r.Municipalities
  x=pairs[r.Predictor].rank(method='average').to_numpy(copy=True);y=pairs[r.Outcome].rank(method='average').to_numpy(copy=True);x-=x.mean();y-=y.mean();den=np.sqrt(x@x*(y@y));rho=x@y/den if den>0 else np.nan
  assert np.isclose(rho,r.Spearman,rtol=1e-12,atol=1e-12,equal_nan=True)
 before=(OUT/'anasop_before_trial.md').read_text();after=(ROOT/'docs/AnaSOP.md').read_text()
 def sections(s):
  p=re.split(r'(?m)(^## [1-8]\. .+$)',s);return {int(p[i][3]):p[i]+p[i+1] for i in range(1,len(p),2)}
 b,c=sections(before),sections(after)
 for k in [1,2,8]:assert b[k]==c[k],k
 for k in [3,4,5,6,7]:assert b[k]!=c[k],k
 assert not re.search(r'[\u4e00-\u9fff]',after)
 assert after.count('\\[')==after.count('\\]') and after.count('\\(')==after.count('\\)')
 for eq in re.findall(r'\\\[(.*?)\\\]',after,re.S):assert eq.isascii()
 geom=json.loads((OUT/'independent_geometry_validation.json').read_text());assert geom['status']=='passed' and geom['independent_checks']==94
 protected={ROOT/'data/processed/national/land_cover_poi_extension/focused_extension_panel_preprocessed.parquet':'367624671e416ff01c6f69df0126addfd4fa69b523ee00b9e85c10b6e381c4b3',
 ROOT/'data/exp/land-cover-poi-extension/gwpr-local-constant-controls-5km/local_coefficients.parquet':'ec7ae7ceff715b8a44fc8f7571e264005b24d75cee80532a789e017f84420f14'}
 for p,h in protected.items():assert sha(p)==h,p
 report={'status':'passed','municipal_summaries_independently_checked':checks,'rank_comparisons_independently_checked':len(cor),
  'fiscal_amounts_agree_with_original_sources':True,'all_original_mesh_and_traffic_columns_preserved':True,'candidate_counts_conserved':True,
  'protected_panel_and_local_coefficient_hashes_unchanged':True,'independent_geometry_checks':94,'ana_sections_updated':[3,4,5,6,7],
  'ana_other_sections_preserved':True,'english_and_ascii_display_math_checked':True,'visual_review':'Municipal three-panel scatter and five-panel distribution figure reviewed',
  'substantive_limit':'Unadjusted territorial associations; no excess-road or causal-fiscal claim'}
 (OUT/'delivery_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
