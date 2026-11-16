"""Spatial Distribution of Potential Mismatch.

AnaSOP Sections 5-7, comparable-context UMD 2024 screen, unchanged support and
quartile rules. Panel a shows candidate/support states; panel b candidate context.
Reads validated results and draws actual third-order mesh footprints at 600 dpi.
"""
from pathlib import Path
import os
import json
os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from shapely.geometry import shape
from administrative_association_map_helpers import ROOT, OCEAN, boundaries, polygon_patch, polygons, sha
from figure_local_road_associations_across_japan import mesh_vertices
from gwpr_twoways import mesh_centroids

SOURCE = ROOT / 'data/exp/umd-mismatch-screen'
OUT = ROOT / 'data/results/figures/Figure_spatial_distribution_of_potential_mismatch.png'
AUDIT = ROOT / 'data/exp/figure-table-generation/spatial-distribution-of-potential-mismatch'
STATE_COLORS = {'Supported noncandidate': '#edf0f2', 'Screening unavailable': '#737b85',
                'Potential mismatch candidate': '#b2182b'}
OTHER_MESHES = '#edf0f2'
CONTEXT_COLORS = {'Forest': '#228833', 'Shrublands and Grasslands': '#ccbb44', 'Urban': '#cc3311',
                  'Cropland': '#eeaa33', 'Water': '#4477aa', 'Barren': '#a277aa',
                  'Incomplete coverage': '#737b85', 'Tied dominant classes': '#222222'}


def caption_source_hashes():
    paths = ['data/exp/umd-municipal-context/validation.json',
             'data/exp/umd-municipal-context/municipal_evidence_2024.parquet']
    return {path: sha(ROOT / path) for path in paths}

def draw_map(ax, vertices, categories, colors, groups, context):
    views = [ax, ax.inset_axes([.015, .66, .31, .23]), ax.inset_axes([.76, .02, .22, .24])]
    counts = {}
    for view, (xlim, ylim, ref, mask, name) in zip(views, groups):
        view.set_xlim(xlim); view.set_ylim(ylim)
        view.set_aspect(1 / np.cos(np.deg2rad(ref)))
        view.set_facecolor(OCEAN)
        for parts in context:
            visible = [p for p in parts if p.bounds[2] >= xlim[0] and p.bounds[0] <= xlim[1]
                       and p.bounds[3] >= ylim[0] and p.bounds[1] <= ylim[1]]
            if visible:
                view.add_patch(polygon_patch(visible, '#f0f0f0'))
        plotted = 0
        for label, color in colors.items():
            selected = mask & (categories == label)
            plotted += int(selected.sum())
            if selected.any():
                view.add_collection(PolyCollection(vertices[selected], facecolors=color,
                    edgecolors='none', antialiased=False, zorder=3))
        assert plotted == mask.sum()
        assert (vertices[mask, :, 0] >= xlim[0]).all() and (vertices[mask, :, 0] <= xlim[1]).all()
        assert (vertices[mask, :, 1] >= ylim[0]).all() and (vertices[mask, :, 1] <= ylim[1]).all()
        counts[name] = plotted
        view.set_axisbelow(False)
        view.grid(True, color='#687987', linewidth=.45, alpha=.45, linestyle=(0, (2, 3)))
        view.tick_params(labelsize=9, length=2)
        for spine in view.spines.values():
            spine.set_color('#b8bec5'); spine.set_linewidth(.6)
        if view is not ax:
            view.xaxis.set_major_locator(MaxNLocator(2)); view.yaxis.set_major_locator(MaxNLocator(2))
            view.tick_params(labelsize=6, pad=1)
    ax.set_xticks([130, 135, 140, 145]); ax.set_yticks([30, 35, 40, 45])
    ax.set_xlabel('Longitude (°E)', fontsize=11); ax.set_ylabel('Latitude (°N)', fontsize=11)
    return counts

