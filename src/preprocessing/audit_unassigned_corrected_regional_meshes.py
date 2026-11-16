#!/usr/bin/env python3
"""Propose, but do not apply, local administrative matches for no-land meshes.

Read source polygons independently and measure each mesh rectangle's minimum
distance to nearby administrative land in its existing local metric projection.
No regression membership or confirmed classification changes in this audit.
"""
from pathlib import Path
import csv
import json
import zipfile
from osgeo import ogr, osr
from construct_regional_mesh_assignment import rectangle,reference,sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected'


def main():
    ogr.UseExceptions();osr.UseExceptions();osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    report=json.loads((OUT / 'geometry_validation.json').read_text())
    manifest=json.loads((ROOT / report['boundary_reference_manifest']).read_text())
    prefecture_region={f'{p:02d}':r for r,ps in report['regions'].items() for p in ps}
    geo=reference(4612)
    proposals=[]
    for code in report['unassigned_meshes']:
        west=100+int(code[2:4])+int(code[5])/8+int(code[7])/80
        south=int(code[:2])*2/3+int(code[4])/12+int(code[6])/120
        bounds=(west,south,west+1/80,south+1/120)
        target=osr.SpatialReference();target.ImportFromWkt(report['metric_projections'][code[:4]])
        target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        metric=osr.CoordinateTransformation(geo,target)
        box=rectangle(*bounds);box.Transform(metric)
        nearest={}
        for record in manifest:
            path=ROOT / record['path'];assert sha(path)==record['sha256']
            with zipfile.ZipFile(path) as archive:
                member=next(n for n in archive.namelist() if n.endswith('.shp'))
            dataset=ogr.Open('/vsizip/'+str(path)+'/'+member)
            layer=dataset.GetLayer();source=layer.GetSpatialRef().Clone()
            source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            inverse=osr.CoordinateTransformation(geo,source)
            corners=inverse.TransformPoints([(west-.25,south-.25),(west+1/80+.25,south+1/120+.25)])
            layer.SetSpatialFilterRect(corners[0][0],corners[0][1],corners[1][0],corners[1][1])
            transform=osr.CoordinateTransformation(source,target)
            region=prefecture_region[record['prefecture_code']]
            for feature in layer:
                geom=feature.GetGeometryRef().Clone()
                if not geom.IsValid():geom=geom.MakeValid()
                geom.Transform(transform)
                distance=box.Distance(geom)
                assert distance>=0
                if region not in nearest or distance<nearest[region][0]:
                    nearest[region]=(distance,record['prefecture_code'])
            dataset=None
        assert nearest
        ordered=sorted(nearest,key=lambda r:(nearest[r][0],r))
        chosen=ordered[0]
        assert nearest[chosen][0]<10000
        proposals.append(dict(mesh_code=code,proposed_region=chosen,nearest_prefecture_code=nearest[chosen][1],
            minimum_land_distance_m=nearest[chosen][0],longitude=west+1/160,latitude=south+1/240,
            other_region_in_local_search=','.join(ordered[1:]),
            proposal_only=True))
    with (OUT / 'unassigned_mesh_region_proposals.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(proposals[0]));writer.writeheader();writer.writerows(proposals)
    print(json.dumps(proposals,indent=2))


if __name__ == '__main__':main()
