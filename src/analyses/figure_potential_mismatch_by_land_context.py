"""Potential Mismatch by Land Context.

Plan: five displayed contexts in two bar panels with numerator/denominator counts.
Framework: AnaSOP Sections 5-7, descriptive 2024 UMD comparable-context screen.
Panel a: candidates / supported meshes; panel b: valid-zero radiance / candidates.
No new thresholds, significance tests, regressions, exclusions or source changes.
Run locally: uv run python src/analyses/figure_potential_mismatch_by_land_context.py
"""
from __future__ import annotations
import os
import json
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter
from figure_spatial_distribution_of_potential_mismatch import CONTEXT_COLORS
from run_road_economy_mismatch_trial import sha

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/umd-mismatch-screen'
OUT = ROOT / 'data/results/figures/Figure_potential_mismatch_by_land_context.png'
AUDIT = ROOT / 'data/exp/figure-table-generation/potential-mismatch-by-land-context'
ORDER = ['Forest', 'Shrublands and Grasslands', 'Urban', 'Cropland', 'Water', 'Barren', 'Incomplete coverage']
DISPLAY = ['Forest', 'Shrublands and Grasslands', 'Urban', 'Cropland', 'Water']
LABELS = {'Shrublands and Grasslands': 'Shrublands and\nGrasslands',
          'Incomplete coverage': 'Incomplete\ncoverage'}

