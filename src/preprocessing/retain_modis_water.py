"""Retain source IGBP water with QC=3, under MILI-D-20261010-023.

Reconstruct mask-identified water area using saved native pixel intersections.
Preserve QC provenance, all unrelated variables, keys and the core cohort.
Run stages in order: prepare, annual, panels, finalize.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prepare_modis_meshes import GROUPS

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
OUT = ROOT / 'data/exp/data-preprocessing/modis-water-retained'
DEST = ROOT / 'data/processed/national/modis_water_retained'
YEARS = [2002, 2003, 2004, 2010, 2024]
DECISION = 'MILI-D-20261010-023'
SHARES = [v[0] for v in GROUPS.values()]
CHANGED = SHARES + ['Land Cover Coverage', 'Land Cover No Valid Pixels', 'Land Cover Incomplete Coverage']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True); DEST.mkdir(parents=True, exist_ok=True)
    baseline = OUT / 'AnaSOP_before_water_retained.txt'
    if not baseline.exists():
        baseline.write_bytes((ROOT / 'docs/AnaSOP.md').read_bytes())
    pointer_path = OUT / 'previous_active_panel.json'
    if not pointer_path.exists():
        pointer_path.write_bytes((OUT.parent / 'active_panel.json').read_bytes())
    previous = json.loads(pointer_path.read_text())
    protected = {previous[k]: sha(ROOT / previous[k]) for k in ['full_panel', 'core_balanced_panel']}
    ids = np.load(SOURCE / 'native_pixel_ids.npy')
    coordinates = np.load(SOURCE / 'mesh_coordinates.npz')
    n = len(coordinates['codes'])
    datasets, audits = {}, []
    for year in YEARS:
        source_path = ROOT / f'data/processed/national/modis_land_cover/modis_land_cover_{year}_preprocessed.parquet'
        protected[str(source_path.relative_to(ROOT))] = sha(source_path)
        frame = pd.read_parquet(source_path)
        assert np.array_equal(frame['Mesh Code'], coordinates['codes'])
        pixels = np.load(SOURCE / f'native_pixels_{year}.npz')
        present = pixels['published_tile'] & pixels['response_pixel_present']
        qc3 = present & (pixels['QC'] == 3)
        assert (pixels['LC_Type1'][qc3] == 17).all()
        assert not (pixels['published_tile'] & ~pixels['response_pixel_present']).any()
        water = np.zeros(n)
        for weight_path in sorted((SOURCE / 'overlap-weights').glob('*.npz')):
            with np.load(weight_path) as w:
                start, end = int(w['start']), int(w['end'])
                pid = (w['row'].astype(np.int64) * 86400 + w['column']).astype(np.uint32)
                positions = np.searchsorted(ids, pid)
                assert np.array_equal(ids[positions], pid)
                water[start:end] = np.bincount(w['mesh'] - start,
                    weights=w['weight'] * qc3[positions], minlength=end-start)
        old_missing = frame['Land Cover No Valid Pixels'].to_numpy()
        coverage = np.clip(frame['Land Cover Coverage'].to_numpy() + water, 0, 1)
        missing = coverage <= 1e-12
        recovered = old_missing & ~missing
        for column in SHARES:
            values = frame[column].to_numpy().copy()
            values[recovered] = 0.
            if column == 'Water Land Cover Share':
                values[~missing] += water[~missing]
            values[missing] = np.nan
            frame[column] = values
        frame['Land Cover Coverage'] = coverage
        frame['Land Cover No Valid Pixels'] = missing
        frame['Land Cover Incomplete Coverage'] = coverage < 1 - 1e-9
        error = np.max(np.abs(frame.loc[~missing, SHARES].sum(axis=1).to_numpy() - coverage[~missing]))
        assert error < 1e-9
        assert np.max(coverage - frame['Land Cover Source Coverage'].to_numpy()) < 1e-9
        # Unclassified Share still records QC1+QC3, including accepted QC3 water.
        # Coverage and this QC marker now overlap; never add them as disjoint areas.
        residual_land = frame['Land Cover Unclassified Share'].to_numpy() - water
        partition = coverage + residual_land + frame['Land Cover No Data Share'].to_numpy()
        assert np.max(np.abs(partition - 1)) < 1e-9
        original = pd.read_parquet(source_path)
        unchanged = [c for c in frame if c not in CHANGED]
        pd.testing.assert_frame_equal(frame[unchanged], original[unchanged])
        for column in SHARES:
            if column != 'Water Land Cover Share':
                assert np.array_equal(frame.loc[~old_missing, column], original.loc[~old_missing, column])
        input_path = OUT / f'confirmed-inputs/modis_{year}_water_retained.parquet'
        input_path.parent.mkdir(exist_ok=True)
        frame.to_parquet(input_path, index=False, compression='zstd')
        np.savez_compressed(OUT / f'qc3_water_area_{year}.npz', share=water)
        datasets[str(input_path.relative_to(ROOT))] = dict(
            output=f'data/processed/national/modis_water_retained/modis_land_cover_{year}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_modis_water_retained_{year}.py',
            variables=[dict(original_name=c, readable_name=c, full_name=c,
                            is_final_variable='yes' if c in SHARES else 'no', preprocessing=[]) for c in frame])
        audits.append(dict(year=year, rows=n, missing_before=int(old_missing.sum()),
                           recovered_water_records=int(recovered.sum()), missing_after=int(missing.sum()),
                           partial_after=int(((coverage > 1e-12) & (coverage < 1-1e-9)).sum()),
                           complete_after=int((coverage >= 1-1e-9).sum()),
                           maximum_share_partition_error=float(error)))
        print(json.dumps(audits[-1]), flush=True)
    dump(OUT / 'decisions.json', dict(confirmed=True, decision_id=DECISION,
        supersedes_quality_component_of='MILI-D-20261010-019', years=YEARS, datasets=datasets,
        class_groups={v[0]: v[1] for v in GROUPS.values()},
        operation='Retain source LC_Type1=17, QC=3 water; do not infer water where the source is absent.',
        retained_quality_rule='QC1 land remains unresolved; no change to QC10/fill/invalid/source-absence rules.',
        quality_semantics='Unclassified Share retains all QC1/3 area and overlaps accepted QC3 water coverage; '
                          'No Data Share continues to describe genuinely unavailable source/class area.',
        protected_inputs=protected, annual_audit=audits, previous_active_panel=previous))


def annual():
    subprocess.run([sys.executable, str(ROOT / '.codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py'),
                    '--root', str(ROOT), '--decisions', str(OUT / 'decisions.json'), '--pretty'], check=True)
    decisions = json.loads((OUT / 'decisions.json').read_text())
    for source, spec in decisions['datasets'].items():
        subprocess.run([sys.executable, str(ROOT / spec['script'])], check=True)
        pd.testing.assert_frame_equal(pd.read_parquet(ROOT / source), pd.read_parquet(ROOT / spec['output']))
    tables = [pq.read_table(ROOT / spec['output']) for spec in decisions['datasets'].values()]
    pq.write_table(pa.concat_tables(tables), DEST / 'modis_land_cover_mesh_preprocessed.parquet', compression='zstd')


def panels():
    decisions = json.loads((OUT / 'decisions.json').read_text())
    assert decisions['confirmed']
    frames = {y: pd.read_parquet(ROOT / spec['output']) for y, spec in
              zip(YEARS, decisions['datasets'].values(), strict=True)}
    index = pd.Index(frames[YEARS[0]]['Mesh Code'])
    outputs = []
    for key in ['full_panel', 'core_balanced_panel']:
        source_path = ROOT / decisions['previous_active_panel'][key]
        source = pq.ParquetFile(source_path)
        output_path = DEST / source_path.name
        pending = output_path.with_suffix('.pending.parquet')
        counts = {y: dict(rows=0, missing_before=0, missing_after=0, partial_after=0) for y in YEARS}
        writer = None
        def transform(table):
            position = index.get_indexer(table.column('Mesh Code').to_pylist())
            year = table.column('Road Year').to_numpy()
            assert (position >= 0).all() and np.isin(year, YEARS).all()
            result = table
            for name in CHANGED:
                values = np.empty(len(table), dtype=bool if name.startswith('Land Cover No Valid') or
                                  name.startswith('Land Cover Incomplete') else float)
                for y in YEARS:
                    use = year == y
                    values[use] = frames[y][name].to_numpy()[position[use]]
                result = result.set_column(result.schema.get_field_index(name), result.schema.field(name),
                                           pa.array(values, from_pandas=True))
            return result
        try:
            for batch in source.iter_batches(batch_size=65536):
                original = pa.Table.from_batches([batch]); result = transform(original)
                if writer is None:
                    writer = pq.ParquetWriter(pending, result.schema, compression='zstd')
                writer.write_table(result)
                year = original.column('Road Year').to_numpy()
                for y in YEARS:
                    use = year == y
                    counts[y]['rows'] += int(use.sum())
                    counts[y]['missing_before'] += int(original.column('Land Cover No Valid Pixels').to_numpy()[use].sum())
                    new_missing = result.column('Land Cover No Valid Pixels').to_numpy()
                    counts[y]['missing_after'] += int(new_missing[use].sum())
                    counts[y]['partial_after'] += int((result.column('Land Cover Incomplete Coverage').to_numpy() & ~new_missing & use).sum())
        finally:
            if writer is not None:
                writer.close()
        reader = pq.ParquetFile(pending)
        assert reader.metadata.num_rows == source.metadata.num_rows
        assert reader.schema_arrow.equals(source.schema_arrow, check_metadata=False)
        unchanged = [c for c in source.schema_arrow.names if c not in CHANGED]
        checked = 0
        for before, after in zip(source.iter_batches(batch_size=65536), reader.iter_batches(batch_size=65536), strict=True):
            before, after = pa.Table.from_batches([before]), pa.Table.from_batches([after])
            assert before.select(unchanged).equals(after.select(unchanged), check_metadata=False)
            assert after.equals(transform(before), check_metadata=False)
            checked += len(after)
        assert checked == source.metadata.num_rows
        assert sha(source_path) == decisions['protected_inputs'][str(source_path.relative_to(ROOT))]
        pending.replace(output_path)
        outputs.append(dict(dataset=key, path=str(output_path.relative_to(ROOT)), rows=checked,
                            columns=len(reader.schema_arrow), unchanged_columns=len(unchanged),
                            missing_after=sum(r['missing_after'] for r in counts.values()),
                            yearly=counts, sha256=sha(output_path)))
        print('Validated panel', key, checked, 'rows; missing', outputs[-1]['missing_after'], flush=True)
    for path, digest in decisions['protected_inputs'].items():
        assert sha(ROOT / path) == digest
    # All original raw responses remain checksum-verified.
    for manifest in ['download_manifest.json', 'metadata_manifest.json']:
        for record in json.loads((SOURCE / manifest).read_text())['records']:
            assert sha(ROOT / record['path']) == record['sha256']
    dump(OUT / 'panel_validation.json', dict(status='passed', decision_id=DECISION, outputs=outputs,
        annual_audit=decisions['annual_audit'], original_raw_and_processed_inputs_unchanged=True,
        class_groups_unchanged=True, all_unrelated_columns_preserved=True, cohort_and_keys_preserved=True,
        analytical_candidates=65, regression_refitted=False))


def finalize():
    report = json.loads((OUT / 'panel_validation.json').read_text()); assert report['status'] == 'passed'
    old = (OUT / 'AnaSOP_before_water_retained.txt').read_text()
    current = (ROOT / 'docs/AnaSOP.md').read_text()
    def split(text):
        start = re.search(r'^## 4\. ', text, re.M).start()
        end = re.search(r'^## 5\. ', text, re.M).start()
        return text[:start], text[start:end], text[end:]
    pre, section, post = split(current)
    oldpre, _, oldpost = split(old)
    assert pre == oldpre and post == oldpost
    section = section.replace('### Constructed Annual MODIS Land Cover\n\n',
        '### Constructed Annual MODIS Land Cover\n\nThe following construction checkpoint precedes the active water-retention revision below. Its original quality exclusion and cohort counts are historical.\n\n', 1)
    heading = '### Active MODIS Mask-Identified Water Retention'
    if heading in section:
        section = section[:section.index(heading)].rstrip() + '\n\n'
    recovered = sum(r['recovered_water_records'] for r in report['annual_audit'])
    remaining = report['outputs'][0]['missing_after']
    addition = f'''{heading}

The user rejects exclusion of source pixels identified as water by the product water mask. Retain the original IGBP water class for these pixels even when annual spectral classification is unavailable. This revises only the earlier exclusion of mask-identified unclassified water. Unclassified land, invalid labels and genuinely unavailable source areas retain their prior handling. No water label is inferred where the source tile is absent.

Use the same IGBP grouping: urban and built-up land; five forest classes; cropland; cropland/natural-vegetation mosaic; water; and other shrubland, savanna, grassland, wetland, snow/ice and barren classes. These are six fractions of the complete projected mesh area, derived from the original 17-class product, rather than a newly trained classification. Annual matching, native pixel intersections, class groups and all six readable names are unchanged.

Land Cover Coverage now includes mask-identified water area. The six shares partition this accepted coverage; no accepted coverage still gives six NaNs. Land Cover Unclassified Share retains its original quality meaning, including both unclassified land and the now-retained unclassified water. Consequently it overlaps accepted coverage and must not be added to coverage as a disjoint area component. Land Cover No Data Share, source coverage, product adjustment references and original source checksums remain preserved. Completeness and no-valid-pixel flags are recalculated from the updated coverage.

The revision restores six numerical shares for {recovered:,} mesh-period records and leaves {remaining:,} full-grid records without source-supported coverage. In a fully water-covered mesh the water share is one and the five other shares are zero. Partial source coverage and unresolved land areas are not redistributed or statistically imputed.

The active full panel retains 972,800 meshes and 4,864,000 records. The core-balanced panel retains 966,400 meshes and 4,832,000 records. Both retain 210 readable fields and 65 analytical candidates. All 201 columns outside the six shares and three coverage/completeness fields are preserved exactly, including road zero coding, population, radiance, facilities and original land-cover quality references. No model is refitted by this construction revision.

'''
    assert addition.isascii() and not re.search(r'data/|\.parquet', addition)
    updated = pre + section.rstrip() + '\n\n' + addition + post
    (ROOT / 'docs/AnaSOP.md').write_text(updated)
    newpre, _, newpost = split((ROOT / 'docs/AnaSOP.md').read_text())
    assert newpre == oldpre and newpost == oldpost
    previous = json.loads((OUT / 'previous_active_panel.json').read_text())
    pointer = dict(previous, decision_id=DECISION, preceding_road_decision_id=previous['decision_id'],
                   full_panel=report['outputs'][0]['path'], core_balanced_panel=report['outputs'][1]['path'],
                   land_cover_rule='Retain source IGBP class 17 with QC=3; preserve original quality markers.')
    dump(OUT / 'active_panel.json', pointer); dump(OUT.parent / 'active_panel.json', pointer)
    report.update(anasop_section_4_updated=True, all_other_sections_preserved=True,
                  new_anasop_text_english_ascii=True)
    dump(OUT / 'delivery_validation.json', report)
    lines = ['# Retain MODIS mask-identified water', '', f'Human decision: {DECISION}.', '',
             'Classification: original MCD12Q1 Collection 6.1 IGBP 17 classes, grouped into the same six area shares. '
             'Retain QC3 water with original class 17. QC1 land and unavailable source handling are unchanged. '
             'Quality references remain intact; Unclassified Share overlaps accepted QC3 coverage and is no longer a disjoint residual.', '',
             '| Year | Missing before | Water records restored | Missing after |', '| --- | ---: | ---: | ---: |']
    for r in report['annual_audit']:
        lines.append(f"| {r['year']} | {r['missing_before']:,} | {r['recovered_water_records']:,} | {r['missing_after']:,} |")
    lines += ['', 'Six shares sum to accepted coverage within 1e-9. Original raw and processed input checksums are unchanged. '
              'Annual readable outputs reproduce their confirmed inputs. Both panels preserve all 201 unrelated columns '
              'and the exact original mesh-period keys, row order and core cohort. No regression is refitted. '
              'Only AnaSOP Section 4 is updated.', '',
              'Official QC definition: https://lpdaac.usgs.gov/documents/1409/MCD12_User_Guide_V61.pdf (Table 11).', '',
              '## Active outputs', '']
    for r in report['outputs']:
        lines.append(f"- {r['dataset']}: {r['rows']:,} rows, {r['columns']} columns, {r['missing_after']:,} missing land-cover records; {r['path']}.")
    lines += ['', '## Reproduce', '', '```sh',
              'python3 src/preprocessing/retain_modis_water.py --stage prepare',
              'python3 src/preprocessing/retain_modis_water.py --stage annual',
              'python3 src/preprocessing/retain_modis_water.py --stage panels',
              'python3 src/preprocessing/retain_modis_water.py --stage finalize',
              '```', '']
    (OUT / 'README.md').write_text('\n'.join(lines))
    print('Water retention delivered; current data pointer and AnaSOP Section 4 updated.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['prepare', 'annual', 'panels', 'finalize'], required=True)
    {'prepare': prepare, 'annual': annual, 'panels': panels, 'finalize': finalize}[parser.parse_args().stage]()