def build_caption(check):
    """Build the current caption after verifying municipal screen provenance."""
    municipal = json.loads((ROOT / 'data/exp/umd-municipal-context/validation.json').read_text())
    assert municipal['status'] == 'passed' and municipal['classification'] == 'UMD'
    assert sha(ROOT / 'data/exp/umd-municipal-context/municipal_evidence_2024.parquet') == municipal['output_sha256']
    assert municipal['source_hashes']['data/exp/umd-mismatch-screen/mesh_screen_2024.parquet'] == check['output_sha256']
    assert municipal['all_candidates'] == check['candidate_meshes']
    fraction = 100 * check['candidate_fraction_supported']
    zero_pct = 100 * check['candidate_zero_radiance_fraction']
    caption = (
        'Spatial Distribution of Potential Mismatch. Panel a locates relative high-road/low-radiance '
        'candidates, supported noncandidates and unavailable screening in 2024. Panel b colors only '
        'the 66,097 candidate meshes by dominant UMD land context; the other 317,289 analytical meshes '
        'remain pale-gray background, including both supported noncandidates and unavailable screening. '
        'The two panels retain the same complete 383,386-mesh footprint. Road and light '
        'years are 2024; matched Population is from 2020. Peer groups are Region, Population band '
        '(0, 1-9, 10-49, 50-199, 200-999, 1000-4999, 5000+), dominant Land Context, presence of any '
        'selected school, medical, logistics or visitor/event facility, and Railway Station distance '
        '(<1 km, 1-<5 km, >=5 km). A peer group is supported if it contains at least thirty distinct '
        'meshes and maximum radiance exceeds zero. A candidate has positive Road Length Density '
        'strictly above its peer 75th percentile and Nighttime Radiance at or below its peer 25th '
        'percentile, using linear-interpolation quartiles. Thresholds and non-land peer bands are '
        'unchanged from the accepted IGBP screening; UMD dominant context and its peer quartiles '
        'are reconstructed under MILI-D-20261011-027. The candidate-only thematic display is selected under '
        'MILI-D-20261011-028; no screening values or candidate identities are changed. Panel b legend '
        'counts refer only to candidates, not whole-cohort land area or within-context candidate rates. '
        'Barren has zero candidates because all thirty-four Barren-context meshes lack peer support; '
        'this is not evidence of no potential mismatch in Barren areas. UMD shares represent Forest (classes 1-5), '
        'Shrublands and Grasslands (6-10), Cropland (12), Urban (13), Water (0) and Barren (15, '
        'including permanent snow/ice). Largest full-mesh share determines context; ties within '
        '1e-12 remain distinct, and incomplete coverage overrides dominance. No tied context is '
        'observed; all 104 incomplete-coverage meshes are retained. '
        f'There are {check["supported_meshes"]:,} supported meshes, {check["candidate_meshes"]:,} '
        f'candidates ({fraction:.2f}% of supported meshes) and {check["unsupported_meshes"]:,} '
        f'unavailable indicators. Of candidates, {check["candidate_zero_radiance_meshes"]:,} '
        f'({zero_pct:.2f}%) have valid numerical zero radiance. These values are retained; they '
        'do not establish zero economic activity. Nighttime Radiance proxies broader economic '
        'activity. Red candidates are relative empirical patterns, not confirmed road overprovision, '
        'unused roads, causal effects or measured maintenance liabilities. Screening is distinct '
        'from the GWPR coefficient surface. Dark gray in panel a indicates unsupported screening; dark gray '
        'in panel b indicates fourteen candidate meshes with incomplete land-cover coverage. Pale gray '
        'in panel b marks other analytical meshes without a thematic context color. Pale blue is ocean, and light gray '
        'land is geographic context outside the analytical cohort. Actual third-order mesh '
        'rectangles measure 1/120 degree latitude by 1/80 degree longitude; no smoothing, '
        'interpolation or additional land mask is applied. Southwest and Ogasawara insets use '
        'separate scales. Four original Minamitorishima meshes with unavailable land cover remain '
        'outside the unchanged extended cohort; source rows are preserved. All-zero-light groups '
        'and fewer-than-thirty-mesh groups are unavailable, never coded as noncandidates. '
        'Current municipal comparisons use the independently validated UMD screen reconciliation '
        'with unchanged government assignments, traffic and fiscal inputs; earlier IGBP municipal '
        'results remain historical provenance. Export is 600 dpi.\n')
    return caption


