"""Independent geodesic checks, source conservation and source-archive audit.

Run --stage prepare-checks followed by --stage geometry-checks separately.
The GDAL process never initializes the local Arrow writer.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/static-facilities'


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def prepare_checks():
    import pandas as pd
    from facility_geodesy import mesh_centres, nearest
    validation=json.loads((OUT/'panel_linkage_validation.json').read_text())
    assert validation['status']=='passed' and validation['complete_meshes']==972800
    assert [r['rows'] for r in validation['panel_outputs']]==[4864000,1144940]
    mesh=pd.read_parquet(ROOT/validation['mesh_table'])
    centres=mesh_centres(mesh['Mesh Code'])
    rng=np.random.default_rng(20261010);chosen=rng.choice(len(mesh),size=12,replace=False)
    ledgers=OUT/'facility-ledgers'
    requests=[]
    for name,file,col in [('railway','railway_station_groups.parquet','Distance to Railway Station'),
                          ('airports','passenger_airport_terminals.parquet','Distance to Passenger Airport'),
                          ('bus_candidates','bus_terminal_candidate_locations.parquet','Distance to Bus Terminal Candidate')]:
        targets=pd.read_parquet(ledgers/file)
        queries=np.column_stack([centres[0][chosen],centres[1][chosen]])
        # Include coincident facilities to check the zero-distance branch.
        queries=np.vstack([queries,targets[['Longitude','Latitude']].iloc[[0]].to_numpy()])
        d,m=nearest(queries[:,0],queries[:,1],targets.Longitude,targets.Latitude)
        np.testing.assert_allclose(d[:12],mesh[col].iloc[chosen],rtol=0,atol=1e-6)
        assert d[-1]==0
        requests.append(dict(category=name,queries=queries.tolist(),
                             targets=targets[['Longitude','Latitude']].to_numpy().tolist(),
                             distances_km=d.tolist(),matched_indices=m.tolist()))
    (OUT/'independent_geodesic_inputs.json').write_text(json.dumps(requests)+'\n')
    bounds_checks=[]
    for path in sorted(ledgers.glob('*.parquet')):
        f=pd.read_parquet(path)
        x,y=mesh_centres(f['Mesh Code'])
        assert (f.Longitude.to_numpy()>=x-1/160-1e-11).all()
        assert (f.Longitude.to_numpy()<=x+1/160+1e-11).all()
        assert (f.Latitude.to_numpy()>=y-1/240-1e-11).all()
        assert (f.Latitude.to_numpy()<=y+1/240+1e-11).all()
        bounds_checks.append(dict(ledger=str(path.relative_to(ROOT)),records=len(f),inside_independent_mesh_bounds=True))
    catalogue=ROOT/'data/exp/data-augmentation-screening/mlit-facilities'
    archives=json.loads((catalogue/'facility_download_manifest.json').read_text())['records']
    archives+=json.loads((catalogue/'facility_download_manifest_bus_stops_highway_bus_stops.json').read_text())['records']
    rail=ROOT/'data/raw/railway/n02/2024/N02-24_GML.zip'
    archives.append(dict(path=str(rail.relative_to(ROOT)),sha256='504eefd4411cd0fd3ad9a50f35da2f5da07949d5144ded7630df0972f8deaac7'))
    for item in archives:
        path=ROOT/item['path'];assert digest(path)==item['sha256']
        with zipfile.ZipFile(path) as stream:assert stream.testzip() is None
    source_validation=dict(status='passed',archives_sha256_and_crc_verified=len(archives),
                           all_allocated_coordinates_within_independent_mesh_bounds=True,
                           source_ledgers=bounds_checks)
    (OUT/'source_preservation_validation.json').write_text(json.dumps(source_validation,indent=2)+'\n')
    print('Independent bounds and',len(archives),'source archives verified; geodesic inputs saved.',flush=True)


def geometry_checks():
    from osgeo import ogr,osr
    ogr.UseExceptions();osr.UseExceptions();osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    reference=osr.SpatialReference();reference.ImportFromEPSG(4612)
    reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    reports=[]
    for case in json.loads((OUT/'independent_geodesic_inputs.json').read_text()):
        maxima=[]
        for query,expected,matched in zip(case['queries'],case['distances_km'],case['matched_indices']):
            values=[]
            for target in case['targets']:
                line=ogr.Geometry(ogr.wkbLineString)
                line.AddPoint_2D(*query);line.AddPoint_2D(*target);line.AssignSpatialReference(reference)
                values.append(line.GeodesicLength()/1000)
            values=np.asarray(values)
            difference=abs(expected-values.min())
            assert difference<1e-6,(case['category'],query,difference)
            assert values[matched]<=values.min()+1e-6
            maxima.append(difference)
        reports.append(dict(category=case['category'],queries=len(maxima),
                            exhaustive_reference_targets=len(case['targets']),
                            maximum_difference_km=max(maxima),reference='GDAL 3.11 GeodesicLength on GRS80'))
    result=dict(status='passed',distance_tolerance_km=1e-6,categories=reports)
    (OUT/'independent_geodesic_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['prepare-checks','geometry-checks'],required=True)
    args=parser.parse_args()
    if args.stage=='prepare-checks':prepare_checks()
    else:geometry_checks()
