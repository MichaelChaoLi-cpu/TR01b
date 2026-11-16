#!/usr/bin/env python3
"""Verify pooled local moments against expanded weighted least squares.

Synthetic coefficient checks, held-out-group isolation, weight invariances,
and exact radius-index checks. No empirical bandwidth is selected here.
"""
from pathlib import Path
import json
import numpy as np
from gwpr_pooled import PooledMoments, RadiusIndex, bisquare_weights, great_circle_km

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/estimation-framework-planning/gwpr-pooled-population-zero-corrected'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261010)
    x = rng.uniform(.1, 20, (16, 4))
    p = rng.uniform(0, 3000, (16, 4))
    y = 2 + .6*x + .002*p + rng.normal(0, .3, (16, 4))
    values = np.stack([y, x, p], axis=2)
    engine = PooledMoments(values)
    ids = np.arange(16)
    weights = np.r_[0, np.linspace(1, .01, 15)]
    fit = engine.fit(ids, weights)
    assert fit.status == 'ok'
    reference = engine.qr_reference(ids, weights)
    np.testing.assert_allclose(fit.beta, reference, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(fit.beta, engine.fit(ids, weights*9).beta, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(fit.beta, engine.fit(ids[1:], weights[1:]).beta, rtol=1e-10, atol=1e-10)
    changed = values.copy(); changed[0, :, 0] += 10000
    np.testing.assert_array_equal(fit.beta, PooledMoments(changed).fit(ids, weights).beta)
    equal = engine.fit(ids, np.ones(16))
    np.testing.assert_allclose(equal.beta, engine.qr_reference(ids, np.ones(16)), rtol=1e-10, atol=1e-10)
    constant_population = values.copy(); constant_population[:, :, 2] = 0
    failure = PooledMoments(constant_population).fit(ids, weights)
    assert failure.status == 'failed' and failure.rank == 2 and np.isnan(failure.beta).all()
    coordinates = np.column_stack([rng.uniform(33, 44, 300), rng.uniform(130, 142, 300)])
    coordinates[1] = coordinates[0] + [.001, .001]
    index = RadiusIndex(coordinates)
    checks = []
    for focal in [0, 30, 150, 299]:
        for radius in [3., 4., 50.]:
            ids, distance = index.query(coordinates[focal], radius, exclude=focal)
            brute = great_circle_km(coordinates[focal], coordinates)
            expected = np.flatnonzero((brute < radius) & (np.arange(len(coordinates)) != focal))
            np.testing.assert_array_equal(ids, expected)
            np.testing.assert_allclose(distance, brute[ids], atol=1e-12)
            checks.append({'focal': focal, 'radius_km': radius, 'neighbors': len(ids)})
    np.testing.assert_array_equal(bisquare_weights(np.array([0., 3., 4.]), 3.), np.array([1., 0., 0.]))
    report = dict(status='passed', model='Pooled intercept and two slopes; no fixed effects', synthetic_seed=20261010,
                  expanded_wls_max_coefficient_difference=float(np.max(abs(fit.beta-reference))),
                  equal_weight_ols_equivalence=True, weight_scaling_invariance=True, zero_weight_exclusion_invariance=True,
                  held_out_group_outcome_isolation=True, constant_population_rank_failure_flagged=True,
                  radius_index_matches_brute_force=True, strict_kernel_boundary_verified=True,
                  radius_checks=checks, empirical_bandwidth_selected=False)
    (OUT / 'design_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
