#!/usr/bin/env python3
"""Compute authorized 2024 road-density trial on a common JGD2000 mesh.

Outputs are exploratory diagnostics, not an adopted analysis sample. Uses
existing local GDAL/PROJ, pandas, and numpy; does not install packages.
Run from the repository: python3 src/exp/construct_road_pilot_trial.py
"""
import csv
import hashlib
import json
import math
import struct
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from osgeo import gdal,ogr,osr

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/pilot'
WEST,SOUTH,DX,DY=130.0,100/3,1/80,1/120
SIZE=80


def spatial_reference(code):
    ref=osr.SpatialReference();ref.ImportFromEPSG(code)
    ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return ref


def initialize_gdal():
    gdal.UseExceptions();ogr.UseExceptions();osr.UseExceptions()
    try:
        spatial_reference(4612)
        fallback=False
    except RuntimeError:
        # The calling shell can point to an incompatible legacy Anaconda DB.
        # Correct only this process, never shell settings or global files.
        candidates=[Path('/opt/homebrew/share/proj'),Path('/usr/share/proj')]
        correct=next((p for p in candidates if (p/'proj.db').exists()),None)
        if correct is None:raise
        osr.SetPROJSearchPaths([str(correct)])
        spatial_reference(4612)
        fallback=True
    return fallback


def mesh_code(row,col):
    return f'5030{row//10}{col//10}{row%10}{col%10}'


def polygon(row,col):
    x=WEST+col*DX;y=SOUTH+row*DY
    ring=ogr.Geometry(ogr.wkbLinearRing)
    for lon,lat in [(x,y),(x+DX,y),(x+DX,y+DY),(x,y+DY),(x,y)]:ring.AddPoint_2D(lon,lat)
    poly=ogr.Geometry(ogr.wkbPolygon);poly.AddGeometry(ring)
    return poly


def split_segment(a,b):
    """Half-open grid allocation; each segment piece has exactly one owner.

    Boundaries are intersected in target geographic coordinates, then each
    piece is measured in the same local metre-based projection. This avoids
    counting road lines lying along a shared mesh edge twice.
    """
    ax,ay=a[:2];bx,by=b[:2]
    ts=[0.0,1.0]
    for start,end,origin,step in [(ax,bx,WEST,DX),(ay,by,SOUTH,DY)]:
        if start==end:continue
        lo=max(0,math.ceil((min(start,end)-origin)/step))
        hi=min(SIZE,math.floor((max(start,end)-origin)/step))
        for index in range(lo,hi+1):
            t=(origin+index*step-start)/(end-start)
            if 1e-12<t<1-1e-12:ts.append(t)
    ts=sorted(set(ts))
    for first,last in zip(ts,ts[1:]):
        mid=(first+last)/2
        x=ax+(bx-ax)*mid;y=ay+(by-ay)*mid
        col=math.floor((x-WEST)/DX+1e-10)
        row=math.floor((y-SOUTH)/DY+1e-10)
        # Include outer east/north edges in the adjacent interior cell only.
        if col==SIZE and abs(x-(WEST+SIZE*DX))<1e-10:col=SIZE-1
        if row==SIZE and abs(y-(SOUTH+SIZE*DY))<1e-10:row=SIZE-1
        endpoints=[(ax+(bx-ax)*t,ay+(by-ay)*t) for t in (first,last)]
        yield row,col,endpoints


