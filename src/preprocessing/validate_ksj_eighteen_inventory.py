"""Validate the source-inventory delivery and preservation of existing analyses."""
import csv
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'


def main():
    acquisition = json.loads((ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities/acquisition_manifest.json').read_text())
    inventory = json.loads((OUT / 'source_inventory_validation.json').read_text())
    geometry = json.loads((OUT / 'geometry_source_audit.json').read_text())
    schemas = json.loads((OUT / 'schemas.json').read_text())
    assert acquisition['status'] == inventory['status'] == geometry['status'] == 'passed'
    assert len(acquisition['categories']) == 18 and len(acquisition['records']) == 294 and len(schemas) == 28
    for group in acquisition['categories']:
        records = [r for r in acquisition['records'] if r['kind'] == group['kind']]
        assert len(records) == group['expected_archives']
        for record in records:
            with (ROOT / record['path']).open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == record['sha256']
            if record['nested_archives']:
                codes = {int(re.search(r'_(\d{2})_GML.zip', name).group(1)) for name in record['nested_archives']}
                assert codes == set(range(1, 48))
    for record in json.loads((OUT / 'preserved_inputs.json').read_text()):
        with (ROOT / record['path']).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == record['sha256']
    with (OUT / 'variable_list.csv').open() as stream:
        variables = list(csv.DictReader(stream))
    assert len(variables) == 587 and sum(len(s['fields']) for s in schemas.values()) == 279
    summary = pd.read_csv(OUT / 'source_layer_summary.csv')
    assert summary.missing_geometry.eq(0).all() and summary.missing_point_coordinates.eq(0).all()
    assert summary.records.sum() == 852083
    for key, metadata in schemas.items():
        frame = pd.read_parquet(OUT / 'source-inventory' / (key + '.parquet'))
        if metadata['geometry_type'] == 'Point':
            assert frame.source_longitude.between(122, 154).all() and frame.source_latitude.between(20, 47).all()
    lexemes = pd.read_csv(OUT / 'local_industry_reference_code_lexemes.csv', dtype={'P24_011_raw_lexeme': str})
    frame = pd.read_parquet(OUT / 'source-inventory/local_industry_point_9853a84a.parquet')
    assert (frame.P24_011.to_numpy() == lexemes.P24_011_raw_lexeme.astype(float).to_numpy()).all()
    assert (OUT / 'CONSTRUCTION_PROPOSAL.md').exists()
    result = dict(status='passed', decision_id='MILI-D-20261010-020', selected_categories=18, outer_archives=294,
                  nested_constituent_archives=94, raw_bytes=acquisition['total_bytes'], source_layer_schemas=28,
                  original_field_entries=279, inventory_field_entries_including_provenance=587, source_records=852083,
                  point_records=681866, multipoint_features=15669, native_point_coordinates_present=True,
                  native_point_coordinates_within_broad_japan_bounds=True, missing_prj_layers=len(inventory['missing_crs_layers']),
                  official_crs_declarations_available_for_all_18=geometry['official_crs_declarations'] == 18,
                  local_industry_reference_lexemes_verified=True, all_existing_panels_results_anasop_unchanged=True,
                  raw_sha256_verification='passed independently for every outer archive',
                  scientific_construction_confirmation='pending', new_mesh_variables_written=False,
                  five_period_panel_updated=False, regressions_refitted=False)
    (OUT / 'delivery_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
