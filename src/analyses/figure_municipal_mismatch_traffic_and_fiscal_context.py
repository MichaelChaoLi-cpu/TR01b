"""Municipal Mismatch, Traffic and Fiscal Context.

Plan: three scatter panels on a 2 x 2 canvas with pair counts, descriptive Spearman
correlations and original-scale, single-predictor OLS dashed fitted lines.
Pearson coefficients and conventional two-sided zero-correlation p values are
reported on the same available pairs, without spatial or multiplicity adjustment.
Framework: AnaSOP Sections 5-7, UMD municipal candidate fractions and unchanged
territorial traffic / own-government FY2023 fiscal references. No causal model.
"""
from pathlib import Path
import os
import json
os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, t as student_t
from reconcile_umd_municipal_context import OUTCOMES, X, sha

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/umd-municipal-context'
OUT = ROOT / 'data/results/figures/Figure_municipal_mismatch_traffic_and_fiscal_context.png'
AUDIT = ROOT / 'data/exp/figure-table-generation/municipal-mismatch-traffic-and-fiscal-context'
Y = [OUTCOMES[0], OUTCOMES[1], OUTCOMES[3]]

def format_p(value):
    """Use the user-selected 0.1-percent threshold for small p values."""
    assert 0 < value <= 1, 'A valid positive p value is required for this display.'
    if value < .001:
        return 'p < 0.1%'
    return f'p = {value:.3f}'