def geographic_lines(geometry):
    kind=ogr.GT_Flatten(geometry.GetGeometryType())
    if kind==ogr.wkbLineString:yield geometry.GetPoints()
    elif kind==ogr.wkbMultiLineString:
        for index in range(geometry.GetGeometryCount()):yield geometry.GetGeometryRef(index).GetPoints()
    else:raise ValueError(f'Unexpected road geometry: {geometry.GetGeometryName()}')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fallback=initialize_gdal()
    common=spatial_reference(4612);metric=spatial_reference(2444)
    measure=osr.CoordinateTransformation(common,metric)
    grid=[];polygons={}
    for row in range(SIZE):
        for col in range(SIZE):
            p=polygon(row,col);polygons[mesh_code(row,col)]=p.Clone();p.Transform(measure)
            grid.append(dict(mesh_code=mesh_code(row,col),grid_row=row,grid_column=col,
                             longitude=WEST+(col+.5)*DX,latitude=SOUTH+(row+.5)*DY,
                             common_mesh_area_km2=p.GetArea()/1e6))
    pd.DataFrame(grid).to_csv(OUT/'common_grid_trial.csv',index=False)
    source=ROOT/'data/raw/roads/n13_lines/2024/N13-24_5030_GEOJSON.zip'
    with zipfile.ZipFile(source) as z:member=next(n for n in z.namelist() if n.endswith('.geojson'))
    dataset=ogr.Open('/vsizip/'+str(source)+'/'+member);layer=dataset.GetLayer()
    ref=layer.GetSpatialRef()
    if ref is None or ref.GetAuthorityCode(None)!='6668':raise ValueError('2024 source CRS is not confirmed JGD2011')
    ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_common=osr.CoordinateTransformation(ref,common)
    lengths=np.zeros((SIZE,SIZE));unknown_width=np.zeros((SIZE,SIZE));touches=np.zeros((SIZE,SIZE),dtype=int)
    counters=Counter();duplicates=[];seen={};full_length=allocated=outside=0.0
    start=time.monotonic()
    for number,feature in enumerate(layer,1):
        counters['source_features']+=1
        typ=str(feature.GetField('N13_002'));state=str(feature.GetField('N13_004'))
        if typ!='1':counters['excluded_nonordinary_type']+=1;continue
        if state not in ('1','2','3','4'):counters['excluded_construction_other_unknown_state']+=1;continue
        geometry=feature.GetGeometryRef()
        if geometry is None or geometry.IsEmpty():counters['empty_geometry']+=1;continue
        counters['included_features']+=1
        # Flag identical geometry on the same level, without deduplicating it.
        key=(hashlib.blake2b(bytes(geometry.ExportToWkb()),digest_size=16).hexdigest(),feature.GetField('N13_005'))
        if key in seen:
            duplicates.append(dict(first_fid=seen[key],duplicate_fid=feature.GetFID(),level=key[1]))
        else:seen[key]=feature.GetFID()
        touched=set()
        for native in geographic_lines(geometry):
            points=to_common.TransformPoints(native)
            projected=measure.TransformPoints(points)
            full_length+=sum(math.hypot(q[0]-p[0],q[1]-p[1]) for p,q in zip(projected,projected[1:]))
            for a,b in zip(points,points[1:]):
                for row,col,endpoints in split_segment(a,b):
                    p,q=measure.TransformPoints(endpoints)
                    length=math.hypot(q[0]-p[0],q[1]-p[1])
                    if 0<=row<SIZE and 0<=col<SIZE:
                        lengths[row,col]+=length;allocated+=length;touched.add((row,col))
                        if str(feature.GetField('N13_006'))=='6':unknown_width[row,col]+=length
                    else:outside+=length
        for row,col in touched:touches[row,col]+=1
        if number%100000==0:print(f'2024: scanned {number:,} features; {time.monotonic()-start:.1f}s',flush=True)
    frame=pd.DataFrame(grid)
    frame['road_length_km']=lengths.ravel()/1000
    frame['road_length_density']=frame.road_length_km/frame.common_mesh_area_km2
    frame['ordinary_road_feature_intersections']=touches.ravel()
    frame['unknown_width_length_km']=unknown_width.ravel()/1000
    frame['road_source_year']=2024
    frame['source_comparability_verified']=False
    frame.to_csv(OUT/'2024_road_grid_trial.csv',index=False)
    histories=[];checks=[]
    for year in (2002,2003,2004,2010):
        view=next((ROOT/'data/exp/data-organization/source-tables').glob(f'n04_mesh_{year}_*.csv'))
        raw=pd.read_csv(view,dtype=str,keep_default_na=False)
        actual='N04_055' if year==2010 else 'N04_037';norm='N04_056' if year==2010 else 'N04_038'
        history=pd.DataFrame({'mesh_code':raw.N04_001,'road_source_year':year,
                              'road_length_literal':raw[actual],'road_density_literal':raw[norm],
                              'source_area_literal':raw.N04_002})
        history['source_mesh_area_km2']=pd.to_numeric(raw.N04_002,errors='coerce')/(1 if year==2010 else 1e6)
        history['road_length_km']=pd.to_numeric(raw[actual],errors='coerce')/1000
        history['road_length_density']=pd.to_numeric(raw[norm],errors='coerce')/1000
        history['source_row_present']=True
        history['source_unknown']=history.road_length_density.isna()
        history['normalization_anomaly']=abs(history.road_length_km/history.source_mesh_area_km2-history.road_length_density)>.001
        history['source_comparability_verified']=False
        histories.append(history)
        merge=history.merge(frame[['mesh_code','road_length_density','common_mesh_area_km2']],on='mesh_code',suffixes=('_historical','_2024'))
        valid=merge.dropna(subset=['road_length_density_historical'])
        delta=valid.road_length_density_2024-valid.road_length_density_historical
        area=(valid.source_mesh_area_km2-valid.common_mesh_area_km2)/valid.common_mesh_area_km2
        checks.append(dict(road_year=year,source_rows=len(history),numeric_rows=len(valid),unknown_rows=int(history.source_unknown.sum()),anomalous_rows=int(history.normalization_anomaly.sum()),
                           median_density_difference_2024_minus_historical=delta.median(),median_source_area_relative_difference=area.median(),
                           max_absolute_area_relative_difference=abs(area).max(),interpretation='Source transition plus real time change; not attributable to road growth alone'))
    pd.concat(histories,ignore_index=True).to_csv(OUT/'historical_road_grid_trial.csv',index=False)
    pd.DataFrame(checks).to_csv(OUT/'road_trial_comparison.csv',index=False)
    pd.DataFrame(duplicates,columns=['first_fid','duplicate_fid','level']).to_csv(OUT/'2024_identical_geometry_flags.csv',index=False)
    residual=allocated+outside-full_length
    summary=dict(counters=counters,source_crs=6668,common_grid_crs=4612,metric_crs=2444,
                 proj_search_paths=osr.GetPROJSearchPaths(),legacy_proj_database_corrected_in_process=fallback,
                 grid_meshes=len(frame),total_projected_source_length_km=full_length/1000,allocated_length_km=allocated/1000,
                 outside_target_grid_length_km=outside/1000,length_conservation_residual_m=residual,
                 identical_geometry_same_level_count=len(duplicates),duplicate_geometries_removed=False,
                 minimum_mesh_area_km2=frame.common_mesh_area_km2.min(),maximum_mesh_area_km2=frame.common_mesh_area_km2.max(),
                 source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),gdal_version=gdal.VersionInfo(),python=sys.version,
                 source_comparability_verified=False,final_analysis_sample_selected=False)
    (OUT/'road_trial_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    if abs(residual)>max(.01,full_length*1e-7):raise ValueError('Grid allocation does not conserve line length')
    print(json.dumps(summary,default=dict),flush=True)


if __name__=='__main__':main()
