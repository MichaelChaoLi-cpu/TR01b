"""Prepare the approved 2024 extension under existing readable-variable rules.

Run --stage population, --stage weights, --stage lights, --stage roads,
then generate per-dataset scripts from the saved decisions and link the panel.
Raw inputs and historical processed files are preserved.
"""
from pathlib import Path
import argparse
import csv
import io
import json
import zipfile

import numpy as np
import pandas as pd
import prepare_national_historical_panel as prior

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/five-period-2024'
DEST='data/processed/national/five_period'
DECISION='MILI-D-20261010-012'


def save_dataset(kind,year,frame,mapping,details):
    staging=OUT/'confirmed-inputs'; staging.mkdir(parents=True,exist_ok=True)
    path=staging/f'{kind}_{year}_confirmed_input.parquet'
    frame[list(mapping)].to_parquet(path,index=False)
    roles={'population':'control','road_length_density':'main explanatory','nighttime_radiance':'outcome'}
    spec=dict(output=f'{DEST}/{kind}_{year}_preprocessed.parquet',
              script=f'src/preprocessing/preprocess_national_five_period_{kind}_{year}.py',
              variables=[dict(original_name=a,readable_name=b,full_name=b,
                              is_final_variable='yes' if a in roles else 'no',
                              preprocessing=[],role=roles.get(a,'reference')) for a,b in mapping.items()],
              source_details=details)
    p=OUT/'decisions.json'
    contract=json.loads(p.read_text()) if p.exists() else dict(confirmed=True,decision_id=DECISION,datasets={},raw_sha256={})
    contract['datasets'][str(path.relative_to(ROOT))]=spec
    p.write_text(json.dumps(contract,indent=2)+'\n')


