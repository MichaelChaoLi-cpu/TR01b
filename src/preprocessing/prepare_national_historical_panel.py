#!/usr/bin/env python3
"""Prepare confirmed nationwide historical inputs; preserve all source archives.

Raster values are streamed from ZIP tiles, without extracting global TIFFs.
Shared geographic subdivisions implement exact rectangle intersections, measured
in local projected coordinates. No source rescaling, imputation or sample filter.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import math
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/exp'))
from audit_source_archives import dbf

OUT = ROOT/'data/exp/data-preprocessing/national'
STAGING = OUT/'confirmed-inputs'
YEARS = [2002, 2003, 2004, 2010]
POP = {2000:'T000146', 2005:'T000148', 2010:'T000608'}
DX, DY = 1/80, 1/120


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(epsg):
    s = osr.SpatialReference();s.ImportFromEPSG(epsg)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def tiles():
    return sorted({p.name.split('_')[1].split('-')[0]
                   for p in (ROOT/'data/raw/roads/n04_mesh').rglob('*.zip')} |
                  {p.stem.split('_')[1] for y in POP for p in (ROOT/f'data/raw/population/estat_1km/{y}').glob('*.zip')})


def mesh_codes(tile):
    return [tile+str(r//10)+str(c//10)+str(r%10)+str(c%10) for r in range(80) for c in range(80)]


def register(kind, year, frame, mapping, details):
    path = STAGING/f'{kind}_{year}_confirmed_input.parquet'
    frame.to_parquet(path, index=False)
    roles = {'road_length_density':'main explanatory', 'population':'control', 'nighttime_radiance':'outcome'}
    variables = [dict(original_name=a, readable_name=b, full_name=b,
                      is_final_variable='yes' if a in roles else 'no', preprocessing=[],
                      role=roles.get(a,'reference')) for a,b in mapping.items()]
    return str(path.relative_to(ROOT)), dict(output=f'data/processed/national/{kind}_{year}_preprocessed.parquet',
        script=f'src/preprocessing/preprocess_national_{kind}_{year}.py', variables=variables,
        spatial_preparation='src/preprocessing/prepare_national_historical_panel.py', source_details=details)


def checked_archive(path, manifest):
    expected = manifest.loc[str(path.relative_to(ROOT))]
    assert expected['status'] == 'downloaded_verified'
    digest = sha(path)
    assert digest == expected['sha256'], path
    return digest


def prepare_attributes():
    STAGING.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(ROOT/'data/exp/data-organization/tables/download_manifest.csv').set_index('local_path')
    grid = pd.DataFrame({'mesh_code':pd.array([c for tile in tiles() for c in mesh_codes(tile)],dtype='string')})
    grid.to_parquet(OUT/'common_grid.parquet', index=False)
    datasets, audits, hashes = {}, [], {}
    for year in YEARS:
        parts=[]
        for path in sorted((ROOT/f'data/raw/roads/n04_mesh/{year}').glob('*.zip')):
            hashes[str(path.relative_to(ROOT))] = checked_archive(path,manifest)
            with zipfile.ZipFile(path) as z:
                rows,fields,deleted = dbf(z.read(next(n for n in z.namelist() if n.endswith('.dbf'))))
            assert deleted == 0
            raw = pd.DataFrame(rows)
            actual,norm = ('N04_055','N04_056') if year==2010 else ('N04_037','N04_038')
            assert raw.N04_001.str.len().eq(8).all() and raw.N04_001.str.startswith(path.name.split('_')[1][:4]).all()
            area=pd.to_numeric(raw.N04_002,errors='coerce')/(1 if year==2010 else 1e6)
            length=pd.to_numeric(raw[actual],errors='coerce')/1000
            density=pd.to_numeric(raw[norm],errors='coerce')/1000
            unknown=~np.isfinite(np.column_stack([area,length,density])).all(axis=1)
            part=pd.DataFrame({'mesh_code':raw.N04_001,'road_length_km':length.mask(unknown),
                'road_length_density':density.mask(unknown),'mesh_area_km2':area.mask(unknown),
                'source_unknown':unknown,'source_row_present':True})
            if year==2010:
                hit=part.mesh_code.eq('50302281')
                if hit.any():
                    assert part.loc[hit,'road_length_km'].item()==.003
                    part.loc[hit,'road_length_km']=12.143
            part['normalization_anomaly']=(abs(part.road_length_km/part.mesh_area_km2-part.road_length_density)*1000>.51)
            audits.append(dict(source=str(path.relative_to(ROOT)),source_rows=len(raw),source_unknown=int(unknown.sum()),
                numeric_rows=int((~unknown).sum()),normalization_anomalies=int(part.normalization_anomaly.sum())))
            parts.append(part)
        source=pd.concat(parts,ignore_index=True)
        assert source.mesh_code.is_unique
        frame=grid.merge(source,on='mesh_code',how='left',validate='one_to_one')
        frame['source_row_present']=frame.source_row_present.fillna(False).astype(bool)
        frame['road_year']=year
        frame[['mesh_code','road_year','source_row_present','source_unknown','normalization_anomaly']].to_parquet(OUT/f'road_quality_{year}.parquet',index=False)
        key,spec=register('roads',year,frame[['mesh_code','road_length_km','road_length_density','mesh_area_km2','road_year']],
            {'mesh_code':'Mesh Code','road_length_km':'Road Length','road_length_density':'Road Length Density','mesh_area_km2':'Mesh Area','road_year':'Road Year'},
            dict(raw_fields=['N04_001','N04_002',actual,norm],length_unit='km',density_unit='km/km2',
                 unknown_and_unlisted='NaN',known_2010_length_repair='MILI-D-20261009-005',other_anomalies='retain and flag; supplied density unchanged'))
        datasets[key]=spec
        print(f'roads {year}: {len(frame):,} common meshes, {frame.road_length_density.notna().sum():,} numeric, {frame.normalization_anomaly.sum()} normalization flags',flush=True)
    for year,stats in POP.items():
        parts=[]
        for path in sorted((ROOT/f'data/raw/population/estat_1km/{year}').glob('*.zip')):
            hashes[str(path.relative_to(ROOT))]=checked_archive(path,manifest)
            with zipfile.ZipFile(path) as z:
                text=z.read(next(n for n in z.namelist() if n.endswith('.txt'))).decode('cp932')
            rows=list(csv.reader(io.StringIO(text)))
            raw=pd.DataFrame(rows[2:],columns=rows[0])
            assert raw.KEY_CODE.str.len().eq(8).all()
            part=pd.DataFrame({'mesh_code':raw.KEY_CODE,'population':pd.to_numeric(raw[stats+'001'],errors='coerce')})
            audits.append(dict(source=str(path.relative_to(ROOT)),source_rows=len(raw),numeric_rows=int(part.population.notna().sum()),
                               source_total_population=float(part.population.sum())))
            parts.append(part)
        source=pd.concat(parts,ignore_index=True)
        assert source.mesh_code.is_unique and source.mesh_code.isin(grid.mesh_code).all()
        frame=grid.merge(source,on='mesh_code',how='left',validate='one_to_one');frame['population_year']=year
        pd.DataFrame({'mesh_code':grid.mesh_code,'population_year':year,'source_row_present':grid.mesh_code.isin(source.mesh_code)}).to_parquet(OUT/f'population_quality_{year}.parquet',index=False)
        key,spec=register('population',year,frame,{'mesh_code':'Mesh Code','population':'Population','population_year':'Population Year'},
            dict(total_field=stats+'001',unlisted_or_nonnumeric='NaN',imputation=False,reaggregation=False))
        datasets[key]=spec
        print(f'population {year}: {frame.population.notna().sum():,} numeric, total {frame.population.sum():,.0f}',flush=True)
    pd.DataFrame(audits).to_csv(OUT/'source_attribute_audit.csv',index=False)
    (OUT/'decisions.json').write_text(json.dumps(dict(datasets=datasets,confirmed=True,
        confirmed_decisions=['MILI-D-20261009-003','MILI-D-20261009-004','MILI-D-20261009-005','MILI-D-20261009-009','MILI-D-20261009-010','MILI-D-20261009-013','MILI-D-20261009-015'],
        national_primary_tiles=tiles(),complete_meshes=len(grid),raw_sha256=hashes,raw_modified=False),indent=2)+'\n')


def layout():
    cache=ROOT/'data/exp/data-organization/nighttime-pilot'
    indexes=[json.loads((cache/f'{y}_tiff_index.json').read_text()) for y in YEARS]
    assert all(x==indexes[0] for x in indexes)
    return indexes[0]['tags']


def bbox(tile,tags):
    south=int(tile[:2])*2/3;west=int(tile[2:])+100
    dx,dy=tags['33550'][:2];x0,y0=tags['33922'][3:5]
    return math.floor((y0-south-2/3)/dy),math.ceil((y0-south)/dy),math.floor((west-x0)/dx),math.ceil((west+1-x0)/dx)


def build_weights():
    # GDAL's bundled Arrow and local PyArrow must not initialize in the same
    # Parquet-writing process. Geometry runs in its own stage.
    global osr
    from osgeo import osr
    osr.UseExceptions();osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    geo=reference(4612);datum=osr.CoordinateTransformation(reference(4326),geo)
    tags=layout();dx,dy=tags['33550'][:2];x0,y0=tags['33922'][3:5]
    cache=OUT/'overlap-cache';cache.mkdir(parents=True,exist_ok=True)
    from osgeo import ogr
    metadata=[];independent=[]
    rng=np.random.default_rng(20261009)
    def rectangle(a,b,c,d):
        ring=ogr.Geometry(ogr.wkbLinearRing)
        for x,y in [(a,b),(c,b),(c,d),(a,d),(a,b)]:ring.AddPoint_2D(x,y)
        result=ogr.Geometry(ogr.wkbPolygon);result.AddGeometry(ring);return result
    for i,tile in enumerate(tiles(),1):
        target=cache/f'{tile}.npz'
        south=int(tile[:2])*2/3;west=int(tile[2:])+100
        r0,r1,c0,c1=bbox(tile,tags)
        corners=[(west,south),(west+1,south+2/3)]
        assert np.allclose(np.array(datum.TransformPoints(corners))[:,:2],corners,atol=1e-12,rtol=0)
        metric=reference(2444) if tile=='5030' else reference(4612)
        if tile!='5030':
            metric.SetProjCS('Local mesh-centered transverse Mercator')
            metric.SetTM(south+1/3,west+.5,1,0,0)
        transform=osr.CoordinateTransformation(geo,metric)
        if not target.exists():
            gx=west+np.arange(81)*DX;gy=south+np.arange(81)*DY
            px=x0+np.arange(c0,c1+1)*dx;py=y0-np.arange(r0,r1+1)*dy
            xs=np.unique(np.r_[gx,px[(px>west)&(px<west+1)]]);ys=np.unique(np.r_[gy,py[(py>south)&(py<south+2/3)]])
            xx,yy=np.meshgrid(xs,ys)
            projected=np.array(transform.TransformPoints(np.column_stack([xx.ravel(),yy.ravel()]).tolist()))[:,:2].reshape(len(ys),len(xs),2)
            p00=projected[:-1,:-1];p10=projected[:-1,1:]-p00;p11=projected[1:,1:]-p00;p01=projected[1:,:-1]-p00
            area=abs((p10[:,:,0]*p11[:,:,1]-p10[:,:,1]*p11[:,:,0]+p11[:,:,0]*p01[:,:,1]-p11[:,:,1]*p01[:,:,0])/2)
            midx=(xs[:-1]+xs[1:])/2;midy=(ys[:-1]+ys[1:])/2
            mc=np.clip(np.floor((midx-west)/DX).astype(int),0,79);mr=np.clip(np.floor((midy-south)/DY).astype(int),0,79)
            mesh=(mr[:,None]*80+mc[None,:]).astype(np.int32)
            rc=np.floor((midx-x0)/dx).astype(np.int32);rr=np.floor((y0-midy)/dy).astype(np.int32)
            cornersx,cornersy=np.meshgrid(gx,gy)
            q=np.array(transform.TransformPoints(np.column_stack([cornersx.ravel(),cornersy.ravel()]).tolist()))[:,:2].reshape(81,81,2)
            origin=q[:-1,:-1];a=q[:-1,1:]-origin;b=q[1:,1:]-origin;c=q[1:,:-1]-origin
            mesh_area=abs((a[:,:,0]*b[:,:,1]-a[:,:,1]*b[:,:,0]+b[:,:,0]*c[:,:,1]-b[:,:,1]*c[:,:,0])/2).ravel()
            np.savez_compressed(target,mesh=mesh.ravel(),raster_row=np.broadcast_to(rr[:,None],area.shape).ravel(),
                raster_column=np.broadcast_to(rc[None,:],area.shape).ravel(),area=area.ravel(),mesh_area=mesh_area)
        with np.load(target) as w:
            coverage=np.bincount(w['mesh'],weights=w['area'],minlength=6400)/w['mesh_area']
            for index in rng.choice(np.flatnonzero(w['area']>1),3,replace=False):
                mr,mc=divmod(int(w['mesh'][index]),80)
                rr,rc=int(w['raster_row'][index]),int(w['raster_column'][index])
                pixel=rectangle(x0+rc*dx,y0-(rr+1)*dy,x0+(rc+1)*dx,y0-rr*dy)
                cell=rectangle(west+mc*DX,south+mr*DY,west+(mc+1)*DX,south+(mr+1)*DY)
                clipped=pixel.Intersection(cell);clipped.Transform(transform)
                expected=clipped.GetArea();delta=abs(expected-float(w['area'][index]))
                assert delta<=max(.02,expected*1e-7),(tile,index,delta)
                independent.append(dict(primary_tile=tile,weight_index=int(index),geos_area_m2=expected,
                                        computed_area_m2=float(w['area'][index]),difference_m2=delta))
        assert coverage.min()>.99999 and coverage.max()<1.00001
        metadata.append(dict(primary_tile=tile,metric_wkt=metric.ExportToWkt(),minimum_geometric_coverage=float(coverage.min()),maximum_geometric_coverage=float(coverage.max()),weight_sha256=sha(target)))
        if i%20==0 or i==len(tiles()):print(f'area overlap weights {i}/{len(tiles())}',flush=True)
    pd.DataFrame(independent).to_csv(OUT/'independent_area_validation.csv',index=False)
    (OUT/'geometry_validation.json').write_text(json.dumps(dict(layout_identical_for_years=YEARS,datum_transform_identity_checked=True,
        independent_geos_intersections=len(independent),maximum_independent_area_difference_m2=max(x['difference_m2'] for x in independent),
        measurement='Projected intersection area; local transverse Mercator per tile; existing EPSG2444 retained for pilot tile 5030',tiles=metadata),indent=2)+'\n')


def stream_raster(year):
    tags=layout();tw,th=tags['322'][0],tags['323'][0];width,height=tags['256'][0],tags['257'][0]
    across=math.ceil(width/tw);bounds=[bbox(tile,tags) for tile in tiles()]
    r0=min(b[0] for b in bounds);r1=max(b[1] for b in bounds);c0=min(b[2] for b in bounds);c1=max(b[3] for b in bounds)
    nodata=np.float32(float(tags['42113']));window=np.full((r1-r0,c1-c0),nodata,dtype=np.float32)
    chosen=set()
    for top,bottom,left,right in bounds:
        chosen.update((tile_row,tile_col) for tile_row in range(top//th,(bottom-1)//th+1)
                      for tile_col in range(left//tw,(right-1)//tw+1))
    blocks=sorted((tags['324'][r*across+c],tags['325'][r*across+c],r,c) for r,c in chosen)
    archive=ROOT/f'data/raw/nighttime_lights/viirs_like_v2/dataset_10.1/{year}/{year}_Version2.zip'
    print(f'lights {year}: stream {len(blocks):,} native tiles into {window.shape} window',flush=True)
    with zipfile.ZipFile(archive) as z:
        member=next(n for n in z.namelist() if n.endswith('.tif'))
        with z.open(member) as f:
            assert f.read(2)==b'II'
            for offset,size,r,c in blocks:
                f.seek(offset)
                data=np.frombuffer(f.read(size),dtype='<f4').reshape(th,tw)
                a=max(r0,r*th);b=min(r1,(r+1)*th);left=max(c0,c*tw);right=min(c1,(c+1)*tw)
                window[a-r0:b-r0,left-c0:right-c0]=data[a-r*th:b-r*th,left-c*tw:right-c*tw]
    return window,r0,c0,nodata


def prepare_lights():
    OUT.mkdir(parents=True,exist_ok=True)
    assert (OUT/'geometry_validation.json').exists(), 'Run --stage weights first'
    contract=json.loads((OUT/'decisions.json').read_text());summaries=[]
    manifest=pd.read_csv(ROOT/'data/exp/data-organization/tables/download_manifest.csv').set_index('local_path')
    for year in YEARS:
        archive=ROOT/f'data/raw/nighttime_lights/viirs_like_v2/dataset_10.1/{year}/{year}_Version2.zip'
        contract['raw_sha256'][str(archive.relative_to(ROOT))]=checked_archive(archive,manifest)
        window,r0,c0,nodata=stream_raster(year);parts=[]
        for tile in tiles():
            with np.load(OUT/f'overlap-cache/{tile}.npz') as w:
                values=window[w['raster_row']-r0,w['raster_column']-c0]
                valid=np.isfinite(values)&(values!=nodata)
                area=np.bincount(w['mesh'],weights=np.where(valid,w['area'],0),minlength=6400)
                numerator=np.bincount(w['mesh'],weights=np.where(valid,values,0)*w['area'],minlength=6400)
                average=np.divide(numerator,area,out=np.full(6400,np.nan),where=area>0)
                coverage=area/w['mesh_area']
            assert (coverage>=0).all() and coverage.max()<1.00001
            parts.append(pd.DataFrame({'mesh_code':pd.array(mesh_codes(tile),dtype='string'),'nighttime_radiance':average,
                'nighttime_light_year':year,'nighttime_light_coverage':np.minimum(coverage,1)}))
        frame=pd.concat(parts,ignore_index=True)
        # Pilot equivalence checks validate this scalable intersection implementation.
        prior=pd.read_parquet(ROOT/f'data/processed/pilot/lights_{year}_preprocessed.parquet')
        paired=frame.set_index('mesh_code').loc[prior['Mesh Code']]
        delta=abs(paired.nighttime_radiance.to_numpy()-prior['Nighttime Radiance'].to_numpy())
        assert np.allclose(paired.nighttime_radiance,prior['Nighttime Radiance'],atol=1e-7,rtol=1e-8),float(delta.max())
        key,spec=register('lights',year,frame,{'mesh_code':'Mesh Code','nighttime_radiance':'Nighttime Radiance',
            'nighttime_light_year':'Nighttime Light Year','nighttime_light_coverage':'Nighttime Light Coverage'},
            dict(construction='Valid native pixel intersection-area-weighted mean; full mesh footprint; local metric area',
                 source_archive=str(archive.relative_to(ROOT)),nodata=float(nodata),raw_layout='WGS84 PixelIsArea',imputation=False))
        contract['datasets'][key]=spec
        summaries.append(dict(year=year,complete_meshes=len(frame),numeric_meshes=int(frame.nighttime_radiance.notna().sum()),
            zero_meshes=int(frame.nighttime_radiance.eq(0).sum()),minimum_coverage=float(frame.nighttime_light_coverage.min()),
            maximum_pilot_overlap_difference=float(delta.max())))
        (OUT/'decisions.json').write_text(json.dumps(contract,indent=2)+'\n')
        print(f'lights {year}: {len(frame):,} meshes; pilot max difference {delta.max():.3g}',flush=True)
        del window
    pd.DataFrame(summaries).to_csv(OUT/'light_aggregation_validation.csv',index=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['attributes','weights','lights'],required=True)
    args=parser.parse_args()
    if args.stage=='attributes':prepare_attributes()
    elif args.stage=='weights':build_weights()
    else:prepare_lights()
