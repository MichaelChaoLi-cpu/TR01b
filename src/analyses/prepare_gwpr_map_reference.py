#!/usr/bin/env python3
"""Create contextual map outlines from already cached official boundaries.

Run separately from Arrow to avoid GDAL/Arrow library conflicts. Geometry
simplification affects only the background illustration, never estimates.
"""
from pathlib import Path
import json
import zipfile

from osgeo import ogr,osr

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/gwpr-twoways'


def main():
    ogr.UseExceptions(); osr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    manifest=json.loads((ROOT/'data/exp/data-preprocessing/regional/reference/manifest.json').read_text())
    lines=[]
    for entry in manifest:
        path=ROOT/entry['path']
        with zipfile.ZipFile(path) as archive:
            member=next(m for m in archive.namelist() if m.endswith('.shp') and 'subprefecture' not in m)
        source=ogr.Open('/vsizip/'+str(path)+'/'+member)
        layer=source.GetLayer()
        for feature in layer:
            geometry=feature.GetGeometryRef()
            if geometry is None: continue
            simplified=geometry.SimplifyPreserveTopology(.015)
            if simplified is None: continue
            def exterior(g):
                kind=ogr.GT_Flatten(g.GetGeometryType())
                if kind==ogr.wkbPolygon:
                    ring=g.GetGeometryRef(0)
                    if ring is not None and ring.GetPointCount()>3:
                        lines.append([[ring.GetX(i),ring.GetY(i)] for i in range(ring.GetPointCount())])
                elif kind in [ogr.wkbMultiPolygon,ogr.wkbGeometryCollection]:
                    for i in range(g.GetGeometryCount()): exterior(g.GetGeometryRef(i))
            exterior(simplified)
        source=None
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'map_reference_lines.json').write_text(json.dumps({'lines':lines,'boundary_date':'2024-01-01',
        'source':'existing official N03 prefecture boundary archive cache',
        'simplification_degrees':.015,'role':'contextual background only; not a mesh or road mask'},separators=(',',':'))+'\n')
    print('Saved contextual boundary rings:',len(lines))


if __name__=='__main__': main()
