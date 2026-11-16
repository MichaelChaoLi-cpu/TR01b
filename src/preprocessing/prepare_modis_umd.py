"""Reconstruct approved UMD shares on the existing native mesh intersections.

Reproduce in order: mosaic, prepare, annual, panels, finalize.
No original archives, IGBP outputs, estimates or figures are overwritten.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from inspect_modis_land_cover import pixel_ids

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
OUT = ROOT / 'data/exp/data-preprocessing/modis-umd'
DEST = ROOT / 'data/processed/national/modis_umd'
YEARS = [2002, 2003, 2004, 2010, 2024]
DECISION = 'MILI-D-20261011-019'
GROUPS = {
    'Urban Land Cover Share': [13],
    'Forest Land Cover Share': [1, 2, 3, 4, 5],
    'Cropland Land Cover Share': [12],
    'Water Land Cover Share': [0],
    'Shrublands and Grasslands': [6, 7, 8, 9, 10],
    'Barren': [15],
}
OLD_SHARES = list(GROUPS)[:3] + ['Cropland Mosaic Land Cover Share',
                               'Water Land Cover Share', 'Other Land Cover Share']
POI = ['Distance to Railway Station', 'Distance to Passenger Airport',
       'School Facility Count', 'Medical Facility Count', 'Logistics Facility Count',
       'Visitor and Event Facility Count']
POI_YEARS = ['School Facility Source Year', 'Medical Facility Source Year',
             'Logistics Facility Source Year', 'Visitor and Event Facility Source Year',
             'Railway Source Year', 'Airport Source Year']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def load_archive(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def mosaic():
    manifest = json.loads((OUT / 'download_manifest.json').read_text())
    assert manifest['finished_requests'] == manifest['planned_requests'] == 267
    assert all(r['status'] == 'downloaded' for r in manifest['records'])
    old_manifest = json.loads((SOURCE / 'download_manifest.json').read_text())
    qc_records = {(r['block'], tuple(r['years'])): r for r in old_manifest['records'] if r['band'] == 'QC'}
    catalogue = {}
    for year in YEARS:
        path = ROOT / f'data/raw/land_cover/modis/mcd12q1_061/metadata/lads_catalogue_{year}.html.gz'
        catalogue[year] = set(re.findall(r'MCD12Q1\.A\d{7}\.h\d{2}v\d{2}\.061\.\d+\.hdf',
                                       gzip.decompress(path.read_bytes()).decode()))
    identifiers = np.load(SOURCE / 'native_pixel_ids.npy')
    arrays = np.full((len(YEARS), len(identifiers)), 256, dtype=np.uint16)
    duplicates = version_checks = 0
    for j, record in enumerate(manifest['records']):
        path = ROOT / record['path']
        assert sha(path) == record['sha256']
        value = load_archive(path)
        qc_record = qc_records[(record['block'], tuple(record['years']))]
        assert sha(ROOT / qc_record['path']) == qc_record['sha256']
        qc_granules = {g['calendar_date']: (g['modis_date'], g['tile'], g['proc_date'])
                       for g in qc_record['granules']}
        # LC_Type2 and QC must use precisely the same window and processing edition.
        assert all(str(record[k]) == str(qc_record[k]) for k in
                   ['xllcorner', 'yllcorner', 'nrows', 'ncols', 'cellsize'])
        ids = pixel_ids(value)
        positions = np.searchsorted(identifiers, ids)
        use = positions < len(identifiers)
        use[use] &= identifiers[positions[use]] == ids[use]
        positions = positions[use]
        for subset in value['subset']:
            assert subset['band'] == 'LC_Type2'
            year = int(subset['calendar_date'][:4])
            edition = (subset['modis_date'], subset['tile'], subset['proc_date'])
            assert edition == qc_granules[subset['calendar_date']]
            granule = f'MCD12Q1.{edition[0]}.{edition[1]}.061.{edition[2]}.hdf'
            assert granule in catalogue[year]
            version_checks += 1
            values = np.asarray(subset['data'], dtype=np.uint16)
            assert (values <= 255).all()
            values = values[use]
            target = arrays[YEARS.index(year)]
            previous = target[positions]
            shared = previous != 256
            assert np.array_equal(previous[shared], values[shared])
            duplicates += int(shared.sum())
            target[positions] = values
        if (j + 1) % 60 == 0:
            print('UMD mosaic', j + 1, '/', len(manifest['records']), flush=True)
    reports = []
    for i, year in enumerate(YEARS):
        original = np.load(SOURCE / f'native_pixels_{year}.npz')
        assert np.array_equal(arrays[i] != 256, original['response_pixel_present'])
        available = original['published_tile'] & original['response_pixel_present']
        labels = np.unique(arrays[i][available]).tolist()
        assert set(labels).issubset(set(sum(GROUPS.values(), [])) | {255})
        np.savez_compressed(OUT / f'native_pixels_{year}.npz', LC_Type2=arrays[i], QC=original['QC'],
                            published_tile=original['published_tile'],
                            response_pixel_present=original['response_pixel_present'])
        reports.append(dict(year=year, native_pixels=len(identifiers),
                            source_pixels_present=int(available.sum()), source_class_values=labels,
                            unresolved_land_barren_pixels=int((available & (original['QC'] == 1) &
                                                              (arrays[i] == 15)).sum())))
    independent = 0
    for path in sorted((ROOT / 'data/raw/land_cover/modis/mcd12q1_061/metadata').glob('probe_*_2024_all_bands.json.gz')):
        value = load_archive(path)
        ids = pixel_ids(value); positions = np.searchsorted(identifiers, ids)
        use = positions < len(identifiers)
        use[use] &= identifiers[positions[use]] == ids[use]
        for subset in value['subset']:
            if subset['band'] == 'LC_Type2':
                assert np.array_equal(np.asarray(subset['data'])[use], arrays[-1, positions[use]])
                independent += int(use.sum())
    dump(OUT / 'source_mosaic_validation.json', dict(status='passed', years=reports,
        requests=267, native_pixel_count=len(identifiers), exact_qc_processing_edition_checks=version_checks,
        duplicate_pixel_values_verified=duplicates, independent_probe_pixels_verified=independent,
        quality_and_source_availability_reused_exactly=True, archive_checksums_verified=True))
    print('UMD source mosaic validated:', version_checks, 'granules;', independent, 'independent pixels', flush=True)


def prepare():
    assert json.loads((OUT / 'source_mosaic_validation.json').read_text())['status'] == 'passed'
    assert json.loads((SOURCE / 'independent_geometry_validation.json').read_text())['status'] == 'passed'
    assert json.loads((SOURCE / 'overlap-weights/validation.json').read_text())['status'] == 'passed'
    DEST.mkdir(parents=True, exist_ok=True)
    (OUT / 'confirmed-inputs').mkdir(exist_ok=True)
    pointer = json.loads((OUT.parent / 'active_panel.json').read_text())
    protected = {pointer[k]: sha(ROOT / pointer[k]) for k in
                 ['full_panel', 'core_balanced_panel', 'active_baseline_panel']}
    formal = 'data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet'
    protected[formal] = sha(ROOT / formal)
    backup = OUT / 'AnaSOP_before_umd.txt'
    if not backup.exists():
        backup.write_bytes((ROOT / 'docs/AnaSOP.md').read_bytes())
    coordinates = np.load(SOURCE / 'mesh_coordinates.npz')
    codes = coordinates['codes']; n = len(codes)
    ids = np.load(SOURCE / 'native_pixel_ids.npy')
    weights = sorted((SOURCE / 'overlap-weights').glob('*.npz'))
    protected.update({str(p.relative_to(ROOT)): sha(p) for p in weights})
    datasets, audits, summaries, inventory = {}, [], [], []
    for year in YEARS:
        pixels = np.load(OUT / f'native_pixels_{year}.npz')
        lc, qc = pixels['LC_Type2'], pixels['QC']
        present = pixels['published_tile'] & pixels['response_pixel_present']
        mask_water = present & (qc == 3) & (lc == 0)
        valid = present & np.isin(lc, sum(GROUPS.values(), [])) & (
            np.isin(qc, [0, 2, 4, 5, 6, 7, 8, 9]) | mask_water)
        unclassified = present & np.isin(qc, [1, 3])
        adjusted = valid & np.isin(qc, [4, 5, 6, 7, 8, 9])
        reference_masks = {'Land Cover Source Coverage': present, 'Land Cover Coverage': valid,
            'Land Cover Unclassified Share': unclassified, 'Land Cover Adjusted Share': adjusted,
            'Land Cover Mask Identified Water Share': mask_water}
        result = {name: np.zeros(n) for name in list(GROUPS) + list(reference_masks) + ['Land Cover Mesh Area']}
        for path in weights:
            with np.load(path) as w:
                start, end = int(w['start']), int(w['end'])
                pid = (w['row'].astype(np.int64) * 86400 + w['column']).astype(np.uint32)
                pos = np.searchsorted(ids, pid)
                assert np.array_equal(ids[pos], pid)
                local, fraction = w['mesh'] - start, w['weight']
                def aggregate(mask):
                    return np.bincount(local, weights=fraction * mask, minlength=end-start)
                for name, classes in GROUPS.items():
                    result[name][start:end] = aggregate(valid[pos] & np.isin(lc[pos], classes))
                for name, mask in reference_masks.items():
                    result[name][start:end] = aggregate(mask[pos])
                result['Land Cover Mesh Area'][start:end] = w['mesh_area_km2']
        total = sum(result[name] for name in GROUPS)
        error = float(np.max(np.abs(total - result['Land Cover Coverage'])))
        assert error < 1e-9
        assert (total <= result['Land Cover Source Coverage'] + 1e-9).all()
        # QC3 water belongs both to classified coverage and the original QC marker.
        result['Land Cover No Data Share'] = (1 - total - result['Land Cover Unclassified Share'] +
                                            result['Land Cover Mask Identified Water Share'])
        for name in reference_masks.keys() | {'Land Cover No Data Share'}:
            assert result[name].min() >= -1e-9 and result[name].max() <= 1+1e-9
            result[name] = np.clip(result[name], 0, 1)  # Floating-point roundoff only.
        missing = result['Land Cover Coverage'] <= 1e-12
        result['Land Cover No Valid Pixels'] = missing
        result['Land Cover Incomplete Coverage'] = result['Land Cover Coverage'] < 1-1e-9
        for name in GROUPS:
            assert result[name].min() >= 0 and result[name].max() <= 1+1e-9
            result[name][missing] = np.nan
        frame = pd.DataFrame(result)
        frame.insert(0, 'Land Cover Year', np.int64(year))
        frame.insert(0, 'Mesh Code', codes)
        frame['Land Cover Product'] = 'MCD12Q1 Collection 6.1 UMD'
        path = OUT / f'confirmed-inputs/modis_umd_{year}_mesh.parquet'
        frame.to_parquet(path, index=False, compression='zstd')
        datasets[str(path.relative_to(ROOT))] = dict(
            output=f'data/processed/national/modis_umd/modis_umd_land_cover_{year}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_modis_umd_{year}.py', variables=[
                dict(original_name=c, readable_name=c, full_name=c,
                     is_final_variable='yes' if c in GROUPS else 'no', preprocessing=[]) for c in frame])
        audits.append(dict(year=year, rows=n, columns=len(frame.columns),
            no_valid_coverage_meshes=int(missing.sum()),
            partial_coverage_meshes=int(((total > 1e-12) & (total < 1-1e-9)).sum()),
            source_coverage_incomplete_meshes=int((result['Land Cover Source Coverage'] < 1-1e-9).sum()),
            share_partition_maximum_error=error,
            accepted_barren_native_pixels=int((valid & (lc == 15)).sum()),
            excluded_qc1_barren_native_pixels=int((present & (qc == 1) & (lc == 15)).sum())))
        for name in GROUPS:
            series = frame[name]
            summaries.append(dict(year=year, variable=name, missing=int(series.isna().sum()),
                positive_meshes=int((series > 1e-12).sum()), minimum=float(series.min()),
                maximum=float(series.max()), mean=float(series.mean()),
                observed_intersection_area_km2=float(np.nansum(series * frame['Land Cover Mesh Area']))))
        for name in ['LC_Type2', 'QC']:
            series = pixels[name][present]
            inventory.append(dict(source_dataset=str((OUT / f'native_pixels_{year}.npz').relative_to(ROOT)),
                original_name=name, dtype=str(series.dtype), non_null_count=int((series != 255).sum()),
                null_pct=float((series == 255).mean() * 100), sample_values=', '.join(map(str, np.unique(series))),
                feasibility_status='testable', readable_name='Land Cover Source Class' if name == 'LC_Type2' else 'Land Cover Source Quality',
                full_name='UMD Land Cover Source Class' if name == 'LC_Type2' else 'MODIS Land Cover Source Quality',
                is_final_variable='no'))
        print('UMD mesh construction', json.dumps(audits[-1]), flush=True)
    dump(OUT / 'decisions.json', dict(confirmed=True, decision_id=DECISION, years=YEARS,
        classification='MCD12Q1 Collection 6.1 UMD', source_band='LC_Type2', class_groups=GROUPS,
        datasets=datasets, previous_active_panel=pointer, protected_inputs=protected,
        quality_rule='QC0,2,4-9 and QC3 water accepted; QC1 unresolved land excluded.',
        denominator='Full projected mesh area, without coverage normalization.',
        annual_audit=audits, analytical_roles='Candidate controls; regression reference not yet selected.',
        regressions_refitted=False))
    dump(OUT / 'mesh_construction_validation.json', dict(status='passed', years=audits,
        group_count=6, mesh_count=n, row_deletion=False, missing_shares_are_nan=True,
        water_class_zero_preserved=True, unresolved_land_not_counted_as_barren=True))
    pd.DataFrame(summaries).to_csv(OUT / 'mesh_variable_summary.csv', index=False)
    spec = importlib.util.spec_from_file_location('discovery',
        ROOT / '.codex/skills/data-preprocessing/scripts/prepare_variable_list.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.write_variable_list(OUT, inventory)
    module.write_readme(OUT, {r['source_dataset']: [v for v in inventory if v['source_dataset'] == r['source_dataset']]
                             for r in inventory}, [])


def annual():
    subprocess.run([sys.executable, str(ROOT / '.codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py'),
                    '--root', str(ROOT), '--decisions', str(OUT / 'decisions.json'), '--pretty'], check=True)
    decisions = json.loads((OUT / 'decisions.json').read_text())
    tables = []
    for source, spec in decisions['datasets'].items():
        subprocess.run([sys.executable, str(ROOT / spec['script'])], check=True)
        pd.testing.assert_frame_equal(pd.read_parquet(ROOT / source), pd.read_parquet(ROOT / spec['output']))
        tables.append(pq.read_table(ROOT / spec['output']))
    pq.write_table(pa.concat_tables(tables), DEST / 'modis_umd_land_cover_mesh_preprocessed.parquet', compression='zstd')
    print('Five annual UMD preprocessing outputs verified.', flush=True)


def panels():
    decisions = json.loads((OUT / 'decisions.json').read_text())
    annual = [pq.read_table(ROOT / s['output']) for s in decisions['datasets'].values()]
    modis = pa.concat_tables(annual)
    index = pd.Index(annual[0].column('Mesh Code').to_pylist())
    assert index.is_unique
    appended = [n for n in modis.column_names if n != 'Mesh Code']
    def matched(table):
        pos = index.get_indexer(table.column('Mesh Code').to_pylist())
        year = table.column('Road Year').to_numpy()
        assert (pos >= 0).all() and np.isin(year, YEARS).all()
        y = np.searchsorted(np.asarray(YEARS), year)
        result = modis.take(pa.array(pos + len(index) * y))
        assert result.column('Mesh Code').equals(table.column('Mesh Code'))
        assert np.array_equal(result.column('Land Cover Year').to_numpy(), year)
        return result
    outputs = []
    extra = ['Road Length', 'Mesh Area', 'Road Density Originally Missing', 'Road Density Source Status']
    selected_source = None
    baseline = pd.read_parquet(ROOT / decisions['previous_active_panel']['active_baseline_panel'])
    baseline_codes = set(baseline['Mesh Code'])
    candidate_parts = []
    for key in ['full_panel', 'core_balanced_panel']:
        source_path = ROOT / decisions['previous_active_panel'][key]
        source = pq.ParquetFile(source_path)
        retained = [n for n in source.schema_arrow.names if n not in OLD_SHARES and n not in appended]
        output = DEST / source_path.name
        pending = output.with_suffix('.pending.parquet')
        writer = None; count = 0; missing = 0
        try:
            for batch in source.iter_batches(batch_size=65536):
                original = pa.Table.from_batches([batch]); cover = matched(original)
                # The source pandas metadata describes IGBP column names. Drop
                # that stale schema-level metadata after changing the column set.
                result = original.select(retained).replace_schema_metadata(None)
                for name in appended:
                    result = result.append_column(name, cover.column(name))
                if writer is None:
                    writer = pq.ParquetWriter(pending, result.schema, compression='zstd')
                writer.write_table(result)
                count += len(result)
                missing += int(cover.column('Land Cover No Valid Pixels').to_numpy().sum())
                if count % (65536 * 16) == 0:
                    print('UMD panel writing', key, count, '/', source.metadata.num_rows, flush=True)
                if key == 'full_panel':
                    use = np.fromiter((c in baseline_codes for c in original.column('Mesh Code').to_pylist()), dtype=bool)
                    selected = result.filter(pa.array(use)).select(['Mesh Code', 'Road Year'] + POI + POI_YEARS + extra + appended)
                    candidate_parts.append(selected)
        finally:
            if writer is not None:
                writer.close()
        reader = pq.ParquetFile(pending)
        assert count == source.metadata.num_rows == reader.metadata.num_rows
        verified = 0
        for a, b in zip(source.iter_batches(batch_size=65536), reader.iter_batches(batch_size=65536), strict=True):
            a, b = pa.Table.from_batches([a]), pa.Table.from_batches([b])
            assert a.select(retained).equals(b.select(retained), check_metadata=False)
            assert matched(a).select(appended).equals(b.select(appended), check_metadata=False)
            verified += len(b)
        assert verified == count
        assert sha(source_path) == decisions['protected_inputs'][str(source_path.relative_to(ROOT))]
        pending.replace(output)
        outputs.append(dict(dataset=key, path=str(output.relative_to(ROOT)), rows=count,
            columns=len(reader.schema_arrow), missing_land_cover_records=missing,
            all_unrelated_columns_preserved_exactly=True, row_order_and_keys_preserved=True, sha256=sha(output)))
        print('UMD linked and verified', key, count, 'rows;', missing, 'missing land-cover records', flush=True)
    selected_source = pa.concat_tables(candidate_parts).to_pandas()
    assert len(selected_source) == len(baseline)
    assert not selected_source.duplicated(['Mesh Code', 'Road Year']).any()
    candidate = baseline.merge(selected_source, on=['Mesh Code', 'Road Year'], how='left',
                               validate='one_to_one', sort=False)
    pd.testing.assert_frame_equal(candidate[baseline.columns], baseline)
    assert not candidate['Land Cover Year'].isna().any()
    assert np.array_equal(candidate['Land Cover Year'], candidate['Road Year'])
    candidate_path = DEST / 'association_candidate_panel_preprocessed.parquet'
    candidate.to_parquet(candidate_path, index=False, compression='zstd')
    pd.testing.assert_frame_equal(pd.read_parquet(candidate_path), candidate)
    by_year = []
    details = []
    for year in YEARS:
        frame = candidate.loc[candidate['Road Year'] == year]
        by_year.append(dict(year=year, meshes=len(frame), missing=int(frame['Land Cover No Valid Pixels'].sum()),
            partial=int((frame['Land Cover Incomplete Coverage'] & ~frame['Land Cover No Valid Pixels']).sum())))
        for prefecture in ['Tokyo', 'Nara']:
            subset = frame.loc[frame['Prefecture'] == prefecture]
            assert len(subset) > 0
            for name in GROUPS:
                values = subset[name]
                details.append(dict(prefecture=prefecture, year=year, variable=name, meshes=len(subset),
                    missing=int(values.isna().sum()), positive_meshes=int((values > 1e-12).sum()),
                    minimum=float(values.min()), maximum=float(values.max()), mean=float(values.mean()),
                    constant=bool(values.dropna().nunique() <= 1)))
    pd.DataFrame(details).to_csv(OUT / 'tokyo_nara_variable_check.csv', index=False)
    cohort_summaries = []
    for year, frame in candidate.groupby('Road Year', sort=True):
        land_area = ((frame['Land Cover Coverage'] - frame['Water Land Cover Share']) *
                     frame['Land Cover Mesh Area']).sum()
        for name in GROUPS:
            values = frame[name]
            area = (values * frame['Land Cover Mesh Area']).sum()
            cohort_summaries.append(dict(year=int(year), variable=name, observations=len(frame),
                missing=int(values.isna().sum()), positive_meshes=int((values > 1e-12).sum()),
                minimum=float(values.min()), maximum=float(values.max()), mean=float(values.mean()),
                observed_area_km2=float(area), fraction_of_valid_classified_land_area=float(area/land_area)
                    if name != 'Water Land Cover Share' and land_area else None))
    pd.DataFrame(cohort_summaries).to_csv(OUT / 'analysis_cohort_variable_summary.csv', index=False)
    unavailable = candidate.loc[candidate['Land Cover No Valid Pixels'], ['Mesh Code', 'Road Year', 'Prefecture',
        'Land Cover Source Coverage', 'Land Cover Unclassified Share', 'Land Cover No Data Share']]
    unavailable.to_csv(OUT / 'analysis_cohort_missing_land_cover.csv', index=False)
    complete_by_mesh = ~candidate.groupby('Mesh Code')['Land Cover No Valid Pixels'].any()
    outputs.append(dict(dataset='association_candidate_panel', path=str(candidate_path.relative_to(ROOT)),
        rows=len(candidate), columns=len(candidate.columns), meshes=len(baseline_codes),
        missing_land_cover_records=len(unavailable), five_period_land_cover_available_meshes=int(complete_by_mesh.sum()),
        baseline_columns_preserved_exactly=True, sha256=sha(candidate_path)))
    for path, digest in decisions['protected_inputs'].items():
        assert sha(ROOT / path) == digest
    dump(OUT / 'panel_validation.json', dict(status='passed', decision_id=DECISION, outputs=outputs,
        candidate_yearly=by_year, original_inputs_unchanged=True, original_models_unchanged=True,
        unselected_land_cover_missing_records_preserved=True, regressions_refitted=False))
    dump(OUT / 'active_panel.json', dict(decision_id=DECISION, classification=decisions['classification'],
        full_panel=outputs[0]['path'], core_balanced_panel=outputs[1]['path'],
        association_candidate_panel=outputs[2]['path'], classification_group_count=6,
        construction_ready=True, analysis_role_selection_pending=True, regressions_refitted=False,
        model_status='Existing estimates and figures use the earlier IGBP inputs.'))
    print('UMD candidate panel:', len(candidate), 'records;', len(unavailable), 'missing retained', flush=True)


def finalize():
    report = json.loads((OUT / 'panel_validation.json').read_text())
    assert report['status'] == 'passed'
    decisions = json.loads((OUT / 'decisions.json').read_text())
    # Extend the raw-band inventory with all selected, constructed annual fields.
    inventory = pd.read_csv(OUT / 'variable_list.csv', keep_default_na=False).to_dict('records')
    inventory = [r for r in inventory if str(r['source_dataset']).endswith('.npz')]
    for spec in decisions['datasets'].values():
        frame = pd.read_parquet(ROOT / spec['output'])
        for name in frame:
            values = frame[name]
            inventory.append(dict(source_dataset=spec['output'], original_name=name,
                dtype=str(values.dtype), non_null_count=int(values.notna().sum()),
                null_pct=float(values.isna().mean() * 100),
                sample_values=', '.join(map(str, values.dropna().head(3))), feasibility_status='testable',
                readable_name=name, full_name=name, is_final_variable='yes' if name in GROUPS else 'no'))
    spec = importlib.util.spec_from_file_location('discovery',
        ROOT / '.codex/skills/data-preprocessing/scripts/prepare_variable_list.py')
    discovery = importlib.util.module_from_spec(spec); spec.loader.exec_module(discovery)
    discovery.write_variable_list(OUT, inventory)
    discovery.write_readme(OUT, {r['source_dataset']: [v for v in inventory if v['source_dataset'] == r['source_dataset']]
                               for r in inventory}, [])
    text = (ROOT / 'docs/AnaSOP.md').read_text()
    previous = (OUT / 'AnaSOP_before_umd.txt').read_text()
    def split(value):
        start = re.search(r'^## 4\. ', value, re.M).start()
        end = re.search(r'^## 5\. ', value, re.M).start()
        return value[:start], value[start:end], value[end:]
    before, section, after = split(text)
    old_before, _, old_after = split(previous)
    assert before == old_before and after == old_after
    heading = '### Confirmed Candidate UMD Class Grouping'
    start = section.index(heading)
    assert not re.search(r'^### ', section[start+len(heading):], re.M)
    candidate = report['outputs'][2]
    addition = '''### Confirmed UMD Land-Cover Reconstruction

The user selects University of Maryland land cover to reconstruct the five-period land context. This classification is read from its own annual source labels; it is not a recoding of IGBP labels. Six area shares are retained:

| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |
|---|---|---|---|---|---|
| Urban Land Cover Share | Urban Land Cover Share | Candidate control; model role TBD | Urban intersection area / full projected mesh area | UMD class 13 | yes |
| Forest Land Cover Share | Forest Land Cover Share | Candidate control; model role TBD | Forest intersection area / full projected mesh area | UMD classes 1-5 | yes |
| Cropland Land Cover Share | Cropland Land Cover Share | Candidate control; model role TBD | Cropland intersection area / full projected mesh area | UMD class 12 | yes |
| Water Land Cover Share | Water Land Cover Share | Candidate control; model role TBD | Water intersection area / full projected mesh area | UMD class 0 | yes |
| Shrublands and Grasslands | Shrublands and Grasslands | Candidate control; model role TBD | Group intersection area / full projected mesh area | UMD classes 6-10; includes closed and open shrublands, woody savannas, savannas and grasslands | yes |
| Barren | Barren | Candidate control; model role TBD | Barren intersection area / full projected mesh area | UMD class 15; includes bare soil, sand, rock and permanent snow/ice | yes |

Shrublands and Grasslands and Barren are numerical area proportions despite their shorter confirmed names. Native pixel/mesh intersection weights and the complete mesh-area denominator are reused exactly. Annual matching uses 2002, 2003, 2004, 2010 and 2024. A six-share sum equals accepted coverage rather than being normalized to one when coverage is partial. Observed class absence is zero; all six shares are NaN when no accepted source pixels cover the mesh. Unavailable source area and unresolved land are not statistically filled.

Accept the source's classified and adjusted quality states, and retain mask-identified water. Exclude unclassified land even where its fallback source label is Barren. Land Cover Unclassified Share continues to record both unresolved land and mask-identified water, so it overlaps the accepted-water reference and is not a disjoint residual. Land Cover Mask Identified Water Share makes this overlap explicit. The genuine unavailable-data reference is the residual after accepted coverage and unresolved land. Native source edition, published-tile availability and independent probe checks pass.

'''
    addition += (f'The reconstructed full panel retains {report["outputs"][0]["rows"]:,} records and '
                 f'{report["outputs"][0]["columns"]} readable columns; the core-balanced panel retains '
                 f'{report["outputs"][1]["rows"]:,} records. All unrelated source columns and mesh-period keys '
                 'are preserved exactly. The baseline-eligible candidate panel retains '
                 f'{candidate["meshes"]:,} meshes and {candidate["rows"]:,} records, including '
                 f'{candidate["missing_land_cover_records"]:,} records without accepted land cover. '
                 'Missing records are retained for model selection rather than automatically removed.\n\n'
                 'This reconstruction supersedes the IGBP land-cover construction for the new UMD dataset. '
                 'Existing estimates, figure inputs and Sections 5-8 still document the earlier IGBP analysis. '
                 'Model roles, a reference category and the handling of geographically constant controls '
                 'require estimation-plan reconciliation before those outputs are recomputed. No regression '
                 'or figure is regenerated by this preprocessing step.\n\n')
    assert addition.isascii() and not re.search(r'data/|\.parquet|LC_Type', addition)
    updated = before + section[:start] + addition + after
    (ROOT / 'docs/AnaSOP.md').write_text(updated)
    check_before, _, check_after = split(updated)
    assert check_before == old_before and check_after == old_after
    report.update(anasop_section_4_updated=True, all_other_anasop_sections_unchanged=True,
                  new_anasop_text_english_ascii=True)
    # Migrate the data entry point, while explicitly retaining the identity of
    # completed estimates. Their saved execution contracts still point to IGBP.
    pointer = dict(decisions['previous_active_panel'])
    pointer.update(decision_id=DECISION,
        preceding_land_cover_decision_id=decisions['previous_active_panel']['decision_id'],
        full_panel=report['outputs'][0]['path'], core_balanced_panel=report['outputs'][1]['path'],
        active_umd_candidate_panel=candidate['path'],
        land_cover_classification=decisions['classification'],
        land_cover_rule='Six UMD full-mesh shares; preserve QC3 water and exclude unresolved QC1 land.',
        regression_refitted=False, completed_extended_model_classification='IGBP',
        umd_regression_refitted=False,
        land_cover_delivery='data/exp/data-preprocessing/modis-umd/delivery_validation.json')
    dump(OUT.parent / 'active_panel.json', pointer)
    report.update(global_data_pointer_updated=True, existing_model_pointers_preserved=True)
    dump(OUT / 'delivery_validation.json', report)
    dump(OUT / 'grouping_decisions.json', dict(decision_id=DECISION,
        classification=decisions['classification'], source_band='LC_Type2', confirmed_groups=GROUPS,
        status='construction_and_linkage_validated', regressions_refitted=False,
        model_reference_category_pending=True))
    with (OUT / 'README.md').open('a') as stream:
        stream.write('\n## Confirmed reconstruction\n\n' +
            f'Human decision: {DECISION}. Six groups: ' + ', '.join(GROUPS) + '.\n\n' +
            'UMD class 0 is valid water; QC1 unclassified land is excluded from Barren. QC3 water is retained. '
            'Shares use full native projected mesh area. Missing coverage is not normalized or imputed. '
            'All original IGBP archives, datasets, estimates and figures remain available.\n\n' +
            '| Group | UMD source codes |\n|---|---|\n' +
            ''.join(f'| {name} | {", ".join(map(str, classes))} |\n' for name, classes in GROUPS.items()) +
            '\n## Linked outputs\n\n' +
            ''.join(f'- {r["dataset"]}: {r["rows"]:,} rows, {r["columns"]} columns; '
                    f'{r["missing_land_cover_records"]:,} missing land-cover records; {r["path"]}.\n'
                    for r in report['outputs']) +
            '\nTokyo/Nara checks: tokyo_nara_variable_check.csv. Full mesh summaries: mesh_variable_summary.csv. '
            'Baseline-eligible summaries: analysis_cohort_variable_summary.csv. '
            'These are different mesh universes and their area totals should not be described as official Japanese land area.\n\n'
            'A UMD pointer is saved locally in active_panel.json, and the global full/core data pointer now '
            'selects these UMD datasets. Existing model and figure input pointers retain their IGBP identity '
            'pending estimation-plan reconciliation.\n\n'
            '## Reproduce\n\n```sh\npython3 src/preprocessing/acquire_modis_umd.py --workers 4\n' +
            ''.join(f'python3 src/preprocessing/prepare_modis_umd.py --stage {s}\n'
                    for s in ['mosaic', 'prepare', 'annual', 'panels', 'finalize']) +
            '```\n\nOfficial UMD and quality definitions: '
            'https://lpdaac.usgs.gov/documents/1409/MCD12_User_Guide_V61.pdf (Tables 4 and 11).\n')
    print('UMD preprocessing delivered; AnaSOP Section 4 updated; estimates remain awaiting reconciliation.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True, choices=['mosaic', 'prepare', 'annual', 'panels', 'finalize'])
    args = parser.parse_args()
    globals()[args.stage]()
