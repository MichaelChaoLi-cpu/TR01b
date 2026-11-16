"""Verify archived candidates and summarize source records without constructing variables."""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-augmentation-screening/mlit-facilities'


def main():
    manifest = json.loads((OUT/'facility_download_manifest.json').read_text())
    assert manifest['status'] == 'passed' and manifest['validated_archives'] == 189
    summary = defaultdict(lambda: dict(archives=0, source_records=0))
    for record in manifest['records']:
        path = ROOT/record['path']
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == record['sha256']
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
        tables = record['attribute_tables']
        if record['kind'] == 'airports':
            selected = [t for t in tables if t['member'].startswith('UTF-8/')]
            assert len(selected) == 4
            # Equivalent encoding copies are inventory alternatives, not new observations.
            for table in selected:
                alternate = next(t for t in tables if t['member'] == table['member'].replace('UTF-8/', 'Shift-JIS/'))
                assert table['records'] == alternate['records'] and table['fields'] == alternate['fields']
        else:
            assert len(tables) == 1, (record['name'], tables)
            selected = tables
        for table in selected:
            layer = table['member'].replace('\\', '/').split('/')[-1].removesuffix('.dbf')
            if record['kind'] != 'airports': layer = 'Facility'
            else: layer = layer.removeprefix('C28-21_')
            key = (record['kind'], record['code'], record['year'], record['reference'], layer, record['page'])
            summary[key]['archives'] += 1
            summary[key]['source_records'] += table['records']
    rows = [dict(zip(['category','source_code','edition_year','reference_date','layer','source_page'], key), **values)
            for key, values in sorted(summary.items())]
    with (OUT/'acquisition_summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    validation = dict(status='passed', decision_id='MILI-D-20261010-013',
                      archived_files_verified=189, sha256_verified=True, zip_crc_verified=True,
                      airport_encoding_copies_not_added=True,
                      counts_are_source_layer_records_not_deduplicated_facilities=True,
                      passenger_station_definition='pending human clarification',
                      scientific_variables_and_regression_terms='not selected')
    protected = {
        'data/processed/national/five_period/balanced_five_period_panel_preprocessed.parquet':
            '976e00422ad8fd6001ace071644a9535d8d24f19634408cb624d60abf54d26cc',
        'data/exp/gwpr-pooled-five-period-2024/mesh-map-3km/local_coefficients.parquet':
            'b0fa621c3567c96a893a0ab8a364a54cec1e17964e84a479b0b873900b8b79bf',
    }
    # Reference hashes are taken from the completed five-period rerun validation.
    validation['existing_analysis_hashes'] = {}
    for relative, expected in protected.items():
        with (ROOT/relative).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert actual == expected, (relative, actual, expected)
        validation['existing_analysis_hashes'][relative] = actual
    (OUT/'acquisition_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    print(json.dumps(dict(validation=validation, summary=rows), indent=2))


if __name__ == '__main__': main()
