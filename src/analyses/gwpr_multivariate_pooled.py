"""Multivariate pooled GWPR sufficient statistics in original reporting units.

Static controls are repeated observations of mesh context, not extra spatial
units. No fixed effects, ridge or bandwidth fallback. Constant-control handling
is explicit and must be selected in the execution contract.
"""
from dataclasses import dataclass
import numpy as np
from gwpr_pooled import RadiusIndex, mesh_centroids, bisquare_weights

RAW_VARIATION_RELATIVE_TOLERANCE = 1e-12


@dataclass
class MultivariateFit:
    status: str
    reason: str
    beta: np.ndarray
    positive_meshes: int
    effective_meshes: float
    rank: int
    condition: float
    active: np.ndarray
    constant: np.ndarray
    constant_values: np.ndarray
    center_x: np.ndarray | None = None
    center_y: float | None = None
    center_anchor: np.ndarray | None = None
    center_offset: np.ndarray | None = None


class MultivariateMoments:
    def __init__(self, values, constant_control_rule='strict', precompute_features=True):
        self.values = np.asarray(values, dtype=float)
        assert self.values.ndim == 3 and np.isfinite(self.values).all()
        assert constant_control_rule in ['strict', 'omit_constant_added_controls']
        self.rule = constant_control_rule
        self.n, self.t, dimensions = self.values.shape
        self.p = dimensions - 1
        self.k = self.p + 1
        flat = self.values.reshape(-1, dimensions)
        self.mean, self.scale = flat.mean(0), flat.std(0)
        assert (self.scale > 0).all()
        self.minimum = self.values[:, :, 1:].min(1)
        self.maximum = self.values[:, :, 1:].max(1)
        self.upper = np.triu_indices(self.p + 2)
        self.features = None
        if not precompute_features:
            return
        self.features = np.empty((self.n, len(self.upper[0])), dtype=float)
        for start in range(0, self.n, 10000):
            stop = min(self.n, start + 10000)
            standardized = (self.values[start:stop] - self.mean) / self.scale
            z = np.concatenate([np.ones((stop-start, self.t, 1)), standardized[:, :, 1:], standardized[:, :, :1]], axis=2)
            gram = np.einsum('ntj,ntl->njl', z, z)
            self.features[start:stop] = gram[:, self.upper[0], self.upper[1]]

    def fit_sums(self, packed, minimum, maximum, positive_meshes, effective_meshes):
        resolution = RAW_VARIATION_RELATIVE_TOLERANCE * np.maximum(1., np.maximum(abs(minimum), abs(maximum)))
        constant = np.flatnonzero((maximum-minimum <= resolution) if self.rule == 'omit_constant_added_controls' else (minimum == maximum))
        active = np.arange(self.p)
        if self.rule == 'omit_constant_added_controls':
            active = active[~np.isin(active, constant[constant >= 2])]
        def failure(reason, rank=0, condition=np.nan):
            return MultivariateFit('failed', reason, np.full(self.k, np.nan), int(positive_meshes),
                float(effective_meshes), int(rank), float(condition), active, constant, minimum[constant])
        if positive_meshes == 0:
            return failure('no_positive_weight_training_meshes')
        if np.isin(active, constant).any():
            return failure('constant_retained_predictor')
        matrix = np.zeros((self.p+2, self.p+2))
        matrix[self.upper] = packed
        matrix[(self.upper[1], self.upper[0])] = packed
        total = matrix[0, 0]
        mu = matrix[0, 1:] / total
        a = matrix[1:-1, 1:-1] - total * np.outer(mu[:-1], mu[:-1])
        b = matrix[1:-1, -1] - total * mu[:-1] * mu[-1]
        a, b = a[np.ix_(active, active)], b[active]
        diagonal = np.diag(a)
        if not (diagonal > 0).all():
            return failure('zero_or_nonpositive_local_predictor_information')
        norm = np.sqrt(diagonal)
        gram = a / norm[:, None] / norm[None, :]
        eigenvalues = np.linalg.eigvalsh(gram)
        rank = 1 + int((eigenvalues > 1e-12).sum())
        if rank != len(active) + 1:
            return failure('rank_deficient_or_numerically_singular_local_design', rank)
        condition = float(np.sqrt(eigenvalues[-1] / eigenvalues[0]))
        standardized_slopes = np.linalg.solve(gram, b / norm) / norm
        slopes = self.scale[0] * standardized_slopes / self.scale[1:][active]
        intercept = self.mean[0] + self.scale[0] * (mu[-1] - mu[:-1][active] @ standardized_slopes) - self.mean[1:][active] @ slopes
        beta = np.full(self.k, np.nan)
        beta[0], beta[active+1] = intercept, slopes
        if not np.isfinite(beta[np.r_[0, active+1]]).all():
            return failure('nonfinite_local_coefficients', rank, condition)
        return MultivariateFit('ok', '', beta, int(positive_meshes), float(effective_meshes), rank, condition, active, constant, minimum[constant],
            self.mean[1:]+self.scale[1:]*mu[:-1], self.mean[0]+self.scale[0]*mu[-1])

    def fit(self, ids, weights):
        ids, weights = np.asarray(ids), np.asarray(weights, dtype=float)
        assert len(ids) == len(weights) and (weights >= 0).all()
        positive = weights > 0
        ids, weights = ids[positive], weights[positive]
        if not len(ids):
            return self.fit_sums(np.zeros(self.features.shape[1]), np.full(self.p, np.nan), np.full(self.p, np.nan), 0, 0.)
        return self.fit_sums(weights @ self.features[ids], self.minimum[ids].min(0), self.maximum[ids].max(0),
            len(ids), weights.sum()**2 / (weights @ weights))

    def predict(self, focus, fit):
        assert fit.status == 'ok'
        omitted = np.setdiff1d(fit.constant, fit.active)
        for column in omitted:
            constant_value = fit.constant_values[np.flatnonzero(fit.constant == column)[0]]
            focal = self.values[focus, :, column+1]
            resolution = RAW_VARIATION_RELATIVE_TOLERANCE * np.maximum(1., np.maximum(abs(focal), abs(constant_value)))
            matches = abs(focal-constant_value) <= resolution if self.rule == 'omit_constant_added_controls' else focal == constant_value
            if not matches.all():
                return None
        x = self.values[focus, :, 1:][:, fit.active]
        centered = (x-fit.center_anchor[fit.active])-fit.center_offset[fit.active] if fit.center_anchor is not None else x-fit.center_x[fit.active]
        return fit.center_y + centered @ fit.beta[fit.active+1]

    def qr_reference(self, ids, weights, active, return_center=False):
        raw = self.values[ids].reshape(-1, self.p+1)
        root = np.repeat(np.sqrt(weights), self.t)
        w = root*root
        anchor = raw[0, 1:][active]
        shifted = raw[:, 1:][:, active]-anchor
        offset = np.average(shifted, weights=w, axis=0)
        centered = shifted-offset
        mean = anchor+offset
        scale = np.sqrt(np.average(centered**2, weights=w, axis=0))
        x = np.column_stack([np.ones(len(raw)), centered/scale])
        result, _, rank, _ = np.linalg.lstsq(x*root[:, None], raw[:, 0]*root, rcond=None)
        assert rank == len(active)+1
        slopes = result[1:] / scale
        beta = np.full(self.k, np.nan)
        beta[0], beta[active+1] = result[0] - mean @ slopes, slopes
        return (beta, anchor, offset, float(result[0])) if return_center else beta

    def qr_fit(self, ids, weights):
        """Stable local centering and SVD; also rejects moment cancellation artifacts."""
        positive = weights > 0
        ids, weights = ids[positive], weights[positive]
        q = len(ids)
        minimum, maximum = self.minimum[ids].min(0), self.maximum[ids].max(0)
        resolution = RAW_VARIATION_RELATIVE_TOLERANCE * np.maximum(1., np.maximum(abs(minimum), abs(maximum)))
        constant = np.flatnonzero((maximum-minimum <= resolution) if self.rule == 'omit_constant_added_controls' else (minimum == maximum))
        active = np.arange(self.p)
        if self.rule == 'omit_constant_added_controls':
            active = active[~np.isin(active, constant[constant >= 2])]
        effective = float(weights.sum()**2/(weights@weights))
        def fail(reason, rank=0):
            return MultivariateFit('failed', reason, np.full(self.k, np.nan), q, effective, rank, np.nan,
                active, constant, minimum[constant])
        if np.isin(active, constant).any():
            return fail('constant_retained_predictor')
        # Existing area-overlay checks bound share roundoff around 1e-12.
        # Normalizing a 1e-13 fluctuation in an otherwise all-forest share can
        # spuriously generate a 1e10 coefficient. Retain the predictor, but
        # reject that fit as below numerical resolution; do not omit it.
        ranges = maximum[active] - minimum[active]
        resolution = RAW_VARIATION_RELATIVE_TOLERANCE * np.maximum(1., np.maximum(abs(minimum[active]), abs(maximum[active])))
        if (ranges <= resolution).any():
            return fail('predictor_variation_at_or_below_numerical_precision')
        raw = self.values[ids].reshape(-1, self.p+1)
        x, y = raw[:, 1:][:, active], raw[:, 0]
        root = np.repeat(np.sqrt(weights), self.t)
        w = root*root
        anchor_x = x[0]
        shifted = x-anchor_x
        offset_x = np.average(shifted, weights=w, axis=0)
        mu_x, mu_y = anchor_x+offset_x, np.average(y, weights=w)
        centered = (shifted-offset_x) * root[:, None]
        norms = np.linalg.norm(centered, axis=0)
        if not (norms > 0).all():
            return fail('zero_or_nonpositive_local_predictor_information')
        scaled = centered / norms
        beta_scaled, _, _, singular = np.linalg.lstsq(scaled, (y-mu_y)*root, rcond=None)
        rank = 1 + int((singular*singular > 1e-12).sum())
        if rank != len(active)+1:
            return fail('rank_deficient_or_numerically_singular_local_design', rank)
        slopes = beta_scaled / norms
        beta = np.full(self.k, np.nan)
        beta[0], beta[active+1] = mu_y - mu_x @ slopes, slopes
        center = np.full(self.p, np.nan)
        center[active] = mu_x
        anchor, offset = np.full(self.p, np.nan), np.full(self.p, np.nan)
        anchor[active], offset[active] = anchor_x, offset_x
        return MultivariateFit('ok', '', beta, q, effective, rank, float(singular[0]/singular[-1]), active, constant, minimum[constant], center, float(mu_y), anchor, offset)