def refresh_caption():
    """Refresh text only, preserving the previously accepted map and review."""
    check = json.loads((SOURCE / 'validation.json').read_text())
    assert check['status'] == 'passed' and check['classification'] == 'UMD'
    assert sha(SOURCE / 'mesh_screen_2024.parquet') == check['output_sha256']
    audit_path = AUDIT / 'validation.json'
    report = json.loads(audit_path.read_text())
    assert report['status'] == 'accepted' and report['figure_sha256'] == sha(OUT)
    caption = OUT.with_suffix('.caption.md')
    caption.write_text(build_caption(check))
    report.update(caption_sha256=sha(caption), script_sha256=sha(Path(__file__)),
                  caption_source_hashes=caption_source_hashes(),
                  caption_revision_decision_id='MILI-D-20261011-046',
                  caption_revision='Synchronize validated UMD municipal provenance; map unchanged',
                  caption_municipal_validation_sha256=sha(ROOT / 'data/exp/umd-municipal-context/validation.json'))
    audit_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Updated: {caption.relative_to(ROOT)}; accepted map hash unchanged.', flush=True)

def main():
    source = SOURCE / 'mesh_screen_2024.parquet'
    validation = SOURCE / 'validation.json'
    contract = SOURCE / 'screening_contract.json'
    protected = [source, validation, contract]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    check = json.loads(validation.read_text()); rules = json.loads(contract.read_text())
    assert check['status'] == 'passed' and check['classification'] == rules['classification'] == 'UMD'
    assert check['output_sha256'] == sha(source) and not rules['thresholds_changed']
    for path, digest in check['source_hashes'].items():
        assert sha(ROOT / path) == digest
    d = pd.read_parquet(source)
    assert len(d) == check['meshes'] == 383386 and d['Mesh Code'].is_unique
    good = d['Supported Comparison'].to_numpy()
    candidate = d['Potential Mismatch Candidate'].fillna(False).to_numpy(dtype=bool)
    assert np.array_equal(d['Potential Mismatch Candidate'].isna().to_numpy(), ~good)
    assert not (candidate & ~good).any()
    state = np.where(~good, 'Screening unavailable',
                     np.where(candidate, 'Potential mismatch candidate', 'Supported noncandidate'))
    land = d['Land Context'].to_numpy()
    assert set(land).issubset(CONTEXT_COLORS)
    candidate_land = np.where(candidate, land, 'Other analytical meshes')
    candidate_context_counts = {label: int((candidate & (land == label)).sum())
                               for label in CONTEXT_COLORS if label in set(land)}
    assert sum(candidate_context_counts.values()) == check['candidate_meshes']
    lat, lon = d['Latitude'].to_numpy(), d['Longitude'].to_numpy()
    np.testing.assert_allclose(mesh_centroids(d['Mesh Code'].astype(str).to_numpy()),
                               np.column_stack([lat, lon]), atol=1e-12)
    vertices = mesh_vertices(lat, lon)
    groups = [((128., 146.5), (29.95, 46.), 36, lat >= 30, 'Main islands'),
              ((122.5, 132.), (23.7, 30.15), 27, (lat < 30) & (lon < 135), 'Southwest islands'),
              ((140.9, 142.65), (24.5, 27.5), 26, (lat < 30) & (lon >= 135), 'Ogasawara islands')]
    assert np.all(np.stack([g[3] for g in groups]).sum(0) == 1)
    cache, boundary_hashes = boundaries()
    context = [list(polygons(shape(geo))) for geo in cache['prefectures'].values()]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    fig = plt.figure(figsize=(18, 11.5), facecolor='white')
    width = .415
    height = width * 18 / 11.5 * (46 - 29.95) / (146.5 - 128) / np.cos(np.deg2rad(36))
    axes = [fig.add_axes([left, .95 - height, width, height]) for left in [.06, .565]]
    land_colors = {label: color for label, color in CONTEXT_COLORS.items() if label in set(land)}
    candidate_land_colors = {'Other analytical meshes': OTHER_MESHES, **land_colors}
    counts = []
    legends = []
    for label, ax, categories, colors in zip('ab', axes, [state, candidate_land], [STATE_COLORS, candidate_land_colors]):
        counts.append(draw_map(ax, vertices, categories, colors, groups, context))
        ax.text(-.075, 1.035, label, transform=ax.transAxes, fontsize=17, fontweight='bold', va='top')
        if label == 'a':
            order = ['Potential mismatch candidate', 'Supported noncandidate', 'Screening unavailable']
            labels = {x: f'{x} ({int((categories == x).sum()):,})' for x in order}
            labels['Potential mismatch candidate'] = (
                f'High-road / low-radiance candidate ({int(candidate.sum()):,})\n'
                f'{100 * check["candidate_fraction_supported"]:.2f}% of supported meshes')
            ncol = 1
        else:
            order = list(land_colors)
            labels = {x: f'{x} ({candidate_context_counts[x]:,})' for x in order}
            ncol = 2
        handles = [Patch(facecolor=colors[x], label=labels[x]) for x in order]
        legends.append(ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, -.09),
             frameon=False, fontsize=11, ncol=ncol, columnspacing=1.3, handlelength=1.3, labelspacing=.8))
    fig.canvas.draw()
    # Verify the complete legend bounds rather than exporting clipped labels.
    for legend in legends:
        bbox = legend.get_window_extent().transformed(fig.transFigure.inverted())
        assert bbox.x0 >= 0 and bbox.x1 <= 1 and bbox.y0 >= 0 and bbox.y1 <= 1
    assert np.isclose(axes[0].get_position().height, axes[1].get_position().height)
    assert all(sum(c.values()) == len(d) for c in counts)
    OUT.parent.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=600, facecolor='white')
    fig.savefig(AUDIT / 'preview.png', dpi=100, facecolor='white')
    plt.close(fig)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert all(sha(ROOT / name) == digest for name, digest in boundary_hashes.items())
    caption = build_caption(check)
    OUT.with_suffix('.caption.md').write_text(caption)
    report = {'status': 'generated_pending_visual_and_human_review', 'human_review': 'pending',
              'title': 'Spatial Distribution of Potential Mismatch', 'classification': 'UMD',
              'decision_id': check['decision_id'], 'presentation_decision_id': 'MILI-D-20261011-028',
              'dpi': 600, 'figure_size_inches': [18, 11.5],
              'panel_labels': ['a', 'b'], 'has_figure_or_panel_titles': False,
              'mesh_geometry': 'Standard third-order mesh rectangles', 'meshes_per_panel': len(d),
              'panel_geographic_counts': counts, 'state_colors': STATE_COLORS, 'context_colors': land_colors,
              'supported_meshes': int(good.sum()), 'candidate_meshes': int(candidate.sum()),
              'unavailable_meshes': int((~good).sum()), 'contexts': check['contexts'],
              'panel_b_candidate_only_thematic_context': True,
              'panel_b_colored_candidate_meshes': int(candidate.sum()),
              'panel_b_muted_other_meshes': int((~candidate).sum()),
              'panel_b_candidate_context_counts': candidate_context_counts,
              'zero_candidate_contexts_retained_in_legend': True,
              'screening_and_candidate_identities_unchanged': True,
              'identical_panel_map_heights': True, 'complete_legend_bounds_checked': True,
              'one_geographic_view_per_mesh_verified': True, 'source_files_unchanged': True,
              'source_hashes': hashes, 'boundary_source_hashes': boundary_hashes,
              'figure_sha256': sha(OUT), 'script_sha256': sha(Path(__file__)),
              'caption_sha256': sha(OUT.with_suffix('.caption.md')),
              'caption_source_hashes': caption_source_hashes(),
              'caption_municipal_validation_sha256': sha(ROOT / 'data/exp/umd-municipal-context/validation.json')}
    (AUDIT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved: {OUT.relative_to(ROOT)}', flush=True)
    print(f'Verified: {len(d):,} meshes per panel, {int(candidate.sum()):,} candidates; source hashes unchanged.', flush=True)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--caption-only', action='store_true',
                        help='Refresh caption provenance while retaining the accepted PNG')
    args = parser.parse_args()
    refresh_caption() if args.caption_only else main()
