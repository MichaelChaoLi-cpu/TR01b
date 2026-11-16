"""Apply the user's density-only zero coding, retaining source missingness flags.

Prepare confirmed inputs, generate/run five readable-name road scripts, then build
and verify new full and core-balanced panels. Source datasets remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/road-density-zero'
DEST = ROOT / 'data/processed/national/road_density_zero'
SOURCE = ROOT / 'data/processed/national/ksj_eighteen_facilities'
YEARS = [2002, 2003, 2004, 2010, 2024]
DECISION = 'MILI-D-20261010-022'
FULL = 'road_population_light_facilities_land_cover_ksj_five_period_preprocessed.parquet'
BALANCED = 'balanced_five_period_facilities_land_cover_ksj_panel_preprocessed.parquet'
FLAGS = ['Road Density Originally Missing', 'Road Density Source Status']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True); DEST.mkdir(parents=True, exist_ok=True)
    baseline = OUT / 'AnaSOP_before_density_zero.txt'
    if not baseline.exists():
        baseline.write_bytes((ROOT / 'docs/AnaSOP.md').read_bytes())
    datasets = {}; audits = []; protected = {}
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code.astype(str).tolist()
    for year in YEARS:
        road_path = ROOT / f'data/processed/national/roads_{year}_preprocessed.parquet' if year != 2024 else ROOT / 'data/processed/national/five_period/roads_2024_preprocessed.parquet'
        quality_path = ROOT / f'data/exp/data-preprocessing/national/road_quality_{year}.parquet' if year != 2024 else ROOT / 'data/exp/data-preprocessing/five-period-2024/road_quality_2024.parquet'
        for path in [road_path, quality_path]:
            protected[str(path.relative_to(ROOT))] = sha(path)
        frame = pd.read_parquet(road_path)
        quality = pd.read_parquet(quality_path)
        assert frame['Mesh Code'].astype(str).tolist() == codes
        assert quality['mesh_code' if year != 2024 else 'Mesh Code'].astype(str).tolist() == codes
        assert frame['Road Year'].eq(year).all()
        values = frame['Road Length Density'].to_numpy(dtype=float)
        assert not np.isinf(values).any()
        missing = np.isnan(values)
        status = np.full(len(codes), 'observed', dtype=object)
        if year != 2024:
            unlisted = ~quality.source_row_present.to_numpy(dtype=bool)
            unknown = quality.source_unknown.eq(True).to_numpy(dtype=bool)
            assert not (unlisted & unknown).any()
            assert np.array_equal(missing, unlisted | unknown)
            status[unlisted] = 'source_unlisted'
            status[unknown] = 'source_unknown'
        else:
            uncovered = ~quality['Source Tile Covered'].to_numpy(dtype=bool)
            assert np.array_equal(missing, uncovered)
            status[uncovered] = 'source_archive_missing'
        frame[FLAGS[0]] = missing
        frame[FLAGS[1]] = status
        input_relative = f'data/exp/data-preprocessing/road-density-zero/confirmed-inputs/roads_{year}_zero_input.parquet'
        path = ROOT / input_relative; path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False, compression='zstd')
        datasets[input_relative] = dict(output=f'data/processed/national/road_density_zero/roads_{year}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_road_density_zero_{year}.py',
            variables=[dict(original_name=c, readable_name=c, full_name=c,
                            is_final_variable='yes' if c == 'Road Length Density' else 'no',
                            preprocessing=['fill_constant:0'] if c == 'Road Length Density' else []) for c in frame.columns])
        audits.append(dict(year=year, rows=len(frame), density_missing_before=int(missing.sum()),
                          source_status_counts=dict(Counter(status)), original_density_zero_rows=int(np.sum(values == 0)),
                          road_source=str(road_path.relative_to(ROOT)), quality_source=str(quality_path.relative_to(ROOT))))
    for path in [SOURCE / FULL, SOURCE / BALANCED,
                 ROOT / 'data/exp/gwpr-pooled-five-period-2024/mesh-map-3km/local_coefficients.parquet']:
        protected[str(path.relative_to(ROOT))] = sha(path)
    dump(OUT / 'decisions.json', dict(confirmed=True, decision_id=DECISION,
        supersedes_density_component_of='MILI-D-20261009-009', years=YEARS, datasets=datasets,
        operation='Missing Road Length Density -> 0; preserve all observed densities exactly.',
        source_status_policy='Both source-unlisted and source-unknown density values are zero-coded by explicit human instruction; retain both labels.',
        unchanged_variables='Road Length, Mesh Area, population, nighttime radiance, all facilities and annual land cover.',
        cohort_rule='Finite road density, population and nighttime radiance in all five periods; no land, island or administrative filter.',
        zero_interpretation='Analytical coding assumption, not verified physical absence of roads.',
        road_audit=audits, protected_inputs=protected))
    print('Confirmed density-only zero rule:', sum(x['density_missing_before'] for x in audits), 'records.', flush=True)


def run_roads():
    subprocess.run([sys.executable, str(ROOT / '.codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py'),
                    '--root', str(ROOT), '--decisions', 'data/exp/data-preprocessing/road-density-zero/decisions.json', '--pretty'], check=True)
    decisions = json.loads((OUT / 'decisions.json').read_text())
    for spec in decisions['datasets'].values():
        result = subprocess.run([sys.executable, str(ROOT / spec['script'])], capture_output=True, text=True)
        print(result.stdout.strip(), flush=True)
        if result.returncode:
            print(result.stderr, file=sys.stderr); raise SystemExit(result.returncode)


def build():
    decisions = json.loads((OUT / 'decisions.json').read_text()); assert decisions['confirmed']
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code.astype(str)
    index = pd.Index(codes); assert index.is_unique
    roads = []
    original_roads = []
    for year, spec, audit in zip(YEARS, decisions['datasets'].values(), decisions['road_audit'], strict=True):
        table = pq.read_table(ROOT / spec['output'])
        original = pq.read_table(ROOT / audit['road_source'])
        assert table.column('Mesh Code').to_pylist() == codes.tolist()
        assert table.column('Road Year').to_numpy().tolist() == [year] * len(codes)
        for name in ['Road Length', 'Mesh Area']:
            assert table.column(name).equals(original.column(name))
        old = original.column('Road Length Density').to_numpy()
        new = table.column('Road Length Density').to_numpy()
        missing = np.isnan(old)
        assert np.array_equal(new, np.where(missing, 0.0, old))
        assert np.array_equal(table.column(FLAGS[0]).to_numpy(), missing)
        assert not np.isnan(new).any()
        roads.append(table); original_roads.append(original)
    # Source tables use varying Arrow string widths; keys are matched explicitly.
    density_arrays = [t.column('Road Length Density').to_numpy() for t in roads]
    old_density_arrays = [t.column('Road Length Density').to_numpy() for t in original_roads]
    missing_arrays = [t.column(FLAGS[0]).to_numpy() for t in roads]
    status_arrays = [np.array(t.column(FLAGS[1]).to_pylist(), dtype=object) for t in roads]
    source = pq.ParquetFile(SOURCE / FULL)
    assert len(source.schema_arrow.names) == 208
    assert not set(FLAGS).intersection(source.schema_arrow.names)
    available = np.zeros((5, len(codes)), dtype=bool)
    seen = np.zeros_like(available)
    def positions(table):
        pos = index.get_indexer(table.column('Mesh Code').to_pylist())
        years = table.column('Road Year').to_numpy()
        assert (pos >= 0).all() and np.isin(years, YEARS).all()
        return pos, years
    for batch in source.iter_batches(columns=['Mesh Code', 'Road Year', 'Road Length Density', 'Population', 'Nighttime Radiance'], batch_size=65536):
        table = pa.Table.from_batches([batch]); pos, years = positions(table)
        for j, year in enumerate(YEARS):
            mask = years == year; subset = pos[mask]
            assert len(np.unique(subset)) == len(subset) and not seen[j, subset].any()
            seen[j, subset] = True
            numeric = np.isfinite(table.column('Population').to_numpy()[mask]) & np.isfinite(table.column('Nighttime Radiance').to_numpy()[mask])
            assert np.array_equal(table.column('Road Length Density').to_numpy()[mask], old_density_arrays[j][subset], equal_nan=True)
            available[j, subset] = numeric & np.isfinite(density_arrays[j][subset])
    assert seen.all()
    eligible = available.all(axis=0)
    old_codes = pd.Index(pq.read_table(SOURCE / BALANCED, columns=['Mesh Code']).column('Mesh Code').to_pylist()).unique()
    assert eligible[index.get_indexer(old_codes)].all()
    writers = {}; output_paths = {'full': DEST / FULL, 'balanced': DEST / BALANCED}
    pending = {k: p.with_suffix('.pending.parquet') for k, p in output_paths.items()}
    totals = Counter(); balances = Counter(); zero_counts = Counter()
    def transformed(table):
        pos, years = positions(table)
        density = np.empty(len(table), dtype=float); missing = np.empty(len(table), dtype=bool)
        statuses = np.empty(len(table), dtype=object)
        for j, year in enumerate(YEARS):
            mask = years == year
            density[mask] = density_arrays[j][pos[mask]]
            missing[mask] = missing_arrays[j][pos[mask]]
            statuses[mask] = status_arrays[j][pos[mask]]
        result = table.set_column(table.schema.get_field_index('Road Length Density'),
                                  table.schema.field('Road Length Density'), pa.array(density))
        return result.append_column(FLAGS[0], pa.array(missing)).append_column(FLAGS[1], pa.array(statuses)), pos
    try:
        for batch in source.iter_batches(batch_size=65536):
            original = pa.Table.from_batches([batch]); result, pos = transformed(original)
            for label, output in [('full', result), ('balanced', result.filter(pa.array(eligible[pos])))]:
                if len(output) == 0:
                    continue
                if label not in writers:
                    writers[label] = pq.ParquetWriter(pending[label], output.schema, compression='zstd')
                writers[label].write_table(output); totals[label] += len(output)
                zero_counts[label] += int(np.sum(output.column('Population').to_numpy() == 0))
            for year in YEARS:
                balances[int(year)] += int(np.sum((result.column('Road Year').to_numpy() == year) & eligible[pos]))
    finally:
        for writer in writers.values():
            writer.close()
    assert totals['full'] == source.metadata.num_rows == len(codes) * 5
    assert totals['balanced'] == int(eligible.sum()) * 5
    assert all(count == int(eligible.sum()) for count in balances.values())
    full = pq.ParquetFile(pending['full']); balanced = pq.ParquetFile(pending['balanced'])
    checked = Counter(); balanced_group = 0
    unchanged = [c for c in source.schema_arrow.names if c != 'Road Length Density']
    for batch, new_batch in zip(source.iter_batches(batch_size=65536), full.iter_batches(batch_size=65536), strict=True):
        original = pa.Table.from_batches([batch]); result = pa.Table.from_batches([new_batch])
        expected, pos = transformed(original)
        assert result.equals(expected, check_metadata=False)
        assert original.select(unchanged).equals(result.select(unchanged), check_metadata=False)
        assert result.column('Road Length Density').null_count == 0
        known = ~result.column(FLAGS[0]).to_numpy()
        assert np.array_equal(original.column('Road Length Density').to_numpy()[known], result.column('Road Length Density').to_numpy()[known])
        subset = result.filter(pa.array(eligible[pos]))
        if len(subset):
            assert subset.equals(balanced.read_row_group(balanced_group), check_metadata=False)
            balanced_group += 1; checked['balanced'] += len(subset)
        checked['full'] += len(result)
    assert checked == totals and balanced_group == balanced.num_row_groups
    for path, digest in decisions['protected_inputs'].items():
        assert sha(ROOT / path) == digest
    outputs = []
    for label, path in output_paths.items():
        pending[label].replace(path)
        outputs.append(dict(dataset=label, path=str(path.relative_to(ROOT)), sha256=sha(path),
                            rows=totals[label], meshes=len(codes) if label == 'full' else int(eligible.sum()),
                            columns=210, density_missing_after=0, population_zero_rows=zero_counts[label]))
    report = dict(status='passed', decision_id=DECISION, density_missing_filled=sum(int(a.sum()) for a in missing_arrays),
                  observed_densities_preserved_exactly=True, unchanged_previous_columns=207,
                  all_other_previous_values_preserved_exactly=True, source_inputs_unchanged=True,
                  new_reference_columns=FLAGS, analytical_candidate_count=65,
                  complete_five_period_meshes=int(eligible.sum()), previous_balanced_meshes=len(old_codes),
                  additional_balanced_meshes=int(eligible.sum())-len(old_codes), previous_balanced_meshes_all_retained=True,
                  no_land_or_island_filter=True, geographic_assignments_extended=False,
                  regression_results_unchanged=True, regressions_refitted=False, outputs=outputs,
                  road_audit=decisions['road_audit'])
    dump(OUT / 'panel_validation.json', report)
    print('Verified full:', totals['full'], 'balanced:', totals['balanced'], 'meshes:', int(eligible.sum()), 'columns: 210', flush=True)


def finalize():
    report = json.loads((OUT / 'panel_validation.json').read_text()); assert report['status'] == 'passed'
    missing = json.loads((ROOT / 'data/exp/data-briefing/road-density-zero-missingness/summary.json').read_text())
    assert all(x['row_summary']['core_rows_with_any_missing'] == 0 for x in missing['datasets'] if x['dataset'] == 'balanced')
    before = (OUT / 'AnaSOP_before_density_zero.txt').read_bytes().decode('utf-8')
    current = (ROOT / 'docs/AnaSOP.md').read_bytes().decode('utf-8')
    def split(text):
        a = re.search(r'^## 4\. ', text, re.M).start(); b = re.search(r'^## 5\. ', text, re.M).start()
        return text[:a], text[a:b], text[b:]
    bpre, _, bpost = split(before); pre, section, post = split(current)
    assert pre == bpre and post == bpost
    old = ('The user confirmed that historical unknown road records and meshes absent from the road source are both missing data. '
           'Encode unavailable Road Length, Road Length Density, and source Mesh Area as NaN.')
    new = ('The earlier rule classified historical unknown road records and source-unlisted meshes as missing. '
           'The active density-only revision below now assigns zero to unavailable Road Length Density by human instruction. '
           'Unavailable Road Length and source Mesh Area remain NaN; original density missingness and source status remain recorded.')
    if old in section:
        section = section.replace(old, new, 1)
    section = section.replace('Source inconsistencies remain flagged; the documented 2010 length reconstruction does not alter supplied density.',
        'Source inconsistencies remain flagged; the documented 2010 length reconstruction does not alter supplied density. Missing analytical density follows the active zero-coding revision below.')
    # Clearly identify prior construction cohorts as checkpoints, without changing their numbers or estimates.
    section = section.replace('This subsection is authoritative for the current analytical cohort and supersedes earlier four-period sample statements.',
        'This subsection records the five-period extension before the subsequent density-zero coding revision; its cohort figures describe the existing regression checkpoint.')
    section = section.replace('Road unknown and unlisted observations remain NaN under the earlier confirmed road rule.',
        'At this earlier population-revision checkpoint, road unknown and unlisted observations remained NaN; the active density-only rule is documented below.')
    section = section.replace('### Constructed Eighteen Additional KSJ Snapshot Counts\n\nThe confirmed additional supplement',
        '### Constructed Eighteen Additional KSJ Snapshot Counts\n\nThis construction checkpoint precedes the density-zero coding revision below. The confirmed additional supplement')
    heading = '### Active Density-Only Zero Coding Revision'
    if heading in section:
        section = section[:section.index(heading)].rstrip() + '\n\n'
    addition = ('\n' + heading + '\n\n'
        'The user now directs all missing Road Length Density values to be coded as zero in the analytical dataset, '
        'including historical source-unlisted meshes and source-unknown records. This supersedes the density '
        'component of the earlier missing-road rule. For the source-derived density \\(D_{it}\\), define '
        '\\(D_{it}^{*}=D_{it}\\) when finite and \\(D_{it}^{*}=0\\) when unavailable. This is an explicit analytical '
        'coding assumption, including for unknown values; it does not establish verified physical absence of roads.\n\n'
        'Retain Road Density Originally Missing and Road Density Source Status as readable provenance references. '
        'They distinguish source-unlisted, source-unknown and observed values. Earlier missing-density data remain '
        'separately preserved. Every finite observed density is retained exactly; Road Length and Mesh Area '
        'are not filled or recomputed. Population, Nighttime Radiance, facilities, annual land cover and actual '
        'matching years are unchanged. No raw archive is modified.\n\n'
        f"The revision codes {report['density_missing_filled']:,} missing densities as zero: 2,074,500 source-unlisted "
        'and 808,353 source-unknown records. The year-specific counts are 723,789 in 2002, 722,287 in 2003, '
        '720,962 in 2004 and 715,815 in 2010; 2024 already has no numerical density missingness.\n\n'
        'The full updated dataset retains 972,800 meshes and 4,864,000 observations. Its 210 readable fields '
        'consist of the previous 208 fields plus two provenance references; 207 prior fields are preserved exactly '
        'and only Road Length Density changes. The count of analytical candidates remains 65.\n\n'
        f"Reapplying the existing finite-density, population and radiance criterion across all five periods yields "
        f"{report['complete_five_period_meshes']:,} meshes and {report['complete_five_period_meshes']*5:,} observations. "
        f"All {report['previous_balanced_meshes']:,} previous core-balanced meshes remain eligible; "
        f"{report['additional_balanced_meshes']:,} additional meshes enter this numerical completeness cohort. "
        'Population archive gaps remain missing and no land, coastline, island or administrative filter is introduced. '
        'Land-cover missingness and incomplete coverage remain present; the expanded core-balanced cohort is not '
        'an all-covariate-complete cohort.\n\n'
        'Existing national, regional, prefecture and local model outputs remain associated with the earlier '
        '228,988-mesh cohort and have not been refitted. Existing reviewed administrative classifications '
        'are preserved; no geographic assignment for newly eligible meshes or additional nearest-land exception '
        'is inferred in this variable-construction step. The expanded cohort is a newly constructed data product, '
        'rather than a completed new regression result.\n\n')
    assert addition.isascii() and not re.search(r'\.parquet|data/', addition)
    text = pre + section.rstrip() + '\n' + addition + post
    (ROOT / 'docs/AnaSOP.md').write_bytes(text.encode('utf-8'))
    apre, _, apost = split((ROOT / 'docs/AnaSOP.md').read_bytes().decode('utf-8'))
    assert apre == bpre and apost == bpost
    content = '# Road density missing-to-zero revision\n\n'
    content += (f'Approved under {DECISION}, superseding the density component of MILI-D-20261009-009. '
        'Fill only numerical Road Length Density missingness, including source-unlisted and source-unknown '
        'records; preserve original source status and an original-missing flag. These coded zeros are an '
        'assumption, not verified absence of roads. Known density, length, area and all other prior values are '
        'preserved; original files and regression outputs remain unchanged.\n\n')
    content += '| Year | Newly zero-coded densities | Source-unlisted | Source-unknown |\n| --- | ---: | ---: | ---: |\n'
    for r in report['road_audit']:
        c = r['source_status_counts']
        content += f"| {r['year']} | {r['density_missing_before']:,} | {c.get('source_unlisted',0):,} | {c.get('source_unknown',0):,} |\n"
    content += '\n'
    for output in report['outputs']:
        content += f"- {output['dataset']}: {output['rows']:,} rows, {output['meshes']:,} meshes, {output['columns']} columns; {output['path']}.\n"
    content += ('\nThe balanced file uses the existing core-variable five-period completeness criterion, now '
        'expanded after density zero coding. It does not apply a land-cover completeness or land/island filter. '
        'Row order follows the original full panel (period first), and mesh-year keys are unique. No old '
        'eligible mesh is removed. Newly admitted meshes have not been assigned to regions or prefectures '
        'by this step; reviewed prior labels and exceptions are not silently extended. No model is refitted.\n\n'
        'Missingness of the expanded data is independently summarized in '
        'data/exp/data-briefing/road-density-zero-missingness/. '
        'AnaSOP Section 4 records the active rule; other sections and existing model descriptions are unchanged.\n\n'
        '## Reproduce\n\n```sh\n'
        'python3 src/preprocessing/recode_missing_road_density_zero.py --stage prepare\n'
        'python3 src/preprocessing/recode_missing_road_density_zero.py --stage roads\n'
        'python3 src/preprocessing/recode_missing_road_density_zero.py --stage build\n'
        'python3 src/exp/brief_current_panel_missingness.py --panel-dir data/processed/national/road_density_zero --output-dir data/exp/data-briefing/road-density-zero-missingness\n'
        'python3 src/preprocessing/recode_missing_road_density_zero.py --stage finalize\n'
        '```\n')
    (OUT / 'README.md').write_text(content)
    report.update(anasop_section_4_updated=True, all_other_anasop_sections_preserved=True,
                  added_anasop_text_english_ascii=True, missingness_report=str((ROOT / 'data/exp/data-briefing/road-density-zero-missingness/summary.json').relative_to(ROOT)))
    dump(OUT / 'delivery_validation.json', report)
    dump(OUT / 'active_panel.json', dict(decision_id=DECISION, full_panel=report['outputs'][0]['path'],
        core_balanced_panel=report['outputs'][1]['path'], numerical_cohort_rule=decisions_rule(),
        previous_model_cohort_meshes=228988, regression_refitted=False))
    # Discoverable current data pointer; earlier scope-specific decisions remain intact.
    (OUT.parent / 'active_panel.json').write_bytes((OUT / 'active_panel.json').read_bytes())
    print('Density-zero revision delivered; Section 4 updated and other sections preserved.', flush=True)


def decisions_rule():
    return 'All five periods finite in Road Length Density after zero coding, Population, Nighttime Radiance.'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True, choices=['prepare', 'roads', 'build', 'finalize'])
    stage = parser.parse_args().stage
    {'prepare': prepare, 'roads': run_roads, 'build': build, 'finalize': finalize}[stage]()
