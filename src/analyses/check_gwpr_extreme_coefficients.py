"""Recheck both road-slope extremes and high-condition focused GWPR fits."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import json
import numpy as np
import pandas as pd
from gwpr_multivariate_pooled import MultivariateMoments, RadiusIndex, mesh_centroids, bisquare_weights

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'data/exp/land-cover-poi-extension'


def main():
    contract = json.loads((PLAN / 'gwpr_execution_contract.json').read_text())
    pointer = json.loads((PLAN / 'active_gwpr_extension.json').read_text())
    path = ROOT / pointer['local_coefficients']
    local = pd.read_parquet(path)
    good = local.loc[local['Fit Status'].eq('ok')]
    selected = pd.concat([good.nsmallest(3, 'Road Density Coefficient'),
        good.nlargest(3, 'Road Density Coefficient'), good.nlargest(3, 'Scaled Design Condition')]).drop_duplicates('Mesh Code')
    panel = pd.read_parquet(ROOT / contract['input']).sort_values(['Mesh Code', 'Road Year'])
    codes = panel['Mesh Code'].drop_duplicates().to_numpy()
    values = panel[[contract['outcome']] + contract['explanatory']].to_numpy().reshape(-1, 5, 14)
    engine = MultivariateMoments(values, contract['constant_control_rule'], False)
    coordinates = mesh_centroids(codes)
    index = RadiusIndex(coordinates)
    lookup = {code: i for i, code in enumerate(codes)}
    rows = []
    for row in selected.to_dict('records'):
        focus = lookup[row['Mesh Code']]
        ids, distances = index.query(coordinates[focus], pointer['bandwidth_km'])
        weights = bisquare_weights(distances, pointer['bandwidth_km'])
        fitted = engine.qr_fit(ids, weights)
        assert fitted.status == 'ok'
        reference, anchor, offset, intercept = engine.qr_reference(ids, weights, fitted.active, True)
        columns = np.r_[0, fitted.active+1]
        np.testing.assert_allclose(fitted.beta[columns], reference[columns], rtol=1e-5, atol=1e-7)
        np.testing.assert_allclose(fitted.beta[1], row['Road Density Coefficient'], rtol=1e-12, atol=1e-12)
        prediction = engine.predict(focus, fitted)
        alternate = intercept + ((values[focus, :, 1:][:, fitted.active]-anchor)-offset) @ reference[fitted.active+1]
        np.testing.assert_allclose(prediction, alternate, rtol=1e-6, atol=1e-7)
        rows.append({'Mesh Code': row['Mesh Code'], 'Road Density Coefficient': fitted.beta[1],
            'Scaled Design Condition': fitted.condition, 'Training Meshes': len(ids),
            'Road Density Range': float(np.ptp(values[ids, :, 1])),
            'Maximum Reference Prediction Difference': float(abs(prediction-alternate).max()), 'Reference Passed': True})
    pd.DataFrame(rows).to_csv(path.parent / 'extreme_coefficient_reference_checks.csv', index=False)
    print(f'{len(rows)} extreme/high-condition reference checks passed.', flush=True)


if __name__ == '__main__':
    main()
