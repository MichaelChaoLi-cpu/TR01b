"""Construct approved static facility mesh inputs, preserving all source records.

Run --stage bus-input, --stage geometry, --stage prepare in separate processes.
The geometry stage uses GDAL without importing Arrow. The prepare stage writes
the skill decisions and confirmed parquet inputs for per-dataset scripts.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/static-facilities'
INVENTORY = OUT / 'source-inventory'
DEST = 'data/processed/national/static_facilities'
DECISION = 'MILI-D-20261010-017'

SCHOOL = {'16001':'Primary School', '16002':'Junior High School', '16003':'Secondary School',
          '16004':'High School', '16005':'Technical College', '16006':'Junior College',
          '16007':'University', '16011':'Kindergarten', '16012':'Special Needs School',
          '16013':'Integrated Early Childhood Centre', '16014':'Compulsory Education School',
          '16015':'Miscellaneous School', '16016':'Specialized Training College'}
MEDICAL = {1:'Hospital', 2:'General Clinic', 3:'Dental Clinic'}
LOGISTICS = {1:'Container Terminal', 2:'Air Cargo Terminal', 3:'Freight Railway Station',
             4:'Bonded Facility', 5:'Truck Terminal', 7:'Wholesale Market'}
VISITOR = {1:'Cinema', 2:'Public Assembly Hall', 3:'Theatre', 4:'Exhibition Venue',
           5:'Spectator Venue', 6:'Other Visitor Facility'}
POI = [('schools', 'P29_004', 'P29_003', ['P29_003','P29_008'], SCHOOL, 'School Facility', 2023),
       ('medical', 'P04_002', 'P04_001', ['P04_001'], MEDICAL, 'Medical Facility', 2020),
       ('logistics', 'P31_001', 'P31_002', ['P31_002','P31_003'], LOGISTICS, 'Logistics Facility', 2013),
       ('visitor_facilities', 'P33_005', 'P33_004', ['P33_004'], VISITOR, 'Visitor and Event Facility', 2014)]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def key_hash(rows):
    result = hashlib.sha256()
    for row in rows:
        key = [row['source_archive'], row['source_member'], int(row['source_feature_id'])]
        result.update(json.dumps(key, ensure_ascii=False, separators=(',', ':')).encode() + b'\n')
    return result.hexdigest()


def bus_input():
    import pandas as pd
    source = ROOT / 'data/exp/data-augmentation-screening/bus-terminal-candidates/terminal_candidate_stop_records.parquet'
    frame = pd.read_parquet(source)
    rows = [dict(source_archive=r.source_archive, source_member=r.source_member,
                 source_feature_id=i, source_geometry_wkt=f'POINT ({r.longitude:.17g} {r.latitude:.17g})',
                 source_crs_wkt='EPSG:6668') for i,r in enumerate(frame.itertuples(index=False))]
    with gzip.open(INVENTORY / 'bus_candidates.jsonl.gz', 'wt', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    (OUT / 'bus_input_validation.json').write_text(json.dumps(dict(source=str(source.relative_to(ROOT)),
        sha256=sha(source), source_records=len(frame), temporary_numeric_row_index_not_facility_id=True),indent=2)+'\n')
    print('Bus candidate geometry input:', len(rows), flush=True)


def geometry():
    from osgeo import ogr, osr
    ogr.UseExceptions(); osr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    geo = osr.SpatialReference(); geo.ImportFromEPSG(4612)
    geo.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    cache = OUT / 'geometry-cache'; cache.mkdir(exist_ok=True)
    reports = []
    for kind in [p[0] for p in POI] + ['railway_Station', 'airports_TerminalBuilding', 'bus_candidates']:
        path = INVENTORY / (kind + '.jsonl.gz')
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream]
        points, lengths = [], []
        transforms, metrics = {}, {}
        for row in rows:
            crs = row['source_crs_wkt']
            if crs is None:
                assert kind == 'logistics'
                # P31 official product page explicitly declares JGD2000 despite
                # the missing PRJ components in the archived shapefiles.
                crs = 'EPSG:4612'
            if crs not in transforms:
                native = osr.SpatialReference()
                native.SetFromUserInput(crs)
                native.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                transforms[crs] = osr.CoordinateTransformation(native, geo)
            geom = ogr.CreateGeometryFromWkt(row['source_geometry_wkt'])
            assert geom is not None and not geom.IsEmpty()
            geom.Transform(transforms[crs])
            if kind == 'railway_Station':
                centre = geom.Centroid(); x, y = centre.GetX(), centre.GetY()
                tile = (int(x), int(y * 1.5))
                if tile not in metrics:
                    metric = geo.Clone(); metric.SetProjCS('Local station section metric reference')
                    metric.SetTM((tile[1] + .5) * 2/3, tile[0] + .5, 1, 0, 0)
                    metrics[tile] = (osr.CoordinateTransformation(geo, metric), osr.CoordinateTransformation(metric, geo))
                forward, backward = metrics[tile]
                geom.Transform(forward)
                length = geom.Length(); assert length > 0
                centre = geom.Centroid(); centre.Transform(backward)
                points.append([centre.GetX(), centre.GetY()]); lengths.append(length)
            else:
                assert geom.GetGeometryName() == 'POINT'
                points.append([geom.GetX(), geom.GetY()]); lengths.append(0.)
        xy = np.asarray(points)
        assert np.isfinite(xy).all() and (xy[:,0] > 120).all() and (xy[:,0] < 155).all()
        assert (xy[:,1] > 20).all() and (xy[:,1] < 46).all()
        np.savez_compressed(cache / (kind + '.npz'), coordinates=xy, length_m=np.asarray(lengths))
        report = dict(category=kind, input_sha256=sha(path), source_key_sha256=key_hash(rows),
                      records=len(rows), output_datum='JGD2000 EPSG:4612',
                      missing_prj_reference='Official P31 product JGD2000' if kind=='logistics' else None)
        (cache / (kind + '.json')).write_text(json.dumps(report,indent=2)+'\n')
        reports.append(report); print('Geometry prepared:',kind,len(rows),flush=True)
    (OUT/'geometry_validation.json').write_text(json.dumps(dict(status='passed', categories=reports),indent=2)+'\n')


def load(kind):
    import pandas as pd
    path = INVENTORY / (kind + '.parquet')
    frame = pd.read_parquet(path)
    cache = OUT / 'geometry-cache'
    audit = json.loads((cache / (kind + '.json')).read_text())
    assert sha(INVENTORY / (kind + '.jsonl.gz')) == audit['input_sha256']
    assert key_hash(frame.to_dict('records')) == audit['source_key_sha256']
    with np.load(cache / (kind + '.npz')) as arrays:
        frame['Longitude'] = arrays['coordinates'][:,0]
        frame['Latitude'] = arrays['coordinates'][:,1]
        frame['Section Length'] = arrays['length_m']
    return frame


def prepare():
    import pandas as pd
    from facility_geodesy import mesh_codes, mesh_centres, nearest
    staging = OUT / 'confirmed-inputs'; staging.mkdir(exist_ok=True)
    ledger = OUT / 'facility-ledgers'; ledger.mkdir(exist_ok=True)
    grid = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet')
    codes = grid.mesh_code.astype('string')
    centre_lon, centre_lat = mesh_centres(codes)
    assert np.array_equal(mesh_codes(centre_lon,centre_lat),codes.to_numpy())
    contract = dict(confirmed=True, decision_id=DECISION, temporal_decision='MILI-D-20261010-016',
                    datasets={}, analytical_variables_are_candidates_not_regression_terms=True)
    audits = []

    def count(points, mask=None):
        target = points if mask is None else points.loc[mask]
        values = target['Mesh Code'].value_counts()
        return codes.map(values).fillna(0).astype('int32').to_numpy()

    def register(kind, frame, analytical, source_details):
        path = staging / (kind + '_confirmed_input.parquet')
        frame.to_parquet(path,index=False)
        variables = [dict(original_name=c,readable_name=c,full_name=c,preprocessing=[],
                          is_final_variable='yes' if c in analytical else 'no',
                          role='TBD' if c in analytical else 'reference') for c in frame]
        contract['datasets'][str(path.relative_to(ROOT))] = dict(output=f'{DEST}/{kind}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_static_{kind}.py', variables=variables,
            source_details=source_details, spatial_preparation='src/preprocessing/prepare_static_facility_meshes.py')

    for kind, name, field, partitions, classifications, prefix, year in POI:
        raw = load(kind)
        identity = [name, 'source_geometry_wkt'] + partitions
        selected = raw.drop_duplicates(identity).copy()
        selected['Mesh Code'] = mesh_codes(selected.Longitude, selected.Latitude)
        outside = ~selected['Mesh Code'].isin(codes)
        selected['Inside Study Grid'] = ~outside
        selected.to_parquet(ledger / (kind + '_allocated_facilities.parquet'),index=False)
        output = pd.DataFrame({'Mesh Code':codes, prefix+' Count':count(selected)})
        analytical = [prefix+' Count']
        assert set(selected[field]) <= set(classifications)
        for code,label in classifications.items():
            col = label+' Count'; output[col] = count(selected,selected[field].eq(code)); analytical.append(col)
        np.testing.assert_array_equal(output[analytical[1:]].sum(axis=1),output[analytical[0]])
        output[prefix+' Source Year'] = np.int16(year)
        output[prefix+' Archives Complete'] = True
        details = dict(raw_name=name, raw_classification=field, duplicate_identity=identity,
                       classes=classifications, filters='No status exclusion; source categories retained',
                       zero_rule='No observed selected record in the complete nationwide inventory',
                       missing_rule='Unavailable location or archive remains missing, never imputed',
                       source_edition=year, raw_records=len(raw), retained_records=len(selected),
                       exact_duplicates_removed=len(raw)-len(selected), outside_grid_records=int(outside.sum()),
                       allocated_records=int((~outside).sum()), count_sum=int(output[analytical[0]].sum()))
        assert details['count_sum']==details['allocated_records']
        register(kind,output,analytical,details);audits.append(dict(category=kind,**details))
        print('POI allocated:',kind,len(selected),'outside',int(outside.sum()),flush=True)

    railway = load('railway_Station')
    representatives = railway[railway.N02_005c.eq(railway.N02_005g)].drop_duplicates(['N02_005g','source_geometry_wkt']).copy()
    absent=set(railway.N02_005g)-set(representatives.N02_005g)
    unresolved=railway[railway.N02_005g.isin(absent)]
    # One source group (Echizen-Takefu) names a nonexistent representative code.
    # Its single recorded station section gives an unambiguous observed position;
    # preserve the source group identifier and flag the linkage inconsistency.
    assert unresolved.groupby('N02_005g').size().eq(1).all()
    representatives=pd.concat([representatives,unresolved],ignore_index=True)
    assert set(representatives.N02_005g)==set(railway.N02_005g)
    rows=[]
    for group, part in representatives.groupby('N02_005g',sort=True):
        w=part['Section Length'].to_numpy()
        rows.append({'Station Group Code':group, 'Station Name':part.N02_005.iloc[0],
                     'Longitude':np.average(part.Longitude,weights=w), 'Latitude':np.average(part.Latitude,weights=w),
                     'Representative Sections':len(part), 'Group Source Records':int(railway.N02_005g.eq(group).sum()),
                     'Official Representative Code Missing':group in absent})
    stations=pd.DataFrame(rows)
    stations['Mesh Code']=mesh_codes(stations.Longitude,stations.Latitude)
    stations['Inside Study Grid']=stations['Mesh Code'].isin(codes)
    stations.to_parquet(ledger/'railway_station_groups.parquet',index=False)
    distance,matched=nearest(centre_lon,centre_lat,stations.Longitude,stations.Latitude)
    output=pd.DataFrame({'Mesh Code':codes,'Railway Station Count':count(stations),
                        'Distance to Railway Station':distance,'Railway Source Year':np.int16(2024),
                        'Nearest Station Group Code':stations['Station Group Code'].to_numpy()[matched],
                        'Railway Archives Complete':True})
    details=dict(source_records=len(railway),retained_groups=len(stations),
                 representative='Official group-code station; length-weighted centroid of its unique station-section geometries; a source group with one section and a missing designated code uses that observed section with an explicit flag',
                 groups_with_missing_designated_code=sorted(absent),
                 allocated_records=int(stations['Inside Study Grid'].sum()), outside_grid_records=int((~stations['Inside Study Grid']).sum()))
    assert output['Railway Station Count'].sum()==details['allocated_records']
    register('railway',output,['Railway Station Count','Distance to Railway Station'],details)
    audits.append(dict(category='railway',**details));print('Railway proximity complete',flush=True)

    airports=pd.read_parquet(INVENTORY/'airports_Airport.parquet')
    selected=airports[(airports.C28_004.eq('供用中')|airports.C28_004.eq('1'))&airports.C28_011.isin([1,2])].copy()
    links=selected[['C28_101','C28_102','C28_005','C28_004','C28_011']].drop_duplicates()
    assert links.C28_101.is_unique
    terminal=load('airports_TerminalBuilding')
    airport_rows=[]
    for terminal_id,part in links.groupby('C28_102',sort=True):
        point=terminal[terminal.C28_000.eq(terminal_id.removeprefix('#'))]
        assert len(point)==1
        airport_rows.append({'Airport Terminal Code':terminal_id.removeprefix('#'),
                            'Airport Names':' | '.join(sorted(part.C28_005)),
                            'Linked Airport Reference Codes':' | '.join(sorted(part.C28_101)),
                            'Shared Airport Reference Count':len(part),
                            'Longitude':point.Longitude.item(),'Latitude':point.Latitude.item()})
    passenger=pd.DataFrame(airport_rows);passenger['Mesh Code']=mesh_codes(passenger.Longitude,passenger.Latitude)
    passenger['Inside Study Grid']=passenger['Mesh Code'].isin(codes)
    passenger.to_parquet(ledger/'passenger_airport_terminals.parquet',index=False)
    distance,matched=nearest(centre_lon,centre_lat,passenger.Longitude,passenger.Latitude)
    output=pd.DataFrame({'Mesh Code':codes,'Passenger Airport Count':count(passenger),
                        'Distance to Passenger Airport':distance,'Airport Source Year':np.int16(2021),
                        'Nearest Airport Terminal Code':passenger['Airport Terminal Code'].to_numpy()[matched],
                        'Airport Archives Complete':True})
    details=dict(source_polygon_records=len(airports),eligible_reference_sites=len(links),
                 retained_passenger_terminal_points=len(passenger),
                 selection='Operating and regular-flight code in {1 jet, 2 propeller}; group shared terminal IDs',
                 shared_terminal_groups=int(passenger['Shared Airport Reference Count'].gt(1).sum()),
                 allocated_records=int(passenger['Inside Study Grid'].sum()),outside_grid_records=int((~passenger['Inside Study Grid']).sum()))
    assert output['Passenger Airport Count'].sum()==details['allocated_records']
    register('airports',output,['Passenger Airport Count','Distance to Passenger Airport'],details)
    audits.append(dict(category='airports',**details));print('Airport proximity complete',flush=True)

    source=ROOT/'data/exp/data-augmentation-screening/bus-terminal-candidates/terminal_candidate_stop_records.parquet'
    raw=pd.read_parquet(source)
    assert sha(source)==json.loads((OUT/'bus_input_validation.json').read_text())['sha256']
    with np.load(OUT/'geometry-cache/bus_candidates.npz') as arrays:
        raw['Longitude']=arrays['coordinates'][:,0];raw['Latitude']=arrays['coordinates'][:,1]
    flags=['peripheral_stop_name_flag','air_related_name_flag','port_related_name_flag',
           'freight_related_name_flag','abbreviation_name_flag']
    rows=[]
    for (name,lon,lat),part in raw.groupby(['bsn','longitude','latitude'],sort=True):
        row={'Candidate Name':name,'Longitude':part.Longitude.iloc[0],'Latitude':part.Latitude.iloc[0],
             'Regular Source Present':bool(part.source_code.eq('P11').any()),
             'Highway Source Present':bool(part.source_code.eq('P36').any()),'Source Records':len(part),
             'Original Longitude':lon,'Original Latitude':lat,
             'Source Record Keys':' | '.join(part.source_archive.astype(str)+'#'+part.source_feature_id.astype(str))}
        row.update({flag:bool(part[flag].any()) for flag in flags});rows.append(row)
    candidates=pd.DataFrame(rows);candidates['Mesh Code']=mesh_codes(candidates.Longitude,candidates.Latitude)
    candidates['Inside Study Grid']=candidates['Mesh Code'].isin(codes)
    candidates['Requires Facility Identity Review']=True
    candidates.to_parquet(ledger/'bus_terminal_candidate_locations.parquet',index=False)
    distance,matched=nearest(centre_lon,centre_lat,candidates.Longitude,candidates.Latitude)
    output=pd.DataFrame({'Mesh Code':codes,'Bus Terminal Candidate Count':count(candidates),
                        'Distance to Bus Terminal Candidate':distance,
                        'Regular Bus Terminal Candidate Count':count(candidates,candidates['Regular Source Present']),
                        'Highway Bus Terminal Candidate Count':count(candidates,candidates['Highway Source Present']),
                        'Regular Bus Source Year':np.int16(2022),'Highway Bus Source Year':np.int16(2023),
                        'Nearest Bus Terminal Candidate Name':candidates['Candidate Name'].to_numpy()[matched],
                        'Bus Candidate Archives Complete':True,'Bus Candidate Coverage Limited':True,
                        'Bus Candidate Identity Review Pending':True})
    for flag,label in zip(flags,['Peripheral','Air Related','Port Related','Freight Related','Abbreviation']):
        output['Bus Candidate '+label+' Count']=count(candidates,candidates[flag])
    details=dict(source_records=len(raw),retained_candidate_locations=len(candidates),
                 exact_repeated_name_coordinate_records=len(raw)-len(candidates),
                 allocated_records=int(candidates['Inside Study Grid'].sum()),
                 outside_grid_records=int((~candidates['Inside Study Grid']).sum()),
                 identity='Exact original name plus exact original longitude/latitude across P11/P36',
                 candidate_screen='Previously saved name-based screen; no flagged names silently excluded',
                 unlocated_source_stops=63, coverage='Observed candidate locations only, not a complete terminal inventory')
    assert output['Bus Terminal Candidate Count'].sum()==details['allocated_records']
    register('bus_candidates',output,['Bus Terminal Candidate Count','Distance to Bus Terminal Candidate'],details)
    audits.append(dict(category='bus_candidates',**details));print('Bus candidate proximity complete',flush=True)
    (OUT/'decisions.json').write_text(json.dumps(contract,indent=2)+'\n')
    (OUT/'mesh_construction_validation.json').write_text(json.dumps(dict(status='passed',decision_id=DECISION,
        complete_grid_meshes=len(codes),geodesic_distance_units='km',nearest_targets_include_facilities_outside_study_grid=True,
        no_log_transform=True,no_status_filters_on_poi=True,source_audits=audits),indent=2)+'\n')
    print('Confirmed mesh inputs saved for seven source groups.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['bus-input','geometry','prepare'],required=True)
    args=parser.parse_args()
    if args.stage=='bus-input':bus_input()
    elif args.stage=='geometry':geometry()
    else:prepare()