def main():
    source = SOURCE / 'municipal_evidence_2024.parquet'
    validation = SOURCE / 'validation.json'
    corr_path = SOURCE / 'municipal_context_rank_correlations.csv'
    protected = [source, validation, corr_path]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    check = json.loads(validation.read_text())
    assert check['status'] == 'passed' and check['classification'] == 'UMD'
    assert check['output_sha256'] == sha(source) and check['correlation_sha256'] == sha(corr_path)
    for path, digest in check['source_hashes'].items():
        assert sha(ROOT / path) == digest
    d = pd.read_parquet(source)
    cor = pd.read_csv(corr_path)
    assert len(d) == check['municipal_governments'] == 1741 and d['Government Code'].is_unique
    assert d['Fiscal Year'].eq(2023).all() and d['Traffic Year'].eq(2021).all()
    assert d['Road Year'].eq(2024).all() and d['Population Year'].eq(2020).all()
    assert d[X].dropna().between(0, 1).all()
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig = plt.figure(figsize=(16, 12), facecolor='white')
    # Three existing outcomes occupy a two-by-two canvas; the fourth slot is empty.
    axes = [fig.add_axes(bounds) for bounds in
            [[.09, .585, .36, .32], [.59, .585, .36, .32], [.09, .10, .36, .32]]]
    labels = ['Surveyed traffic (vehicles / 24 h)', 'Road + bridge maintenance /\ntotal expenditure (%)',
              'Standard fiscal revenue /\nstandard fiscal need']
    x_max = max(10., float(np.ceil(100 * d[X].max() / 10) * 10))
    entries = []
    pairs_export = []
    colors = ['#2166ac', '#1a9850', '#7b3294']
    for letter, ax, outcome, ylabel, color in zip('abc', axes, Y, labels, colors):
        pairs = d[['Government Code', 'Government Name', X, outcome]].replace([np.inf, -np.inf], np.nan).dropna(subset=[X, outcome])
        x = pairs[X].to_numpy() * 100
        y = pairs[outcome].to_numpy() * (100 if outcome == OUTCOMES[1] else 1)
        stat = cor.loc[cor['Scope'].eq('All municipal governments') & cor['Outcome'].eq(outcome)].iloc[0]
        assert len(pairs) == stat['Municipalities']
        # Verify each plotted pairing and descriptive correlation independently.
        rx, ry = [pairs[c].rank(method='average').to_numpy(copy=True) for c in [X, outcome]]
        rx -= rx.mean(); ry -= ry.mean()
        rho = (rx @ ry) / np.sqrt((rx @ rx) * (ry @ ry))
        np.testing.assert_allclose(rho, stat['Spearman'], atol=1e-12, rtol=1e-12)
        ax.scatter(x, y, s=18, alpha=.35, color=color, edgecolors='none', zorder=3)
        design = np.column_stack([np.ones(len(x)), x])
        coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
        assert rank == 2
        # Independent centered-moment calculation verifies the displayed OLS fit.
        centered_x, centered_y = x - x.mean(), y - y.mean()
        pearson = pearsonr(x, y, alternative='two-sided')
        r, p_value = float(pearson.statistic), float(pearson.pvalue)
        independent_r = (centered_x @ centered_y) / np.sqrt(
            (centered_x @ centered_x) * (centered_y @ centered_y))
        np.testing.assert_allclose(r, independent_r, atol=1e-12, rtol=1e-12)
        t_stat = independent_r * np.sqrt((len(x) - 2) / (1 - independent_r ** 2))
        independent_p = float(2 * student_t.sf(abs(t_stat), df=len(x) - 2))
        np.testing.assert_allclose(p_value, independent_p, atol=0, rtol=1e-9)
        assert np.isfinite(p_value) and 0 < p_value <= 1
        slope = (centered_x @ centered_y) / (centered_x @ centered_x)
        intercept = y.mean() - slope * x.mean()
        np.testing.assert_allclose(coef, [intercept, slope], atol=1e-10, rtol=1e-10)
        residual = y - design @ coef
        np.testing.assert_allclose(residual.mean(), 0, atol=1e-9)
        fit_x = np.linspace(x.min(), x.max(), 200)
        fit_y = coef[0] + coef[1] * fit_x
        ax.plot(fit_x, fit_y, color='#252525', linewidth=2.2,
                linestyle=(0, (6, 4)), zorder=4)
        ax.set_xlim(-.02 * x_max, 1.05 * x_max)
        ax.set_xticks(np.arange(0, x_max + 1, 10))
        if outcome == OUTCOMES[0]:
            ax.set_yticks(np.arange(-10000, 50001, 10000))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:,.0f}'))
        # Retain the complete fitted line even when unconstrained OLS predicts
        # beyond the outcome's natural range; do not clip or constrain the fit.
        lower = min(0., float(y.min()), float(fit_y.min()))
        upper = max(float(y.max()), float(fit_y.max()))
        span = upper - lower
        ax.set_ylim(lower - .025 * span, upper + .07 * span)
        xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
        assert ((x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)).all()
        ax.set_axisbelow(True)
        ax.grid(True, which='major', color='#dfe4e8', linewidth=.7)
        ax.set_xlabel('Potential mismatch among supported meshes (%)', fontsize=11, labelpad=10)
        ax.set_ylabel(ylabel, fontsize=12, labelpad=12)
        ax.tick_params(labelsize=11)
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']:
            ax.spines[spine].set_color('#a7afb7')
        ax.text(-.11, 1.10, letter, transform=ax.transAxes, fontsize=18, fontweight='bold', va='top')
        annotation = (f'n = {len(pairs):,}\nSpearman ρ = {rho:+.3f}\n'
                      f'Pearson r = {r:+.3f}\n{format_p(p_value)}')
        ax.text(.97, .965, annotation, transform=ax.transAxes,
                ha='right', va='top', fontsize=12, color='black',
                bbox={'facecolor': 'white', 'alpha': .85, 'edgecolor': 'none', 'pad': 3})
        entry = {'panel': letter, 'outcome': outcome, 'paired_governments': len(pairs), 'spearman': float(rho),
                 'pearson': r, 'pearson_two_sided_p': p_value,
                 'pearson_p_display': format_p(p_value),
                 'pearson_reference_test': {'null': 'zero Pearson correlation',
                         'assumptions': 'independent bivariate-normal pairs',
                         'spatial_adjustment': False, 'multiple_comparison_adjustment': False,
                         'independent_t_reference_check': 'passed'},
                 'missing_pairs': len(d) - len(pairs), 'y_display_scale': 'linear',
                 'fit': {'method': 'OLS with intercept, unweighted', 'x_units': 'percentage points',
                         'y_units': ylabel.replace('\n', ' '), 'response_scale': 'original',
                         'intercept': float(coef[0]), 'slope_per_percentage_point': float(coef[1]),
                         'x_range': [float(x.min()), float(x.max())],
                         'predicted_endpoint_values': [float(fit_y[0]), float(fit_y[-1])],
                         'independent_centered_moment_check': 'passed'},
                 'all_points_inside_axes': True, 'zero_outcome_values_retained': int((y == 0).sum())}
        entries.append(entry)
        pairs_export.append(pairs.assign(Panel=letter, Outcome=outcome).rename(columns={outcome: 'Outcome Value'}))
    fig.canvas.draw()
    for ax in axes:
        text_items = ax.texts + [ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels()
        for t in text_items:
            if not t.get_visible():
                continue
            bbox = t.get_window_extent().transformed(fig.transFigure.inverted())
            assert bbox.x0 >= 0 and bbox.x1 <= 1 and bbox.y0 >= 0 and bbox.y1 <= 1, t.get_text()
    OUT.parent.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=600, facecolor='white')
    fig.savefig(AUDIT / 'preview.png', dpi=100, facecolor='white')
    plt.close(fig)
    pd.concat(pairs_export, ignore_index=True).to_parquet(AUDIT / 'plotted_pairs.parquet', index=False)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    caption = (
        'Municipal Mismatch, Traffic and Fiscal Context. Each point is an individual municipal financial '
        'government (city, town, village or Tokyo special ward); designated-city administrative wards '
        'are consolidated to the financial parent. The horizontal axis is the percentage of assigned '
        'supported UMD comparison meshes that are potential mismatch candidates. Panel a shows '
        'segment-length-weighted surveyed twenty-four-hour traffic in the territory; panel b own-government '
        'road-plus-bridge maintenance spending as a percentage of total expenditure; panel c the '
        'single-year standard fiscal revenue/need ratio. Panels report pairwise available counts and '
        'unadjusted descriptive Spearman correlations, Pearson correlations and conventional '
        'two-sided Pearson p values for the null of zero linear correlation. Pearson tests assume '
        'independent bivariate-normal pairs and are not adjusted for spatial dependence or multiple '
        'comparisons; p values do not refer to Spearman coefficients. Values below 0.1 percent '
        'are displayed as p < 0.1%; exact computed values remain in the verification record. '
        'Small p values do not establish '
        'large associations or causality. Black dashed lines show unweighted, '
        'single-predictor OLS fits with an intercept on each panel\'s available pairs, using original '
        'outcome values. Fits span the observed predictor range, without controls, confidence bands '
        'or separate fitted-line tests. The unconstrained traffic and fiscal-resource lines fall below zero '
        'at the high end of candidate fractions; these segments expose the limits of the linear '
        'summary and are not plausible outcome predictions. The three panels occupy a two-by-two '
        'layout with the fourth slot empty. '
        'Road/light and land context use 2024, Population 2020, surveyed traffic 2021 and actual fiscal '
        'year 2023. Municipal mesh allocation and government consolidation are unchanged. The '
        '383,386-mesh ledger retains 320 unavailable government links; '
        f'{check["unlinked_candidate_meshes"]} candidate meshes lack such links and are not reassigned. '
        f'There are {check["linked_candidates"]:,} linked candidates from 66,097 national candidates. '
        'All source fiscal values and traffic references agree with the previously verified inputs. '
        'Missing traffic stays missing, and each panel uses its available outcome/predictor pairs. '
        'All axes are linear and all finite outcome values are retained. Candidate and maintenance '
        'fractions are displayed as percentages, with source '
        'values unchanged. Zero maintenance values and all finite extreme values remain included. '
        'No smoothing, jitter, outcome trimming or new control is introduced. Contexts omitted from '
        'the previous bar figure remain part of this overall municipal aggregation. Surveyed traffic '
        'primarily covers major roads and does not measure all ordinary municipal roads. Territorial '
        'traffic and own-government fiscal spending are not matched by road ownership. Realized '
        'maintenance spending does not measure required or deferred maintenance, nor costs attributable '
        'to flagged roads. Tokyo special wards retain their distinct fiscal arrangement. These '
        'cross-sectional associations provide transport and fiscal context; they do not establish '
        'road overprovision, causality or a measured fiscal effect of candidate road stock. Export '
        'is 600 dpi.\n')
    OUT.with_suffix('.caption.md').write_text(caption)
    report = {'status': 'generated_pending_visual_and_human_review', 'human_review': 'pending',
        'title': 'Municipal Mismatch, Traffic and Fiscal Context', 'classification': 'UMD',
        'decision_id': 'MILI-D-20261011-036', 'dpi': 600, 'figure_size_inches': [16, 12],
        'layout': '2 x 2, bottom-right slot empty',
        'panel_labels': ['a', 'b', 'c'], 'has_figure_or_panel_titles': False,
        'municipal_governments': len(d), 'panels': entries,
        'same_x_axis_limits': True, 'source_values_unchanged': True, 'source_hashes': hashes,
        'figure_sha256': sha(OUT), 'script_sha256': sha(Path(__file__)),
        'all_label_bounds_inside_canvas': True, 'descriptive_original_scale_ols_lines': True,
        'no_causal_inference': True}
    (AUDIT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved: {OUT.relative_to(ROOT)}', flush=True)
    print(json.dumps(entries, indent=2), flush=True)

if __name__ == '__main__':
    main()
