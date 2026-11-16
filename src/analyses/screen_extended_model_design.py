"""Check proposed control sets at current validation centers; estimate no model."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import json
import numpy as np
import pandas as pd
from gwpr_pooled import RadiusIndex, mesh_centroids, bisquare_weights

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/estimation-framework-planning/land-cover-poi-extension'
FOCUSED = ['Distance to Railway Station', 'Distance to Passenger Airport',
           'School Facility Count', 'Medical Facility Count',
           'Logistics Facility Count', 'Visitor and Event Facility Count']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pointer = json.loads((ROOT / 'data/exp/data-preprocessing/active_panel.json').read_text())
    groups = json.loads((ROOT / 'data/exp/data-briefing/modis-water-retained-missingness/summary.json').read_text())['groups']
    land = [c for c in groups['land_cover'] if c != 'Other Land Cover Share']
    totals = FOCUSED[2:]
    broad = totals + groups['existing_facilities'][-6:] + groups['additional_ksj']
    assert len(broad) == 28 and len(set(broad)) == 28
    base = pd.read_parquet(ROOT / pointer['active_baseline_panel'], columns=['Mesh Code', 'Road Year', 'Road Length Density', 'Population']).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = base['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    source = ROOT / pointer['core_balanced_panel']
    annual = pd.read_parquet(source, columns=['Mesh Code', 'Road Year'] + land, filters=[('Mesh Code', 'in', codes.tolist())]).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    for key in ['Mesh Code', 'Road Year']:
        assert np.array_equal(base[key].to_numpy(), annual[key].to_numpy())
    static = pd.read_parquet(source, columns=['Mesh Code'] + broad, filters=[('Road Year', '==', 2024), ('Mesh Code', 'in', codes.tolist())]).sort_values('Mesh Code').reset_index(drop=True)
    assert np.array_equal(static['Mesh Code'].to_numpy(), codes)
    annual_values = np.column_stack([base[['Road Length Density', 'Population']].to_numpy(float), annual[land].to_numpy(float)]).reshape(len(codes), 5, -1)
    centers = pd.read_csv(ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km/validation_centers_input.csv', dtype={'Mesh Code': str})
    coordinates = mesh_centroids(codes)
    index, positions = RadiusIndex(coordinates), {code: i for i, code in enumerate(codes)}
    records = []
    for label, controls in [('focused_6_poi', FOCUSED), ('broad_28_poi', broad)]:
        sv = static[controls].to_numpy(float)
        names = ['Road Length Density', 'Population'] + land + controls
        for code in centers['Mesh Code']:
            ids, distance = index.query(coordinates[positions[code]], 3.)
            weights = bisquare_weights(distance, 3.)
            positive = weights > 0
            ids, weights = ids[positive], weights[positive]
            x = np.concatenate([annual_values[ids], np.repeat(sv[ids, None, :], 5, axis=1)], axis=2).reshape(-1, len(names))
            w = np.repeat(weights, 5)
            finite = np.isfinite(x).all()
            constant_names = []
            rank, minimum_eigenvalue = 0, None
            if finite and len(x):
                constant = np.ptp(x, axis=0) == 0
                constant_names = np.array(names)[constant].tolist()
                mu = np.average(x, weights=w, axis=0)
                centered = (x - mu) * np.sqrt(w[:, None])
                varying = ~constant
                if varying.any():
                    z = centered[:, varying]
                    z /= np.sqrt(np.einsum('ij,ij->j', z, z))
                    eigenvalues = np.linalg.eigvalsh(z.T @ z)
                    rank = 1 + int((eigenvalues > 1e-12).sum())
                    minimum_eigenvalue = float(eigenvalues.min())
                else:
                    rank = 1
            records.append({'Mesh Code': code, 'Proposal': label, 'Bandwidth km': 3., 'Local Meshes': len(ids), 'Local Records': len(x), 'Parameters': len(names) + 1, 'Finite Design': bool(finite), 'Constant Predictors': '; '.join(constant_names), 'Scaled Rank': rank, 'Minimum Scaled Eigenvalue': minimum_eigenvalue, 'Full Rank': bool(finite and rank == len(names) + 1)})
    frame = pd.DataFrame(records)
    frame.to_csv(OUT / 'proposed_local_design_support_3km.csv', index=False)
    report = {'status': 'passed', 'statistical_models_estimated': False, 'final_control_subset_selected': False, 'sample_selection_changed': False,
              'reference_land_cover_proposal': 'Other Land Cover Share', 'land_cover_controls_proposal': land,
              'focused_poi_controls_proposal': FOCUSED, 'broad_poi_controls_proposal': broad,
              'scope': 'Existing validation centers, focal mesh included; this is not a national full-fit coverage estimate.',
              'by_proposal': {key: {'parameters': int(part['Parameters'].iloc[0]), 'centers': len(part), 'full_rank_centers': int(part['Full Rank'].sum()), 'centers_with_constant_predictors': int(part['Constant Predictors'].ne('').sum()), 'nonfinite_design_centers': int((~part['Finite Design']).sum())} for key, part in frame.groupby('Proposal')}}
    (OUT / 'design_screening.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'README.md').write_text('# Proposed land-cover and POI extension\n\n'
        'Reproduce with `python3 src/analyses/screen_extended_model_design.py`. These are proposals, not approved specifications. '
        'All data and existing regression outputs are preserved. The six land-cover categories remain in data; the proposed equation includes five shares with Other Land Cover Share as reference. '
        'Shares partition accepted coverage; incomplete-coverage records remain flagged, without normalization or imputation. '
        'Facility snapshots retain the already approved replication across five periods and their original source vintages. '
        'The broad proposal uses totals instead of their overlapping categories; the focused proposal uses two transport distances and four facility totals. '
        'Screening evaluates weighted design rank at the existing validation centers at 3 km, with all focal observations included. '
        'No coefficients, significance tests or new bandwidth optimum are estimated. Constant predictors are reported rather than dropped. '
        'Exact controls and treatment of the four meshes with unavailable land-cover data await human selection.\n')
    print(json.dumps(report['by_proposal'], indent=2), flush=True)


if __name__ == '__main__':
    main()
