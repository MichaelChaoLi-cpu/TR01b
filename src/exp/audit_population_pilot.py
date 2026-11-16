#!/usr/bin/env python3
"""Read original pilot population archives and audit totals and disclosure links.

This script writes diagnostic outputs only. It does not select final variables,
alter raw files, impute absent meshes, or redistribute population.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/pilot/population'
FIELDS = {2000: 'T000146001', 2005: 'T000148001',
          2010: 'T000608001', 2020: 'T001100001'}
REFERENCES = ['https://www.e-stat.go.jp/help/data-definition-information/shuroku/T001100.pdf',
              'https://www.stat.go.jp/data/mesh/pdf/r2kokusei.pdf']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_source(year):
    field = FIELDS[year]
    archive = ROOT / f'data/raw/population/estat_1km/{year}/{field[:-3]}_5030.zip'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        member = next(n for n in z.namelist() if n.endswith('.txt'))
        rows = list(csv.reader(io.StringIO(z.read(member).decode('cp932'))))
    columns, labels = rows[:2]
    assert all(len(r) == len(columns) for r in rows[2:] if r)
    source = pd.DataFrame([r for r in rows[2:] if r], columns=columns, dtype='string')
    assert source.KEY_CODE.is_unique
    assert source.KEY_CODE.str.fullmatch(r'5030[0-7]{2}[0-9]{2}').all()
    view = ROOT / f'data/exp/data-organization/source-tables/population_{year}_{field[:-3]}_5030.csv'
    pd.testing.assert_frame_equal(source, pd.read_csv(view, dtype='string', keep_default_na=False))
    return source, archive, dict(zip(columns, labels))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summaries, sources, variables, links = [], [], [], []
    grid = pd.read_csv(ROOT / 'data/exp/data-preprocessing/pilot/common_grid_trial.csv',
                       dtype={'mesh_code': 'string'})
    for year, field in FIELDS.items():
        source, archive, labels = read_source(year)
        assert set(source.KEY_CODE) <= set(grid.mesh_code)
        total = pd.to_numeric(source[field], errors='coerce')
        male = pd.to_numeric(source[field[:-3] + '002'], errors='coerce')
        female = pd.to_numeric(source[field[:-3] + '003'], errors='coerce')
        comparable = total.notna() & male.notna() & female.notna()
        assert (total[comparable] == (male + female)[comparable]).all()
        assert total.dropna().ge(0).all() and total.dropna().mod(1).eq(0).all()
        counts = dict(population_year=year, pilot_meshes=len(grid), source_listed=len(source),
                      source_unlisted=len(grid) - len(source), numeric_total=int(total.notna().sum()),
                      source_nonnumeric_total=int(total.isna().sum()), numeric_zero=int(total.eq(0).sum()),
                      published_total_sum=int(total.sum()), gender_sum_checks=int(comparable.sum()))
        if year == 2020:
            assert set(source.HTKSYORI) == {'0', '1', '2'}
            indexed = source.set_index('KEY_CODE')
            for r in source[source.HTKSYORI.eq('2')].itertuples():
                assert r.HTKSAKI in indexed.index
                target = indexed.loc[r.HTKSAKI]
                assert target.HTKSYORI == '1' and r.KEY_CODE in target.GASSAN.split(';')
                links.append(dict(source_mesh=r.KEY_CODE, destination_mesh=r.HTKSAKI,
                                  published_total=int(getattr(r, field)),
                                  total_population_is_disclosed=True, total_not_reallocated=True))
            for r in source[source.HTKSYORI.eq('1')].itertuples():
                for code in r.GASSAN.split(';'):
                    assert code in indexed.index
                    assert indexed.loc[code, 'HTKSYORI'] == '2'
                    assert indexed.loc[code, 'HTKSAKI'] == r.KEY_CODE
            for status in ['0', '1', '2']:
                selected = source.HTKSYORI.eq(status)
                counts[f'disclosure_status_{status}_meshes'] = int(selected.sum())
                counts[f'disclosure_status_{status}_published_total'] = int(total[selected].sum())
        summaries.append(counts)
        sources.append(dict(year=year, archive=str(archive.relative_to(ROOT)),
                            archive_sha256=sha(archive), original_view_matches=True,
                            total_field=field, rows=len(source)))
        for name in source.columns:
            values = source[name]
            variables.append(dict(year=year, original_name=name, source_label=labels[name],
                                  dtype='source text', blank_pct=float(values.eq('').mean()*100),
                                  sample_values='; '.join(values.head(3).tolist())))
    pd.DataFrame(summaries).to_csv(OUT / 'source_summary.csv', index=False)
    pd.DataFrame(variables).to_csv(OUT / 'source_variable_inventory.csv', index=False)
    pd.DataFrame(links).to_csv(OUT / 'disclosure_links_2020.csv', index=False)
    report = dict(status='passed', scope='primary mesh 5030 pilot only', sources=sources,
                  summaries=summaries, references=REFERENCES,
                  total_population_exempt_from_disclosure_suppression=True,
                  disclosure_link_checks=len(links), raw_archives_unchanged=True,
                  final_variables_selected=False, processed_outputs_written=False)
    (OUT / 'source_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'SOURCE_README.md').write_text(
        '# Population pilot source audit\n\n'
        'Original archives were read without modification. Total population fields include all ages '
        'and both sexes. The 2020 official table definition explicitly exempts total population '
        'from suppression. Status 2 marks a mesh with suppressed detail variables, and status 1 '
        'marks the recipient of those details; neither means its published total population '
        'should be blanked or reaggregated. Earlier basic totals have no disclosure metadata '
        'columns; their status must not be inferred as 0.\n\n'
        'Source-unlisted pilot cells are reported separately; this audit does not interpret them '
        'as zero population. Variable naming and processing confirmation is pending. '
        'No processed population data or merged panel is written by this audit.\n\n'
        'Reproduce: `python3 src/exp/audit_population_pilot.py`. The source inventory lists '
        'all original fields; source summaries and the 2020 linkage audit are saved alongside it.\n\n'
        'Official definitions: ' + ', '.join(REFERENCES) + '\n')
    print(json.dumps(dict(status='passed', summaries=summaries, reciprocal_disclosure_links=len(links)), indent=2))


if __name__ == '__main__':
    main()