def population():
    grid=pd.read_parquet(ROOT/'data/exp/data-preprocessing/national/common_grid.parquet')
    manifest=pd.read_csv(ROOT/'data/exp/data-organization/tables/download_manifest.csv').set_index('local_path')
    parts=[]; covered=set(); audits=[]
    for p in sorted((ROOT/'data/raw/population/estat_1km/2020').glob('*.zip')):
        digest=prior.checked_archive(p,manifest); tile=p.stem.split('_')[1]; assert tile not in covered; covered.add(tile)
        with zipfile.ZipFile(p) as z:
            names=[n for n in z.namelist() if n.endswith('.txt')]; assert len(names)==1
            rows=list(csv.reader(io.StringIO(z.read(names[0]).decode('cp932'))))
        raw=pd.DataFrame(rows[2:],columns=rows[0])
        assert raw.KEY_CODE.str.startswith(tile).all() and raw.KEY_CODE.str.fullmatch(r'\d{8}').all()
        pop=pd.to_numeric(raw.T001100001,errors='coerce'); pop=pop.mask(~np.isfinite(pop))
        assert pop.dropna().ge(0).all()
        male=pd.to_numeric(raw.T001100002,errors='coerce'); female=pd.to_numeric(raw.T001100003,errors='coerce')
        hit=np.isfinite(pop)&np.isfinite(male)&np.isfinite(female)
        assert (male[hit]+female[hit]).eq(pop[hit]).all()
        parts.append(pd.DataFrame({'mesh_code':raw.KEY_CODE,'population':pop,'source_present':True,
                                  'disclosure_status':raw.HTKSYORI.astype('string'),
                                  'disclosure_destination':raw.HTKSAKI.astype('string'),
                                  'merged_mesh_codes':raw.GASSAN.astype('string')}))
        audits.append(dict(source=str(p.relative_to(ROOT)),tile=tile,rows=len(raw),population_sum=float(pop.sum()),sha256=digest))
    source=pd.concat(parts,ignore_index=True)
    assert source.mesh_code.is_unique and source.population.sum()==126146099
    assert source.mesh_code.isin(grid.mesh_code).all()
    frame=grid.merge(source,on='mesh_code',how='left',validate='one_to_one')
    present=frame.source_present.eq(True); covered_mask=frame.mesh_code.str[:4].isin(covered)
    zeros=covered_mask&~present; frame.loc[zeros,'population']=0.; frame['population_year']=2020
    assert frame.population.sum()==126146099
    quality=pd.DataFrame({'Mesh Code':frame.mesh_code,'Source Row Present':present,'Source Tile Covered':covered_mask,
                          'Population Structural Zero':zeros,'Invalid Published Total':present&frame.population.isna()})
    quality.to_parquet(OUT/'population_quality_2020.parquet',index=False)
    metadata=frame[['mesh_code','disclosure_status','disclosure_destination','merged_mesh_codes']].rename(columns={
        'mesh_code':'Mesh Code','disclosure_status':'Disclosure Status','disclosure_destination':'Disclosure Destination','merged_mesh_codes':'Merged Mesh Codes'})
    for c in metadata.columns[1:]: metadata[c]=metadata[c].replace('',pd.NA).astype('string')
    metadata.to_parquet(OUT/'population_metadata_2020.parquet',index=False)
    save_dataset('population',2020,frame,{'mesh_code':'Mesh Code','population':'Population','population_year':'Population Year'},
                 dict(total_field='T001100001',zero_rule='Absent record in verified complete source tile is zero',
                      gap_rule='Missing archive or invalid published total is NaN',imputation=False,reaggregation=False))
    pd.DataFrame(audits).to_csv(OUT/'population_raw_audit.csv',index=False)
    report=dict(status='passed',archives=len(covered),source_records=len(source),structural_zero_meshes=int(zeros.sum()),
                missing_meshes=int(frame.population.isna().sum()),population_sum=int(frame.population.sum()),
                coverage_gap_tiles=sorted(set(grid.mesh_code.str[:4])-covered))
    (OUT/'population_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)


def roads():
    grid=pd.read_parquet(ROOT/'data/exp/data-preprocessing/national/common_grid.parquet')
    frame=grid.copy(); lengths=np.full(len(grid),np.nan); areas=lengths.copy(); audits=[]
    quality=pd.DataFrame({'Mesh Code':grid.mesh_code,'Source Tile Covered':False})
    for tile in grid.mesh_code.str[:4].drop_duplicates():
        cache=OUT/f'road-cache/{tile}.npz'; path=ROOT/f'data/raw/roads/n13_lines/2024/N13-24_{tile}_GEOJSON.zip'
        if not path.exists(): assert not cache.exists(); continue
        assert cache.exists(),tile
        audit=json.loads((cache.with_suffix('.json')).read_text());assert prior.sha(path)==audit['source_sha256']
        audits.append(audit); mask=grid.mesh_code.str.startswith(tile).to_numpy()
        with np.load(cache) as w: lengths[mask]=w['length_km'];areas[mask]=w['area_km2']
        quality.loc[mask,'Source Tile Covered']=True
    frame['road_length_km']=lengths;frame['mesh_area_km2']=areas
    frame['road_length_density']=lengths/areas;frame['road_year']=2024
    pilot=pd.read_parquet(ROOT/'data/processed/pilot/roads_2024_preprocessed.parquet').set_index('Mesh Code')
    pair=frame.set_index('mesh_code').loc[pilot.index]
    for a,b in [('road_length_km','Road Length'),('mesh_area_km2','Mesh Area'),('road_length_density','Road Length Density')]:
        np.testing.assert_allclose(pair[a],pilot[b],rtol=1e-8,atol=1e-7)
    save_dataset('roads',2024,frame,{'mesh_code':'Mesh Code','road_length_km':'Road Length','road_length_density':'Road Length Density',
                                   'mesh_area_km2':'Mesh Area','road_year':'Road Year'},
                 dict(filter='N13_002 == 1; N13_004 in 1,2,3,4; retain unknown width and duplicate geometry with audit',
                      density='Projected centreline length / projected full mesh area',source_equivalence_established=False,
                      calibration=False,missing_archive='NaN; zero only inside complete covered road tiles'))
    quality.to_parquet(OUT/'road_quality_2024.parquet',index=False)
    report=dict(status='passed',target_meshes=len(grid),covered_tiles=len(audits),
                numeric_meshes=int(frame.road_length_density.notna().sum()),zero_meshes=int(frame.road_length_density.eq(0).sum()),
                pilot_equivalence_passed=True,raw_archives_unchanged=True,tile_audits=audits)
    (OUT/'road_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k!='tile_audits'},flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['population','roads','weights','lights'],required=True);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='population':population()
    elif args.stage=='roads':roads()
    else:
        prior.OUT=OUT;prior.STAGING=OUT/'confirmed-inputs';prior.YEARS=[2024]
        if args.stage=='weights':prior.build_weights()
        else:
            prior.prepare_lights()
            p=OUT/'decisions.json';contract=json.loads(p.read_text())
            for spec in contract['datasets'].values():
                if spec['output'].endswith('lights_2024_preprocessed.parquet'):
                    spec['output']=f'{DEST}/lights_2024_preprocessed.parquet'
                    spec['script']='src/preprocessing/preprocess_national_five_period_lights_2024.py'
            p.write_text(json.dumps(contract,indent=2)+'\n')


if __name__=='__main__':main()
