"""Read official bus-stop GML and inventory terminal candidates without facility merging.

All original feature attributes and route structures are retained. Screening fields
are exploratory review aids, not selected regression variables or certified terminals.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/exp/data-augmentation-screening/bus-terminal-candidates'
MANIFEST = ROOT/'data/exp/data-augmentation-screening/mlit-facilities/facility_download_manifest_bus_stops_highway_bus_stops.json'
KSJ = '{http://nlftp.mlit.go.jp/ksj/schemas/ksj-app}'
GML = '{http://schemas.opengis.net/gml/3.2.1}'
XLINK = '{http://www.w3.org/1999/xlink}'
TERMS = ['ターミナル','バスセンター','バスステーション','バスプラザ',
         '交通センター','交通ターミナル','バス乗継','バス乗り継ぎ',
         'バス乗換','乗継センター','乗換センター','バス発着所','バス発着場','バスの駅']
ABBREVIATION = re.compile(r'(?<![A-Z])(?:BT|BC|OCAT|YCAT|T-CAT|TCAT)(?![A-Z])')
PERIPHERAL = re.compile(r'(?:ターミナル|センター|ステーション|バスプラザ|BT|BC)\s*(?:駅)?(?:前|入口|入り口|付近|向かい|[東西南北](?:口|側))')


def source_structure(element):
    """Keep namespace-qualified tags/attributes and all nested feature values."""
    obj = dict(tag=element.tag, attributes=element.attrib)
    if element.text and element.text.strip(): obj['text'] = element.text
    if len(element): obj['children'] = [source_structure(child) for child in element]
    return obj


def screen(name):
    normalized = unicodedata.normalize('NFKC', name or '')
    matches = [term for term in TERMS if term in normalized]
    if re.search(r'バスタ(?!ーミナル)', normalized): matches.append('バスタ')
    abbrev = bool(ABBREVIATION.search(normalized))
    if abbrev: matches.append('BT/BC/CAT abbreviation')
    return dict(screening_match_terms=' | '.join(matches),
                name_based_terminal_candidate=bool(matches),
                peripheral_stop_name_flag=bool(PERIPHERAL.search(normalized)),
                air_related_name_flag=bool(re.search(r'空港|航空|エア|飛行場', normalized)),
                port_related_name_flag=bool(re.search(r'港|フェリー|旅客船|客船|船舶|ポート|クルーズ', normalized)),
                freight_related_name_flag=bool(re.search(r'貨物|トラック|物流|コンテナ|配送', normalized)),
                abbreviation_name_flag=abbrev)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    assert manifest['status'] == 'passed' and manifest['validated_archives'] == 94
    assert manifest['decision_id'] == 'MILI-D-20261010-015'
    records, audits, schemas, metadata_mismatches = [], [], Counter(), []
    for archive_record in manifest['records']:
        path = ROOT/archive_record['path']
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == archive_record['sha256']
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            source_members = [n for n in archive.namelist() if n.lower().endswith(('.xml','.gml')) and 'meta' not in n.lower()]
            assert len(source_members) == 1, (path, source_members)
            member = source_members[0]
            root = ET.fromstring(archive.read(member))
        prefecture = re.search(r'_(\d{2})_GML\.zip$', path.name).group(1)
        for item in archive_record['metadata_date_inventory']:
            match = re.search(r'_(\d{2})\.xml$', item['member'])
            if match and match.group(1) != prefecture:
                metadata_mismatches.append(dict(archive=archive_record['path'], metadata_member=item['member'],
                                               handling='Preserve original; flag filename mismatch; do not rename or infer record absence'))
        points = {}
        for point in root.findall(GML+'Point'):
            point_id = point.attrib[GML+'id']
            assert point_id not in points
            position = point.findtext(GML+'pos').split()
            assert len(position) == 2
            latitude, longitude = map(float, position)
            assert 20 <= latitude <= 46 and 123 <= longitude <= 154
            points[point_id] = (latitude, longitude)
        features = root.findall(KSJ+'BusStop')
        ids = set()
        count_before = len(records)
        for feature in features:
            feature_id = feature.attrib[GML+'id']
            assert feature_id not in ids; ids.add(feature_id)
            for node in feature.iter(): schemas[(archive_record['code'], node.tag)] += 1
            location = feature.find(KSJ+'loc').attrib[XLINK+'href']
            assert location.startswith('#') and location[1:] in points
            latitude, longitude = points[location[1:]]
            routes = [source_structure(route) for route in feature.findall(KSJ+'bri')]
            row = dict(source_code=archive_record['code'], source_year=archive_record['year'],
                       source_prefecture_archive=prefecture, source_archive=archive_record['path'],
                       source_member=member, source_feature_id=feature_id, source_point_id=location[1:],
                       latitude=latitude, longitude=longitude, bsn=feature.findtext(KSJ+'bsn'),
                       boc=feature.findtext(KSJ+'boc'), rmk=feature.findtext(KSJ+'rmk'),
                       bri_json=json.dumps(routes, ensure_ascii=False),
                       source_attributes_json=json.dumps(source_structure(feature), ensure_ascii=False))
            row.update(screen(row['bsn']))
            records.append(row)
        assert len(records)-count_before == len(features)
        audits.append(dict(source_code=archive_record['code'], source_year=archive_record['year'],
                           source_prefecture_archive=prefecture, source_archive=archive_record['path'],
                           stop_records=len(features), coordinate_points=len(points),
                           sha256_passed=True, crc_passed=True, all_feature_locations_resolved=True))
    frame = pd.DataFrame(records)
    assert not frame.duplicated(['source_archive','source_member','source_feature_id']).any()
    assert frame[['latitude','longitude']].notna().all().all()
    for code in ['P11','P36']:
        coverage=[r['source_prefecture_archive'] for r in audits if r['source_code']==code]
        assert len(coverage)==47 and set(coverage)=={f'{n:02d}' for n in range(1,48)}
    candidates = frame.loc[frame.name_based_terminal_candidate].copy()
    # Mark exact repetitions only. Do not merge differently named or nearby records.
    candidates['exact_name_coordinate_repeat_count'] = candidates.groupby(['bsn','latitude','longitude'], dropna=False)['bsn'].transform('size')
    candidates['requires_facility_identity_review'] = True
    candidates['review_priority'] = 'terminal_candidate'
    candidates.loc[candidates.abbreviation_name_flag, 'review_priority'] = 'abbreviation_needs_review'
    candidates.loc[candidates.peripheral_stop_name_flag, 'review_priority'] = 'peripheral_stop_needs_review'
    candidates.loc[candidates.air_related_name_flag | candidates.port_related_name_flag, 'review_priority'] = 'air_or_port_name_needs_review'
    candidates.loc[candidates.freight_related_name_flag, 'review_priority'] = 'freight_name_needs_review'
    frame.to_parquet(OUT/'all_bus_stop_source_inventory.parquet', index=False)
    candidates.to_parquet(OUT/'terminal_candidate_stop_records.parquet', index=False)
    candidates.to_csv(OUT/'terminal_candidate_stop_records.csv', index=False)
    pd.DataFrame(audits).to_csv(OUT/'archive_coverage_audit.csv', index=False)
    schema_rows=[dict(source_code=code,source_gml_tag=tag,occurrences=count) for (code,tag),count in sorted(schemas.items())]
    (OUT/'source_schema_inventory.json').write_text(json.dumps(schema_rows, ensure_ascii=False, indent=2)+'\n')
    counts=frame.groupby(['source_code','source_year','source_prefecture_archive']).agg(
        stop_records=('source_feature_id','size'),name_candidate_records=('name_based_terminal_candidate','sum')).reset_index()
    counts.to_csv(OUT/'prefecture_screening_summary.csv', index=False)
    summary=[]
    for code in ['P11','P36']:
        all_rows=frame.loc[frame.source_code==code]; selected=candidates.loc[candidates.source_code==code]
        summary.append(dict(source_code=code,source_year=int(all_rows.source_year.iloc[0]),
                            prefectural_archives=47,stop_records=len(all_rows),name_candidate_records=len(selected),
                            peripheral_name_flag_records=int(selected.peripheral_stop_name_flag.sum()),
                            air_related_name_flag_records=int(selected.air_related_name_flag.sum()),
                            port_related_name_flag_records=int(selected.port_related_name_flag.sum()),
                            freight_related_name_flag_records=int(selected.freight_related_name_flag.sum()),
                            abbreviation_name_flag_records=int(selected.abbreviation_name_flag.sum()),
                            exact_name_coordinate_groups=len(selected.groupby(['bsn','latitude','longitude'])),
                            exact_repeat_flag_records=int((selected.exact_name_coordinate_repeat_count>1).sum())))
    pd.DataFrame(summary).to_csv(OUT/'screening_summary.csv', index=False)
    report=dict(status='passed',decision_id='MILI-D-20261010-015',archives_verified=94,
                all_source_records=len(frame),candidate_stop_records=len(candidates),summary=summary,
                all_point_references_resolved=True,source_feature_keys_unique=True,source_attributes_preserved=True,
                metadata_filename_mismatches=metadata_mismatches,name_screening_only=True,
                route_names_not_used_as_terminal_location_evidence=True,
                no_source_records_dropped_from_full_inventory=True,facility_deduplication_performed=False,
                validated_terminal_facilities=None,national_terminal_coverage_complete='not established',
                temporal_alignment_to_2024='2022/2023 reference editions; not a verified 2024 operational snapshot',
                model_variables_constructed=False,regression_changed=False)
    omission_path=ROOT/'data/raw/poi/p11/2022/auxiliary/P11-v3_0.xlsx'
    if omission_path.exists():
        omissions=pd.read_excel(omission_path,engine='openpyxl',dtype=str)
        omissions['name_based_terminal_candidate']=omissions['バス停留所の名称'].map(lambda n:screen(n)['name_based_terminal_candidate'])
        omissions.to_csv(OUT/'unlocated_stop_screening.csv',index=False)
        report['official_unlocated_stop_list']=dict(source_records=len(omissions),
            name_candidate_records=int(omissions.name_based_terminal_candidate.sum()),
            included_in_geolocated_inventory=False,coordinates_imputed=False)
    (OUT/'screening_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='metadata_filename_mismatches'},ensure_ascii=False,indent=2))
    print('Metadata filename mismatches:', len(metadata_mismatches))


if __name__=='__main__': main()
