#!/usr/bin/env python3
"""Validate line clipping independently and prepare pixel/grid area overlaps.

Spatial weights are independent of the final light-aggregation choice.
This script does not construct a mean/sum radiance analysis variable.
"""
import csv
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
from osgeo import ogr,osr
from construct_road_pilot_trial import (ROOT,OUT,WEST,SOUTH,DX,DY,SIZE,
    initialize_gdal,spatial_reference,mesh_code,polygon,split_segment,geographic_lines)


def extent_cells(extent):
    x0,x1,y0,y1=extent
    left=max(0,math.floor((x0-WEST)/DX));right=min(SIZE-1,math.floor((x1-WEST)/DX))
    bottom=max(0,math.floor((y0-SOUTH)/DY));top=min(SIZE-1,math.floor((y1-SOUTH)/DY))
    return [(r,c) for r in range(bottom,top+1) for c in range(left,right+1)]


def rectangle(x0,y0,x1,y1):
    ring=ogr.Geometry(ogr.wkbLinearRing)
    for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]:ring.AddPoint_2D(x,y)
    result=ogr.Geometry(ogr.wkbPolygon);result.AddGeometry(ring)
    return result


def main():
    initialize_gdal()
    common=spatial_reference(4612);metric=spatial_reference(2444)
    measure=osr.CoordinateTransformation(common,metric)
    meshes={mesh_code(r,c):polygon(r,c) for r in range(SIZE) for c in range(SIZE)}
    source=ROOT/'data/raw/roads/n13_lines/2024/N13-24_5030_GEOJSON.zip'
    with zipfile.ZipFile(source) as z:member=next(n for n in z.namelist() if n.endswith('.geojson'))
    data=ogr.Open('/vsizip/'+str(source)+'/'+member);layer=data.GetLayer()
    ref=layer.GetSpatialRef();ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform=osr.CoordinateTransformation(ref,common)
    audit=[]
    for feature in layer:
        if str(feature.GetField('N13_002'))!='1' or str(feature.GetField('N13_004')) not in ('1','2','3','4'):continue
        geometry=feature.GetGeometryRef().Clone();geometry.Transform(transform)
        cells=extent_cells(geometry.GetEnvelope())
        if len(cells)<2:continue
        expected={};actual=defaultdict(float)
        for r,c in cells:
            cut=geometry.Intersection(meshes[mesh_code(r,c)])
            if not cut.IsEmpty():cut.Transform(measure);expected[mesh_code(r,c)]=cut.Length()
        for points in geographic_lines(geometry):
            for first,last in zip(points,points[1:]):
                for r,c,endpoints in split_segment(first,last):
                    if 0<=r<SIZE and 0<=c<SIZE:
                        a,b=measure.TransformPoints(endpoints)
                        actual[mesh_code(r,c)]+=math.hypot(a[0]-b[0],a[1]-b[1])
        delta=max((abs(expected.get(key,0)-actual.get(key,0)) for key in set(expected)|set(actual)),default=0)
        audit.append(dict(source_fid=feature.GetFID(),candidate_cells=len(cells),geos_clipped_length_m=sum(expected.values()),
                          allocated_length_m=sum(actual.values()),max_cell_difference_m=delta))
        if len(audit)==150:break
    pd.DataFrame(audit).to_csv(OUT/'independent_clipping_validation.csv',index=False)
    if max(r['max_cell_difference_m'] for r in audit)>.01:raise ValueError('Independent GEOS clipping differs by more than 1 cm')
    print(f'Independent clipping: {len(audit)} crossing features; max delta={max(r["max_cell_difference_m"] for r in audit):.6g} m',flush=True)
    del data,layer
    raster_metadata=json.loads((ROOT/'data/exp/data-organization/tables/nighttime_raster_metadata.json').read_text())
    groups={};coverage=[];mapping=[]
    from_wgs=osr.CoordinateTransformation(spatial_reference(4326),common)
    for item in raster_metadata:
        year=int(item['year'])
        if year==1995:continue
        tags=item['tags'];dx,dy=tags['33550'][:2];west,north=tags['33922'][3:5]
        pixels=pd.read_csv(ROOT/f'data/exp/data-organization/nighttime-pilot/{year}_native_pixels.csv')
        signature=(dx,dy,west,north,int(pixels.raster_row.min()),int(pixels.raster_row.max()),int(pixels.raster_column.min()),int(pixels.raster_column.max()))
        if signature in groups:
            name=groups[signature];mapping.append(dict(year=year,overlap_file=name));continue
        name=f'{year}_pixel_mesh_overlaps.csv';groups[signature]=name
        weights=[];covered=defaultdict(float)
        for index,pixel in enumerate(pixels.itertuples(index=False),1):
            row,col=int(pixel.raster_row),int(pixel.raster_column)
            x0=west+col*dx;y1=north-row*dy
            p=rectangle(x0,y1-dy,x0+dx,y1);p.Transform(from_wgs)
            for r,c in extent_cells(p.GetEnvelope()):
                code=mesh_code(r,c);cut=p.Intersection(meshes[code])
                if cut.IsEmpty():continue
                cut.Transform(measure);area=cut.GetArea()
                if area<=0:continue
                weights.append(dict(mesh_code=code,raster_row=row,raster_column=col,overlap_area_m2=area))
                covered[code]+=area
            if index%10000==0:print(f'{year} pixel/grid overlaps: {index:,}/{len(pixels):,}',flush=True)
        pd.DataFrame(weights).to_csv(OUT/name,index=False)
        for code,p in meshes.items():
            projected=p.Clone();projected.Transform(measure);area=projected.GetArea()
            coverage.append(dict(geometry_reference_year=year,mesh_code=code,covered_area_m2=covered[code],mesh_area_m2=area,geometric_coverage_fraction=covered[code]/area))
        mapping.append(dict(year=year,overlap_file=name))
        print(f'{year}: {len(weights):,} overlaps; geometry cache ready',flush=True)
    pd.DataFrame(mapping).to_csv(OUT/'nighttime_overlap_file_mapping.csv',index=False)
    table=pd.DataFrame(coverage);table.to_csv(OUT/'nighttime_geometric_coverage.csv',index=False)
    if table.geometric_coverage_fraction.min()<.9999 or table.geometric_coverage_fraction.max()>1.0001:raise ValueError('Incomplete or double-counted geometric raster coverage')
    summary=dict(independent_clipping_features=len(audit),maximum_clipping_difference_m=max(r['max_cell_difference_m'] for r in audit),
                 unique_native_grid_layouts=len(groups),minimum_raster_geometric_coverage=table.geometric_coverage_fraction.min(),
                 maximum_raster_geometric_coverage=table.geometric_coverage_fraction.max(),final_light_aggregation_selected=False)
    (OUT/'spatial_alignment_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
