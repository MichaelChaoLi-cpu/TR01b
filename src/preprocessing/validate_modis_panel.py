"""Validate readable annual outputs, mesh-period uniqueness, coverage and preservation."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from prepare_modis_meshes import GROUPS, OUT, ROOT


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    decisions = json.loads((OUT / 'decisions.json').read_text())
    contract = json.loads((OUT / 'proposed_construction.json').read_text())
    assert contract['confirmed'] and decisions['confirmed']
    assert {label: classes for label, classes in GROUPS.values()} == contract['proposed_groups']
    classes = [c for _, group in GROUPS.values() for c in group]
    assert sorted(classes) == list(range(1, 18))
    raw = json.loads((OUT / 'download_manifest.json').read_text())['records']
    raw += json.loads((OUT / 'metadata_manifest.json').read_text())['records']
    for record in raw:
        assert sha(ROOT / record['path']) == record['sha256']
    for source, spec in decisions['datasets'].items():
        original = pd.read_parquet(ROOT / source)
        rename = {v['original_name']: v['readable_name'] for v in spec['variables']}
        expected = original[list(rename)].rename(columns=rename)
        result = pd.read_parquet(ROOT / spec['output'])
        pd.testing.assert_frame_equal(expected, result)
        assert not result.duplicated(['Mesh Code', 'Land Cover Year']).any()
    shares = [label for label, _ in GROUPS.values()]
    linkage = json.loads((OUT / 'panel_linkage_validation.json').read_text())
    assert linkage['status'] == 'passed'
    records = []
    for spec in linkage['outputs']:
        path = ROOT / spec['output']
        assert sha(path) == spec['output_sha256']
        assert sha(ROOT / spec['source']) == spec['source_sha256']
        per_year = {y: dict(rows=0, no_valid_coverage=0, partial_valid_coverage=0,
                           complete_valid_coverage=0, source_coverage_incomplete=0,
                           genuine_population_zeros=0) for y in contract['years']}
        keys = []; missing_meshes = set(); incomplete_meshes = set()
        maximum_partition_error = 0.
        columns = ['Mesh Code', 'Road Year', 'Land Cover Year', 'Population'] + shares + [
            'Land Cover Coverage', 'Land Cover Source Coverage', 'Land Cover Unclassified Share',
            'Land Cover No Data Share', 'Land Cover Adjusted Share',
            'Land Cover Incomplete Coverage', 'Land Cover No Valid Pixels', 'Land Cover Mesh Area']
        for batch in pq.ParquetFile(path).iter_batches(batch_size=65536, columns=columns):
            frame = batch.to_pandas()
            year = frame['Road Year'].to_numpy()
            assert np.array_equal(year, frame['Land Cover Year'])
            coverage = frame['Land Cover Coverage'].to_numpy()
            source = frame['Land Cover Source Coverage'].to_numpy()
            no_valid = frame['Land Cover No Valid Pixels'].to_numpy()
            partial = frame['Land Cover Incomplete Coverage'].to_numpy()
            values = frame[shares].to_numpy()
            assert np.array_equal(np.isnan(values).all(axis=1), no_valid)
            assert np.array_equal(np.isnan(values).any(axis=1), no_valid)
            assert np.array_equal(no_valid, coverage <= 1e-12)
            assert np.array_equal(partial, coverage < 1 - 1e-9)
            assert np.isfinite(values[~no_valid]).all()
            observed_values = values[~no_valid]
            assert observed_values.min(initial=0) >= -1e-9
            assert observed_values.max(initial=0) <= 1 + 1e-9
            difference = np.abs(values[~no_valid].sum(axis=1) - coverage[~no_valid])
            maximum_partition_error = max(maximum_partition_error, difference.max(initial=0))
            assert maximum_partition_error < 1e-9
            unclassified = frame['Land Cover Unclassified Share'].to_numpy()
            nodata = frame['Land Cover No Data Share'].to_numpy()
            assert np.max(np.abs(coverage + unclassified + nodata - 1)) < 1e-9
            assert (coverage <= source + 1e-9).all()
            assert (frame['Land Cover Adjusted Share'] <= coverage + 1e-9).all()
            assert (frame['Land Cover Mesh Area'] > 0).all()
            mesh_codes = frame['Mesh Code'].to_numpy()
            keys.append(mesh_codes.astype(np.int64) * 10000 + year)
            missing_meshes.update(mesh_codes[no_valid].tolist())
            incomplete_meshes.update(mesh_codes[partial].tolist())
            for y in np.unique(year):
                use = year == y; record = per_year[int(y)]
                record['rows'] += int(use.sum())
                record['no_valid_coverage'] += int((use & no_valid).sum())
                record['partial_valid_coverage'] += int((use & partial & ~no_valid).sum())
                record['complete_valid_coverage'] += int((use & ~partial).sum())
                record['source_coverage_incomplete'] += int((use & (source < 1 - 1e-9)).sum())
                record['genuine_population_zeros'] += int((use & frame['Population'].eq(0).to_numpy()).sum())
        keys = np.sort(np.concatenate(keys))
        assert len(keys) == spec['rows'] and not (keys[1:] == keys[:-1]).any()
        assert all(record['rows'] == spec['rows'] // 5 for record in per_year.values())
        records.append(dict(output=spec['output'], rows=spec['rows'], columns=spec['columns'],
                            unique_mesh_period_keys=len(keys), coverage_by_year=per_year,
                            meshes_without_valid_coverage_in_any_year=len(missing_meshes),
                            meshes_with_incomplete_coverage_in_any_year=len(incomplete_meshes),
                            maximum_share_partition_error=maximum_partition_error))
        print('Validated coverage and keys:', path.name, flush=True)
    reference = json.loads((OUT / 'preserved_analysis_reference.json').read_text())
    assert sha(ROOT / reference['path']) == reference['sha256']
    report = dict(status='passed', decision_id=decisions['decision_id'],
                  original_source_archives_verified=len(raw),
                  generated_annual_outputs_match_confirmed_inputs=True,
                  approved_class_groups_partition_igbp=True, all_original_panel_columns_preserved=True,
                  source_panel_checksums_preserved=True, original_local_coefficients_preserved=True,
                  rows_not_deleted=True, quality_profiles=records, regressions_refitted=False)
    (OUT / 'panel_quality_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('All MODIS panel quality checks passed.', flush=True)


if __name__ == '__main__':
    main()
