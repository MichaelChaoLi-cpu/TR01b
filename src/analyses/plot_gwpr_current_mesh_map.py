"""Exploratory national road-coefficient map drawn with actual mesh polygons.

Run after run_gwpr_local_3km.py. PNG is the preview; vector
PDF preserves each mesh for zooming. Insets do not discard remote islands.
"""
from pathlib import Path
import hashlib
import json
import os

os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import TwoSlopeNorm
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/local-fit-3km'
OUT = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/mesh-map-3km'
BOUNDARY = ROOT / 'data/exp/gwpr-twoways/map_reference_lines.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def mesh_vertices(lat, lon):
    # Third-order Japanese standard mesh: 30 arcseconds N/S, 45 E/W.
    vertices = np.empty((len(lat), 4, 2))
    vertices[:, :, 0] = lon[:, None] + np.array([-1, 1, 1, -1])[None, :]/160
    vertices[:, :, 1] = lat[:, None] + np.array([-1, -1, 1, 1])[None, :]/240
    return vertices


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = INPUT_DIR / 'local_coefficients.parquet'
    before = sha(source)
    fit = json.loads((INPUT_DIR / 'local_fit_validation.json').read_text())
    assert fit['status'] == 'passed' and before == fit['output_sha256'] and fit['bandwidth_km'] == 3
    data = pd.read_parquet(source)
    lat, lon = data['Latitude'].to_numpy(), data['Longitude'].to_numpy()
    good = data['Fit Status'].eq('ok').to_numpy()
    low = data['Below 30 Observations'].to_numpy()
    beta = data['Road Density Coefficient'].to_numpy()
    assert len(data) == fit['meshes'] == 383390 and data['Mesh Code'].is_unique
    assert int(good.sum()) == fit['estimable_meshes']
    from gwpr_twoways import mesh_centroids
    assert np.allclose(mesh_centroids(data['Mesh Code'].astype(str).to_numpy()),np.column_stack([lat,lon]),atol=1e-12)
    assert np.isfinite(beta[good]).all() and np.isnan(beta[~good]).all()
    assert np.array_equal(low, data['Local Observations'].to_numpy() < 30)
    vertices = mesh_vertices(lat, lon)
    assert np.allclose(vertices[:, :, 0].max(1)-vertices[:, :, 0].min(1), 1/80, atol=1e-12)
    assert np.allclose(vertices[:, :, 1].max(1)-vertices[:, :, 1].min(1), 1/120, atol=1e-12)
    assert np.allclose(vertices.mean(1), np.column_stack([lon, lat]), atol=1e-12)
    limit = float(np.quantile(abs(beta[good]), .98))
    assert limit > 0
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    cmap = plt.get_cmap('RdBu_r')
    boundary = json.loads(BOUNDARY.read_text())
    context = []
    for ring in boundary['lines']:
        v = np.asarray(ring, dtype=float)
        area = abs(np.sum(v[:-1, 0]*v[1:, 1]-v[1:, 0]*v[:-1, 1]))/2
        if area > .0001:
            context.append((v, v.min(0), v.max(0)))

    groups = [
        {'name': 'Main islands', 'mask': lat >= 30, 'position': [.045, .155, .65, .745],
         'xlim': (128., 146.5), 'ylim': (29.95, 46.), 'reference_lat': 36},
        {'name': 'Southwest islands', 'mask': (lat < 30) & (lon < 135), 'position': [.735, .655, .245, .245],
         'xlim': (122.5, 132.), 'ylim': (23.7, 30.1), 'reference_lat': 27},
        {'name': 'Ogasawara islands', 'mask': (lat < 30) & (lon >= 135) & (lon < 147),
         'position': [.73, .275, .145, .325], 'xlim': (140.9, 142.65), 'ylim': (24.5, 27.4), 'reference_lat': 26},
        {'name': 'Minamitorishima', 'mask': lon >= 147, 'position': [.893, .39, .085, .14],
         'xlim': (153.94, 154.02), 'ylim': (24.24, 24.34), 'reference_lat': 24},
    ]
    assert np.all(np.stack([g['mask'] for g in groups]).sum(0) == 1)
    fig = plt.figure(figsize=(14, 12), facecolor='white')
    fig.text(.045, .96, 'Road-density association with nighttime activity', fontsize=19, weight='bold')
    fig.text(.045, .931, 'Local pooled regression  |  3 km selected within 3-50 km  |  Five periods, 2002-2024', fontsize=11, color='#555555')
    fig.text(.98, .931, 'Exploratory mesh map', fontsize=10, ha='right', color='#555555')
    panel_counts = {}
    for g in groups:
        mask = g['mask']
        ax = fig.add_axes(g['position'])
        ax.set_facecolor('#fbfcfe')
        ax.set_xlim(g['xlim']); ax.set_ylim(g['ylim'])
        ax.set_aspect(1/np.cos(np.deg2rad(g['reference_lat'])))
        nearby = [v for v, lo, hi in context if hi[0] >= g['xlim'][0] and lo[0] <= g['xlim'][1]
                  and hi[1] >= g['ylim'][0] and lo[1] <= g['ylim'][1]]
        if nearby:
            ax.add_collection(PolyCollection(nearby, facecolors='#eeeeee', edgecolors='#bbbbbb', linewidths=.17, zorder=0))
        bad_here, good_here = mask & ~good, mask & good
        ax.add_collection(PolyCollection(vertices[bad_here], facecolors='#717780', edgecolors='none', zorder=2))
        ax.add_collection(PolyCollection(vertices[good_here], facecolors=cmap(norm(beta[good_here])), edgecolors='none', zorder=3))
        ax.add_collection(PolyCollection(vertices[mask & low], facecolors='none', edgecolors='#ca8200', linewidths=.40, zorder=4))
        ax.set_title(g['name'], loc='left', fontsize=11, pad=8)
        ax.tick_params(labelsize=8, length=3)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.yaxis.set_major_locator(MaxNLocator(4))
        if g['name'] == 'Main islands':
            ax.set_xlabel('Longitude (degrees east)', fontsize=9)
            ax.set_ylabel('Latitude (degrees north)', fontsize=9)
        if g['name'] == 'Minamitorishima':
            ax.tick_params(labelsize=6)
            ax.ticklabel_format(useOffset=False)
            ax.xaxis.set_major_locator(MaxNLocator(2))
            ax.yaxis.set_major_locator(MaxNLocator(3))
        for spine in ax.spines.values():
            spine.set_color('#c4c9d0'); spine.set_linewidth(.7)
        assert np.all(vertices[mask, :, 0] >= g['xlim'][0]) and np.all(vertices[mask, :, 0] <= g['xlim'][1])
        assert np.all(vertices[mask, :, 1] >= g['ylim'][0]) and np.all(vertices[mask, :, 1] <= g['ylim'][1])
        panel_counts[g['name']] = int(mask.sum())
    cax = fig.add_axes([.10, .092, .53, .019])
    bar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', extend='both')
    bar.solids.set_rasterized(False)
    bar.set_label('Road-density coefficient (radiance units per km/km²)', fontsize=10, labelpad=5)
    bar.ax.tick_params(labelsize=9)
    legend = [Patch(facecolor='#717780', label='Non-estimable'),
              Patch(facecolor='white', edgecolor='#ca8200', linewidth=1, label='Below 30 observation records'),
              Patch(facecolor='#eeeeee', edgecolor='#bbbbbb', label='Land background; no panel estimate')]
    fig.legend(handles=legend, loc='lower left', bbox_to_anchor=(.725, .155), frameon=False, fontsize=9)
    fig.text(.73, .25, 'Island panels use separate map scales.', fontsize=9, color='#555555')
    fig.text(.045, .031, f'{len(data):,} meshes retained; {int(good.sum()):,} estimable. '
             f'Colors saturate at ±{limit:.3f} (98th percentile of |coefficient|); numerical estimates are unchanged.', fontsize=9, color='#555555')
    fig.text(.045, .014, 'Actual mesh extents, without interpolation. Blue: negative; red: positive. '
             'Population controlled; no fixed effects or significance claim.', fontsize=9, color='#555555')
    png, pdf = OUT / 'road_density_coefficient_mesh_map.png', OUT / 'road_density_coefficient_mesh_map.pdf'
    fig.savefig(png, dpi=260, facecolor='white')
    fig.savefig(pdf, facecolor='white', metadata={'Title': 'Exploratory pooled GWPR road-density mesh map, 3 km'})
    plt.close(fig)
    assert sha(source) == before
    report = {'status': 'generated_pending_visual_review', 'mesh_geometry': 'Actual standard third-order rectangles: 1/120 degree latitude by 1/80 degree longitude',
              'polygons_shown': len(data), 'one_panel_per_mesh_verified': True, 'all_meshes_inside_plot_limits': True,
              'panel_mesh_counts': panel_counts, 'effects': [], 'bandwidth_km': 3, 'local_fit_decision_id': fit['local_fit_decision_id'],
              'map_decision_id': 'MILI-D-20261010-030', 'source': str(source.relative_to(ROOT)),
              'estimable_meshes': int(good.sum()), 'non_estimable_meshes': int((~good).sum()),
              'below_30_observation_meshes': int(low.sum()), 'below_30_coefficients_not_filtered': True,
              'color_limit_absolute_98th_percentile': limit, 'color_clipped_meshes': int((abs(beta[good]) > limit).sum()),
              'coefficient_values_unmodified': True, 'source_sha256': before,
              'boundary_sha256': sha(BOUNDARY), 'boundary_source': boundary['source'],
              'boundary_role': 'Illustrative only; no land or estimation mask', 'boundary_date': boundary['boundary_date'],
              'background_minimum_polygon_area_degrees_squared': .0001,
              'no_significance_map': True, 'outputs': {p.name: sha(p) for p in [png, pdf]}}
    (OUT / 'map_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    (OUT / 'README.md').write_text(
        '# Exploratory current GWPR road-density mesh map\n\n'
        'Reproduce `python3 src/analyses/plot_gwpr_current_mesh_map.py` after '
        '`python3 src/analyses/run_gwpr_local_3km.py`.\n\n'
        f"All {len(data):,} common-cohort meshes are represented; {int(good.sum()):,} are estimable. "
        'Five periods: 2002, 2003, 2004, 2010 and 2024. Original-scale weighted pooled regression '
        'with intercept, Road Length Density and Population, no fixed effects. The selected fixed '
        'bisquare radius is 3 km, the lower boundary of the user-approved 3-50 km search. '
        'Selection is approximate and conditional on common estimable validation support.\n\n'
        'Draw actual standard third-order mesh rectangles, without interpolation or a new land mask. '
        'All southwest, Ogasawara and Minamitorishima sample cells are included in separate-scale insets. '
        'Red means a positive road coefficient, blue negative, white near zero; dark gray means '
        'non-estimable, not zero. Orange outlines identify fewer than thirty five-period records; '
        'estimable flagged coefficients are retained. Light gray land is illustrative boundary context '
        'and does not introduce estimated values.\n\n'
        f"The diverging scale is centered on zero and saturates at +/-{limit:.6f}, the 98th percentile "
        'of absolute estimable road coefficients. Only displayed colors saturate; numerical coefficients '
        'and source parquet remain unchanged. The figure shows conditional coefficient magnitude, '
        'not local statistical significance or a causal effect. PNG is the preview; vector PDF '
        'retains the mesh polygons for closer inspection.\n')
    print('Saved mesh preview:', png.relative_to(ROOT), flush=True)
    print('Saved vector PDF:', pdf.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    main()
