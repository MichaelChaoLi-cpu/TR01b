"""Focused numerical checks of the UMD nuisance-basis estimator."""
from pathlib import Path
import json
import numpy as np
from gwpr_umd_identified import fit, predict, expanded_reference


def main():
    rng = np.random.default_rng(42)
    g, t = 80, 5
    core = rng.normal(size=(g*t, 2))
    a, b = rng.normal(size=(2, g*t))
    x = np.column_stack([core, a, b, a+2*b, np.ones(g*t)])
    y = x[:, :4]@np.array([.7, -.3, 1.2, -.4])+rng.normal(scale=.05, size=g*t)
    raw = np.column_stack([y, x]); weights = rng.uniform(.05, 1, g)
    fitted = fit(raw, weights)
    assert fitted.status == 'ok' and 4 in fitted.redundant and 5 in fitted.constant
    assert np.isnan(fitted.beta[[5, 6]]).all()
    prediction = predict(x, fitted)
    reference, slopes = expanded_reference(raw, weights, fitted)
    np.testing.assert_allclose(prediction, reference, rtol=1e-9, atol=1e-9)
    xx = np.column_stack([np.ones(g*t), x]); root = np.repeat(np.sqrt(weights), t)
    beta = np.linalg.lstsq(xx*root[:, None], y*root, rcond=None)[0]
    np.testing.assert_allclose(beta[1:3], fitted.beta[1:3], rtol=1e-8, atol=1e-8)
    changed = x[:5].copy(); changed[:, 4] += .1
    assert predict(changed, fitted) is None
    aliased = raw.copy(); aliased[:, 3] = aliased[:, 1]
    assert fit(aliased, weights).status == 'failed'
    constant = raw.copy(); constant[:, 2] = 0
    assert fit(constant, weights).status == 'failed'
    report = dict(status='passed', seed=42, omitted_control_coefficients_nan=True,
        full_rank_deficient_design_core_equivalence=True, expanded_wls_equivalence=True,
        heldout_affine_departure_rejected=True, nuisance_aliased_core_rejected=True,
        constant_mandatory_population_rejected=True,
        maximum_prediction_difference=float(abs(reference-prediction).max()),
        maximum_core_coefficient_difference=float(abs(beta[1:3]-fitted.beta[1:3]).max()))
    path = Path(__file__).resolve().parents[2]/'data/exp/umd-four-layer/estimator_validation.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
