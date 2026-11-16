"""Full-record missingness briefing for the selected five-period panels.

Focused adaptation of data-briefing for the requested missingness question: scan
Arrow batches without changing data, selecting a sample, or editing AnaSOP.
NaN/NULL, numerical zero and incomplete-coverage flags remain distinct.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-briefing/current-five-period-ksj-missingness'
SOURCE = ROOT / 'data/processed/national/ksj_eighteen_facilities'
YEARS = [2002, 2003, 2004, 2010, 2024]
CORE = ['Nighttime Radiance', 'Road Length Density', 'Population']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def candidates():
    groups = {'core': CORE}
    for kind, folder in [('existing_facilities', 'static-facilities'),
                         ('land_cover', 'modis-land-cover'), ('additional_ksj', 'ksj-eighteen-facilities')]:
        decisions = json.loads((ROOT / f'data/exp/data-preprocessing/{folder}/decisions.json').read_text())
        groups[kind] = list(dict.fromkeys(v['readable_name'] for s in decisions['datasets'].values()
                                        for v in s['variables'] if v.get('is_final_variable') == 'yes'))
    assert [len(v) for v in groups.values()] == [3, 38, 6, 18]
    flattened = [c for values in groups.values() for c in values]
    assert len(flattened) == len(set(flattened)) == 65
    return groups


def mask_missing(array):
    nulls = pc.is_null(array).to_numpy(zero_copy_only=False)
    if pa.types.is_floating(array.type):
        nan = pc.fill_null(pc.is_nan(array), False).to_numpy(zero_copy_only=False)
        return nulls | nan, nulls, nan
    return nulls, nulls, np.zeros(len(array), dtype=bool)


def scan(label, path, groups, codes):
    before = sha(path)
    reader = pq.ParquetFile(path); names = reader.schema_arrow.names
    assert len(names) in {208, 210}
    group_of = {c: g for g, columns in groups.items() for c in columns}
    analytical = list(group_of)
    assert set(analytical).issubset(names)
    counters = {c: Counter() for c in names}
    annual = {(y, c): Counter() for y in YEARS for c in analytical}
    row_totals = Counter(); yearly = {y: Counter() for y in YEARS}
    index = pd.Index(codes)
    seen = np.zeros((len(YEARS), len(codes)), dtype=bool)
    incomplete = {g: np.zeros_like(seen) for g in [*groups, 'all_65']}
    missing_patterns = Counter()
    scanned = 0
    for batch in reader.iter_batches(batch_size=65536):
        masks = {}; zeros = {}; infinities = {}
        fields = dict(zip(batch.schema.names, batch.columns, strict=True))
        yvals = fields['Road Year'].to_numpy(zero_copy_only=False)
        positions = index.get_indexer(fields['Mesh Code'].to_pylist())
        assert (positions >= 0).all() and np.isin(yvals, YEARS).all()
        for name, array in fields.items():
            missing, null, nan = mask_missing(array)
            masks[name] = missing
            item = counters[name]
            item.update(rows=len(array), missing=int(missing.sum()), null=int(null.sum()),
                        nan=int(nan.sum()))
            if pa.types.is_integer(array.type) or pa.types.is_floating(array.type):
                values = array.to_numpy(zero_copy_only=False)
                zero = (values == 0) & ~missing
                inf = np.isinf(values) & ~missing
                zeros[name] = zero; infinities[name] = inf
                item.update(zero=int(zero.sum()), infinite=int(inf.sum()))
            elif pa.types.is_string(array.type) or pa.types.is_large_string(array.type):
                blank = pc.fill_null(pc.equal(array, ''), False)
                item.update(empty_string=int(pc.sum(pc.cast(blank, pa.int64())).as_py()))
        any_by_group = {g: np.logical_or.reduce([masks[c] for c in columns]) for g, columns in groups.items()}
        any_by_group['all_65'] = np.logical_or.reduce([masks[c] for c in analytical])
        for g, mask in any_by_group.items():
            row_totals[g + '_rows_with_any_missing'] += int(mask.sum())
        core_code = (masks[CORE[0]].astype(np.uint8) + masks[CORE[1]].astype(np.uint8) * 2
                     + masks[CORE[2]].astype(np.uint8) * 4)
        counts = np.bincount(core_code, minlength=8)
        for pattern, n in enumerate(counts):
            missing_patterns[pattern] += int(n)
        for j, year in enumerate(YEARS):
            select = yvals == year; pos = positions[select]
            assert not seen[j, pos].any()
            seen[j, pos] = True
            yearly[year]['rows'] += int(select.sum())
            for g, mask in any_by_group.items():
                incomplete[g][j, pos] = mask[select]
                yearly[year][g + '_rows_with_any_missing'] += int(mask[select].sum())
            for c in analytical:
                item = annual[(year, c)]
                item.update(rows=int(select.sum()), missing=int(masks[c][select].sum()),
                            zero=int(zeros[c][select].sum()), infinite=int(infinities[c][select].sum()))
            for flag in ['Land Cover No Valid Pixels', 'Land Cover Incomplete Coverage',
                         'Bus Candidate Coverage Limited', 'Bus Candidate Identity Review Pending']:
                flag_values = fields[flag].to_numpy(zero_copy_only=False)
                n = int(np.sum(flag_values[select] == True))
                yearly[year][flag] += n
                row_totals[flag] += n
        scanned += len(batch)
    assert scanned == reader.metadata.num_rows and sha(path) == before
    assert np.array_equal(seen, np.broadcast_to(seen[0], seen.shape))
    meshes = int(seen[0].sum())
    result = dict(dataset=label, source=str(path.relative_to(ROOT)), sha256=before,
                  rows=scanned, meshes=meshes, columns=len(names), analytical_columns=65,
                  numerical_infinite_values=sum(counters[c]['infinite'] for c in analytical),
                  row_summary=dict(row_totals), yearly={str(y): dict(v) for y, v in yearly.items()},
                  mesh_summary={}, core_missing_patterns=[])
    for g in incomplete:
        any_mesh = incomplete[g].any(axis=0)
        result['mesh_summary'][g] = dict(meshes_with_any_missing=int(any_mesh.sum()),
                                        meshes_complete_all_five_periods=meshes-int(any_mesh.sum()))
    for code, count in sorted(missing_patterns.items()):
        result['core_missing_patterns'].append(dict(missing=[c for k, c in enumerate(CORE) if code & (1 << k)], rows=count))
    variable_rows = []
    for c in names:
        entry = dict(dataset=label, variable=c, group=group_of.get(c, 'reference'),
                     dtype=str(reader.schema_arrow.field(c).type), **dict(counters[c]))
        entry['missing_pct'] = 100 * entry['missing'] / scanned
        entry['zero_pct'] = 100 * entry.get('zero', 0) / scanned
        variable_rows.append(entry)
    annual_rows = []
    for (y, c), item in annual.items():
        entry = dict(dataset=label, year=y, variable=c, group=group_of[c], **dict(item))
        entry['missing_pct'] = 100 * entry['missing'] / entry['rows']
        annual_rows.append(entry)
    print(label, 'rows', scanned, 'complete 65 rows', scanned-row_totals['all_65_rows_with_any_missing'],
          'complete 65 meshes', result['mesh_summary']['all_65']['meshes_complete_all_five_periods'], flush=True)
    return result, variable_rows, annual_rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    groups = candidates()
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code.astype(str).tolist()
    summaries, variables, annual = [], [], []
    for label, filename in [('national_full', 'road_population_light_facilities_land_cover_ksj_five_period_preprocessed.parquet'),
                            ('balanced', 'balanced_five_period_facilities_land_cover_ksj_panel_preprocessed.parquet')]:
        summary, rows, yearrows = scan(label, SOURCE / filename, groups, codes)
        summaries.append(summary); variables.extend(rows); annual.extend(yearrows)
    frame = pd.DataFrame(variables)
    frame.to_csv(OUT / 'all_column_missingness.csv', index=False)
    frame.loc[frame.group != 'reference'].to_csv(OUT / 'analytical_variable_missingness.csv', index=False)
    pd.DataFrame(annual).to_csv(OUT / 'analytical_missingness_by_period.csv', index=False)
    report = dict(status='passed', scope='full-record scan of current panels; no sampling',
                  groups=groups, datasets=summaries, data_modified=False, anasop_modified=False,
                  new_sample_selected=False, statistical_models_refitted=False,
                  time_series_plots_generated=0, distribution_plots_generated=0,
                  interpretation='Numerical missingness is distinct from zero and from incomplete source coverage. This report does not certify source completeness.')
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    text = '# Current five-period panel: missingness audit\n\n'
    column_count = summaries[0]['columns']
    assert all(s['columns'] == column_count for s in summaries)
    text += (f'Focused data-briefing adaptation for the requested missingness question. Scan all records in both '
             f'{column_count}-column panels, with no sample, variable transformation, imputation, row deletion or AnaSOP edit. '
             'The 65 analytical candidates are identified from confirmed construction decisions plus the three '
             'core model variables. Source and quality references remain separate.\n\n')
    text += '| Dataset | Rows | Meshes | All 65 observed rows | All-five-period complete meshes |\n| --- | ---: | ---: | ---: | ---: |\n'
    for s in summaries:
        complete = s['rows']-s['row_summary']['all_65_rows_with_any_missing']
        text += f"| {s['dataset']} | {s['rows']:,} | {s['meshes']:,} | {complete:,} | {s['mesh_summary']['all_65']['meshes_complete_all_five_periods']:,} |\n"
    text += '\n## Analytical variables with numerical missingness\n\n'
    text += '| Dataset | Variable | Missing rows | Missing percent | Zero rows |\n| --- | --- | ---: | ---: | ---: |\n'
    for row in frame.loc[(frame.group != 'reference') & (frame.missing > 0)].itertuples():
        text += f'| {row.dataset} | {row.variable} | {row.missing:,} | {row.missing_pct:.6f}% | {int(row.zero):,} |\n'
    text += ('\nNull and floating NaN are missing; true numeric zero is retained and counted separately. Infinite '
             'numeric values are reported separately. Empty reference strings are disclosed without recoding. '
             'MODIS partial valid coverage remains a numerical value with a flag, rather than numerical NaN. '
             'Facility count zeros represent no selected observed record under the documented source inventory; '
             'they do not establish an exhaustive facility census. Bus candidate coverage/identity flags and '
             'the static-snapshot assumption remain relevant even when numerical values are present.\n\n'
             f'See all_column_missingness.csv for all {column_count} fields in each panel, '
             'analytical_variable_missingness.csv for the 65 candidates, '
             'analytical_missingness_by_period.csv for missingness by road period and summary.json for '
             'row/mesh patterns and coverage flags. Reproduce with '
             f'`python3 src/exp/brief_current_panel_missingness.py --panel-dir {SOURCE.relative_to(ROOT)} '
             f'--output-dir {OUT.relative_to(ROOT)}`. The two panels retain their original SHA256 '
             'checksums after the scan. No skipped input dataset. No time-series or distribution plots are '
             'needed for this focused missingness question.\n')
    (OUT / 'README.md').write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--panel-dir', default=str(SOURCE.relative_to(ROOT)))
    parser.add_argument('--output-dir', default=str(OUT.relative_to(ROOT)))
    args = parser.parse_args()
    SOURCE = ROOT / args.panel_dir
    OUT = ROOT / args.output_dir
    main()
