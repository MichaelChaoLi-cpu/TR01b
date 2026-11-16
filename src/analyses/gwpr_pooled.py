"""Geographically weighted pooled panel least squares, without fixed effects.

Weights are constant over a mesh's four observations. Sufficient statistics
yield the intercept and two slopes equivalent to expanded weighted OLS.
"""
from dataclasses import dataclass
import numpy as np

from gwpr_twoways import RadiusIndex, mesh_centroids, bisquare_weights, great_circle_km

MIN_SCALED_EIGENVALUE = 1e-12


@dataclass
class PooledFit:
    status: str
    reason: str
    beta: np.ndarray
    positive_meshes: int
    effective_meshes: float
    rank: int
    scaled_condition: float


class PooledMoments:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=float)
        assert self.values.ndim == 3 and self.values.shape[2] == 3 and np.isfinite(self.values).all()
        self.n, self.t, _ = self.values.shape
        y, x, p = self.values.transpose(2, 0, 1)
        self.features = np.column_stack([x.sum(1), p.sum(1), y.sum(1), (x*x).sum(1),
                                        (x*p).sum(1), (p*p).sum(1), (x*y).sum(1), (p*y).sum(1)])

    def fit(self, ids, weights):
        ids = np.asarray(ids, dtype=np.int64)
        weights = np.asarray(weights, dtype=float)
        assert len(ids) == len(weights) and (weights >= 0).all() and np.isfinite(weights).all()
        assert len(np.unique(ids)) == len(ids)
        keep = weights > 0
        ids, weights = ids[keep], weights[keep]
        q = len(ids)
        sw = float(weights.sum())
        effective = float(sw*sw/(weights@weights)) if sw else 0.
        def fail(reason, rank=0, condition=np.nan):
            return PooledFit('failed', reason, np.full(3, np.nan), q, effective, rank, condition)
        if not q:
            return fail('no_positive_weight_training_meshes')
        sums = weights @ self.features[ids]
        total = self.t * sw
        mu = sums[:3] / total
        a = np.array([[sums[3], sums[4]], [sums[4], sums[5]]]) - total * np.outer(mu[:2], mu[:2])
        b = sums[6:8] - total * mu[:2] * mu[2]
        diagonal = np.diag(a)
        if not (diagonal > 0).all():
            return fail('zero_or_nonpositive_local_predictor_information', 1 + int((diagonal > 0).sum()))
        scale = np.sqrt(diagonal)
        gram = a / scale[:, None] / scale[None, :]
        eigenvalues = np.linalg.eigvalsh(gram)
        rank = 1 + int((eigenvalues > MIN_SCALED_EIGENVALUE).sum())
        if rank < 3:
            return fail('rank_deficient_or_numerically_singular_local_design', rank)
        condition = float(np.sqrt(eigenvalues.max() / eigenvalues.min()))
        slopes = np.linalg.solve(gram, b / scale) / scale
        beta = np.r_[mu[2] - mu[:2] @ slopes, slopes]
        if not np.isfinite(beta).all():
            return fail('nonfinite_local_coefficients', rank, condition)
        return PooledFit('ok', '', beta, q, effective, rank, condition)

    def predict(self, focus, fit):
        assert fit.status == 'ok'
        return fit.beta[0] + self.values[focus, :, 1:] @ fit.beta[1:]

    def qr_reference(self, ids, weights):
        values = self.values[ids].reshape(-1, 3)
        x = np.column_stack([np.ones(len(values)), values[:, 1:]])
        root = np.repeat(np.sqrt(weights), self.t)
        return np.linalg.lstsq(x * root[:, None], values[:, 0] * root, rcond=None)[0]