def main():
    source = SOURCE / 'mesh_screen_2024.parquet'
    validation = SOURCE / 'validation.json'
    summary = SOURCE / 'land_context_summary.csv'
    contract = SOURCE / 'screening_contract.json'
    protected = [source, validation, summary, contract]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    check = json.loads(validation.read_text())
    rules = json.loads(contract.read_text())
    assert check['status'] == 'passed' and check['classification'] == rules['classification'] == 'UMD'
    assert check['output_sha256'] == sha(source) and not rules['thresholds_changed']
    d = pd.read_parquet(source, columns=['Mesh Code', 'Road Year', 'Nighttime Light Year',
        'Population Year', 'Land Context', 'Supported Comparison', 'Potential Mismatch Candidate', 'Nighttime Radiance'])
    assert len(d) == check['meshes'] == 383386 and d['Mesh Code'].is_unique
    assert d['Road Year'].eq(2024).all() and d['Nighttime Light Year'].eq(2024).all()
    assert d['Population Year'].eq(2020).all()
    supported = d['Supported Comparison']
    candidate = d['Potential Mismatch Candidate'].fillna(False)
    assert d['Potential Mismatch Candidate'].isna().equals(~supported)
    assert not (candidate & ~supported).any()
    assert np.isfinite(d['Nighttime Radiance']).all() and d['Nighttime Radiance'].ge(0).all()
    order = ORDER + sorted(set(d['Land Context']) - set(ORDER))
    rows = []
    for label in order:
        z = d.loc[d['Land Context'].eq(label)]
        if z.empty:
            continue
        eligible = z['Supported Comparison']
        c = z['Potential Mismatch Candidate'].fillna(False)
        cohort, n, k = len(z), int(eligible.sum()), int(c.sum())
        zero = int(z.loc[c, 'Nighttime Radiance'].eq(0).sum())
        assert 0 <= zero <= k <= n <= cohort
        rows.append({'Land Context': label, 'Cohort Meshes': cohort, 'Supported Meshes': n,
            'Candidate Meshes': k, 'Candidate Zero Radiance Meshes': zero,
            'Candidate Fraction of Supported Meshes': k / n if n else np.nan,
            'Candidate Zero Radiance Fraction': zero / k if k else np.nan})
    table = pd.DataFrame(rows).set_index('Land Context')
    reference = pd.read_csv(summary).set_index('Land Context').reindex(table.index)
    pd.testing.assert_frame_equal(table, reference, check_dtype=False, atol=1e-12, rtol=1e-12)
    assert table['Cohort Meshes'].sum() == len(d)
    assert table['Supported Meshes'].sum() == check['supported_meshes'] == 376219
    assert table['Candidate Meshes'].sum() == check['candidate_meshes'] == 66097
    assert table['Candidate Zero Radiance Meshes'].sum() == check['candidate_zero_radiance_meshes'] == 64034
    assert np.isnan(table.loc['Barren', 'Candidate Fraction of Supported Meshes'])
    assert np.isnan(table.loc['Barren', 'Candidate Zero Radiance Fraction'])
    display = table.loc[DISPLAY].copy()
    colors = [CONTEXT_COLORS[x] for x in display.index]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig = plt.figure(figsize=(18, 6), facecolor='white')
    axes = [fig.add_axes([x, .17, .28, .68]) for x in [.17, .61]]
    y = np.arange(len(display))
    specs = [
        ('Candidate Fraction of Supported Meshes', 'Candidate Meshes', 'Supported Meshes',
         30, [0, 5, 10, 15, 20, 25, 30], 'Candidates among supported meshes (%)', 'Candidates /\nsupported meshes'),
        ('Candidate Zero Radiance Fraction', 'Candidate Zero Radiance Meshes', 'Candidate Meshes',
         100, [0, 25, 50, 75, 100], 'Valid zero radiance among candidates (%)', 'Zero radiance /\ncandidate meshes'),
    ]
    value_texts = []
    for letter, ax, (fraction, numerator, denominator, maximum, ticks, xlabel, count_label) in zip('ab', axes, specs):
        values = 100 * display[fraction].to_numpy()
        valid = np.isfinite(values)
        ax.barh(y[valid], values[valid], color=np.asarray(colors)[valid], height=.56,
                edgecolor='none', zorder=3)
        ax.set_ylim(len(display) - .45, -.55)
        ax.set_xlim(0, maximum)
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0, symbol=''))
        ax.set_xlabel(xlabel, fontsize=13, labelpad=12)
        ax.set_yticks(y)
        ax.set_yticklabels([LABELS.get(x, x) for x in display.index] if letter == 'a' else [''] * len(display), fontsize=13)
        ax.tick_params(axis='y', length=0, pad=12)
        ax.tick_params(axis='x', labelsize=12)
        ax.set_axisbelow(True)
        ax.grid(axis='x', color='#dde2e6', linewidth=.7)
        for spine in ['top', 'right', 'left']:
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color('#a7afb7')
        ax.text(-.10, 1.10, letter, transform=ax.transAxes, fontsize=18, fontweight='bold', va='top')
        ax.text(1.03, 1.025, count_label, transform=ax.transAxes, ha='left', va='bottom', fontsize=11)
        for i, (_, row) in enumerate(display.iterrows()):
            n, k = int(row[denominator]), int(row[numerator])
            ax.text(1.03, i, f'{k:,} / {n:,}', transform=ax.get_yaxis_transform(),
                    ha='left', va='center', fontsize=12, clip_on=False)
            if not n:
                value_texts.append(ax.text(maximum * .025, i, 'Not estimable', va='center', fontsize=12))
            elif letter == 'b' and values[i] > 80:
                # End labels stay inside the valid 0-100 percent axis.
                value_texts.append(ax.text(values[i] - 1.5, i, f'{values[i]:.1f}%', va='center',
                                          ha='right', fontsize=12,
                                          color='#17232b' if colors[i] in ['#ccbb44', '#eeaa33'] else 'white',
                                          fontweight='bold'))
            else:
                value_texts.append(ax.text(values[i] + maximum * .018, i, f'{values[i]:.1f}%',
                                          va='center', ha='left', fontsize=12))
    fig.canvas.draw()
    # Verify all count, axis, category and value labels fit the canvas.
    all_text = [t for ax in axes for t in ax.texts + ax.get_yticklabels() + ax.get_xticklabels()]
    all_text += [ax.xaxis.label for ax in axes]
    for t in all_text:
        bbox = t.get_window_extent().transformed(fig.transFigure.inverted())
        assert bbox.x0 >= 0 and bbox.x1 <= 1 and bbox.y0 >= 0 and bbox.y1 <= 1, t.get_text()
    OUT.parent.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=600, facecolor='white')
    fig.savefig(AUDIT / 'preview.png', dpi=100, facecolor='white')
    plt.close(fig)
    display.reset_index().to_csv(AUDIT / 'plotted_data.csv', index=False)
    table.reset_index().to_csv(AUDIT / 'complete_context_summary.csv', index=False)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    caption = (
        'Potential Mismatch by Land Context. Panel a reports candidate meshes as a percentage of '
        'supported comparison meshes within each dominant UMD land context; panel b reports meshes '
        'with valid zero Nighttime Radiance as a percentage of candidates in that context. Adjacent '
        'columns give each exact numerator and denominator. Forest, Shrublands and Grasslands, Urban, '
        'Cropland and Water are displayed. Barren and Incomplete coverage are omitted from this figure '
        'only under MILI-D-20261011-031; all source records and the complete seven-context summary '
        'remain retained. Displayed within-context counts and percentages are unchanged. Percentages '
        'are descriptive; no confidence '
        'interval, significance test or new model is estimated. Both panels use the same 2024 road/light '
        'cross-section and matched 2020 census, with 383,386 cohort meshes, 376,219 supported comparisons '
        'and 66,097 candidates. There are 64,034 valid-zero-radiance candidates. Unavailable screening '
        'is excluded from the panel-a denominator and remains missing in the source. Zero denominators '
        'remain unavailable, never zero percent. All thirty-four Barren-context meshes '
        'lack sufficient peer support, giving zero supported and candidate meshes; neither Barren '
        'percentage is estimable. Incomplete coverage includes 104 cohort meshes, sixty-five supported '
        'meshes and fourteen candidates, so its percentages describe a small sample. Context colors '
        'match Spatial Distribution of Potential Mismatch. The existing peer dimensions, at-least-thirty '
        'distinct-mesh and positive-maximum-radiance support rule, and strict positive-road/Q75 and '
        'inclusive radiance/Q25 comparisons are unchanged under MILI-D-20261011-027. These are '
        'relative mismatch patterns and source-proxy diagnostics. Valid zero radiance does not prove '
        'zero economic activity, and candidates do not identify confirmed excessive or unused roads. '
        'Forest, through-route and essential-access functions remain relevant. UMD context uses largest '
        'full-mesh share with incomplete coverage overriding dominance; observed contexts and source '
        'zeros remain retained. Water-context meshes follow full-mesh footprints and may contain land '
        'and roads. Native UMD shares retain their accepted quality and mask-water handling. Export '
        'is 600 dpi.\n')
    OUT.with_suffix('.caption.md').write_text(caption)
    report = {'status': 'generated_pending_visual_and_human_review', 'human_review': 'pending',
        'title': 'Potential Mismatch by Land Context', 'classification': 'UMD',
        'decision_id': check['decision_id'], 'presentation_decision_id': 'MILI-D-20261011-031',
        'dpi': 600, 'figure_size_inches': [18, 6],
        'panel_labels': ['a', 'b'], 'has_figure_or_panel_titles': False,
        'contexts': display.index.tolist(), 'complete_contexts': table.index.tolist(),
        'display_only_omissions': ['Barren', 'Incomplete coverage'],
        'source_records_and_within_context_denominators_preserved': True,
        'cohort_meshes': len(d), 'supported_meshes': int(supported.sum()),
        'candidate_meshes': int(candidate.sum()), 'candidate_zero_radiance_meshes': 64034,
        'numerator_denominator_columns_shown': True, 'zero_denominators_remain_unavailable': True,
        'barren_support_and_candidate_denominators': [0, 0], 'incomplete_context_counts': [104, 65, 14],
        'direct_mesh_counts_match_screen_summary': True, 'all_label_bounds_inside_canvas': True,
        'source_files_unchanged': True, 'source_hashes': hashes, 'figure_sha256': sha(OUT),
        'script_sha256': sha(Path(__file__))}
    (AUDIT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved: {OUT.relative_to(ROOT)}', flush=True)
    print('Verified: five displayed UMD contexts; full seven-context summary and exact denominators retained; source hashes unchanged.', flush=True)

if __name__ == '__main__':
    main()
