"""Focused read-only source availability check for municipality-level analysis.

Does not construct mesh assignments, change source values, or choose a model.
"""
from pathlib import Path
import json, struct, zipfile, hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/feasibility-check/municipality-analysis'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'data/exp/data-preprocessing/regional/reference/manifest.json').read_text())
    names=[];sources=[]
    for rec in manifest:
        p=ROOT/rec['path'];assert sha(p)==rec['sha256']
        with zipfile.ZipFile(p) as z:
            enc=z.read(next(n for n in z.namelist() if n.endswith('.cpg'))).decode().strip()
            b=z.read(next(n for n in z.namelist() if n.endswith('.dbf')))
        n,header,size=struct.unpack_from('<IHH',b,4);fields=[];off=32
        while b[off]!=13:
            e=b[off:off+32];fields.append((e[:11].split(b'\0')[0].decode('ascii'),e[16]));off+=32
        seen=set()
        for i in range(n):
            r=b[header+i*size:header+(i+1)*size]
            if r[:1]==b'*':continue
            off=1;v={}
            for name,width in fields:v[name]=r[off:off+width].decode(enc).strip();off+=width
            code=v['N03_007'];key=(code,v['N03_004'],v['N03_005'])
            if key in seen:continue
            seen.add(key)
            names.append({'Municipality Code':code,'Prefecture':v['N03_001'],'Municipality Name':v['N03_004'],
                          'Designated City Ward':v['N03_005'],'Boundary Year':2024})
        sources.append({'Dataset':'2024 N03 boundary attributes','File':rec['path'],'SHA256':rec['sha256'],
                        'Role':'Available boundary attributes; no new mesh allocation','Prefecture Code':rec['prefecture_code']})
    n=pd.DataFrame(names).drop_duplicates();n.to_csv(OUT/'boundary_municipality_attributes.csv',index=False)
    traffic_path=ROOT/'data/exp/road-economy-mismatch-trial/traffic_segment_reference_2021.parquet'
    t=pd.read_parquet(traffic_path);t['Municipality Code']=t['Municipality Code'].str.zfill(5)
    rows=[]
    for code,z in t.groupby('Municipality Code'):
        attrs=n[n['Municipality Code'].eq(code)]
        rows.append({'Municipality Code':code,'Boundary Code Match':not attrs.empty,
            'Boundary Names':'; '.join(sorted(set(attrs['Municipality Name']+' '+attrs['Designated City Ward']))),
            'Traffic Segment Rows':len(z),'Published Volume Rows':int(z['Published 24h Volume'].notna().sum()),
            'Designated City Managed Rows':int(z['Road Manager'].eq(3).sum()),
            'Prefecture Managed Rows':int(z['Road Manager'].eq(2).sum()),'Traffic Year':2021})
    availability=pd.DataFrame(rows);availability.to_csv(OUT/'municipality_traffic_code_availability.csv',index=False)
    availability.loc[~availability['Boundary Code Match']].to_csv(OUT/'unmatched_2021_traffic_codes.csv',index=False)
    dataset=[{'Dataset':'Latest revised mesh screen','Rows':383386,'Format':'parquet',
              'Feasibility':'Mesh values available; municipal geometry allocation not constructed'},
             {'Dataset':'2021 national traffic references','Rows':len(t),'Format':'parquet',
              'Feasibility':'Municipal code exists; census excludes most ordinary municipal roads'},
             {'Dataset':'2024 N03 boundary archives','Rows':len(n),'Format':'ZIP/DBF/GIS',
              'Feasibility':'47 verified archives available; ward-to-city and year alignment required'},
             {'Dataset':'Municipal fiscal maintenance table 20, catalogue 2024','Rows':None,'Format':'Official CSV/Excel available online',
              'Feasibility':'Official source identified; not downloaded or numerically audited'}]
    pd.DataFrame(dataset).to_csv(OUT/'focused_dataset_availability.csv',index=False)
    pd.DataFrame(sources).to_csv(OUT/'boundary_source_checksums.csv',index=False)
    info={'status':'partly_feasible_data_linkage_pending','verified_boundary_archives':len(manifest),
          'traffic_municipal_codes':len(availability),'traffic_codes_matching_2024_boundary':int(availability['Boundary Code Match'].sum()),
          'traffic_codes_not_matching_2024_boundary':int((~availability['Boundary Code Match']).sum()),
          'codes_with_designated_city_managed_segments':int(availability['Designated City Managed Rows'].gt(0).sum()),
          'mesh_municipality_assignment_available':False,'municipal_fiscal_values_downloaded':False,
          'model_or_aggregation_choice':'Awaiting user preference; no final municipality model selected',
          'source_values_modified':False,'anasop_modified':False,
          'fiscal_source':'https://www.e-stat.go.jp/stat-search/files?layout=dataset&stat_infid=000040231622&toukei=00200251',
          'generic_helper_limitation':'Bundled name-matching check supports CSV/TSV/TXT, so detected zero processed inputs because current processed inputs are parquet. Its labels do not assess actual project feasibility.'}
    (OUT/'focused_validation.json').write_text(json.dumps(info,indent=2)+'\n')
    text='''# Municipality-level feasibility check\n\nThe bundled generic feasibility helper cannot read the existing Parquet panel; its zero-input variable-name labels do not establish a lack of data. This focused check reads the actual traffic reference and all 47 checksum-verified boundary attribute archives. AnaSOP Sections 1-8 retain their existing research contract.\n\n## Available evidence\n\n- Existing 2024 mesh screen: original roads, radiance, 2020 population and selected context are available. Municipal mesh assignment has not been constructed.\n- 2021 traffic records contain municipality codes and manager classes. Ordinary municipal roads are mostly outside the official census. Manager code 3 identifies designated-city management, not management by every municipality. Geographic presence of surveyed national or prefectural roads does not attribute their upkeep to the host municipality.\n- 2024 administrative boundaries retain municipality names, codes and designated-city ward names. Financial analysis should distinguish designated-city administrative wards from the parent city; Tokyo special wards require their own treatment. Exact same-name or prefix matching alone is not enough to validate a fiscal jurisdiction. Traffic codes are as of 2021-04-01, while existing boundaries are 2024-01-01. Unmatched codes are explicitly exported, not discarded or filled.\n- Official e-Stat municipal maintenance Table 20 is publicly available in CSV/Excel. Actual financial year, units, individual-government coverage, road/bridge categories, expenditure and fiscal-resource denominators still need acquisition and auditing. Existing fiscal references cover prefecture governments only.\n\n## Possible analyses and limits\n\nMunicipality-level road-economy associations can be estimated once mesh membership and local support are established. A territorial mismatch-utilization-finance analysis additionally requires municipal fiscal data and aligned statistical geography. It would initially establish territorial association, not the maintenance cost of excess municipality-owned roads. Attributable burden requires a municipality-managed road inventory and transport-function evidence. No final aggregation rule, threshold or new model is selected by this feasibility check.\n\nA user preference is pending between territorial mismatch/utilization/finance summaries and separate within-municipality road-radiance regressions. The immediate next workflow is data-preprocessing for approved municipal allocation and source variables, followed by the responsible estimation planning skill. This check does not alter the question or generate formal outputs.\n\n## Reproduction\n\nRun `python3 src/exp/check_municipality_analysis_feasibility.py`. Source downloads are reused read-only; required local dependencies are pandas and pyarrow plus Python standard library. `focused_validation.json` and the exported code ledgers report exact availability.\n'''
    (OUT/'focused_README.md').write_text(text)
    p=OUT/'README.md';s=p.read_text();warning='> Reader limitation: the generic helper excludes Parquet. Its zero-input labels are not substantive research verdicts. See focused_README.md and focused_dataset_availability.csv for the source-verified municipal assessment.\n\n'
    if warning not in s:p.write_text(s.replace('# Feasibility Check\n\n','# Feasibility Check\n\n'+warning,1))
    print(json.dumps(info,indent=2))
if __name__=='__main__':main()
