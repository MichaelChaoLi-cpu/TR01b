"""Pooled WLS with a basis for nuisance controls and mandatory core slopes.

Only constant or numerically redundant added controls are omitted. A core slope
aliased with any retained nuisance direction fails rather than receiving an
arbitrary coefficient. Held-out data must satisfy training omission relations.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class Fit:
    status: str
    reason: str
    beta: np.ndarray
    active: np.ndarray
    constant: np.ndarray
    redundant: np.ndarray
    rank: int
    condition: float
    anchor: np.ndarray
    offset: np.ndarray
    center_y: float
    norms: np.ndarray
    relation: np.ndarray
    minimum: np.ndarray
    maximum: np.ndarray
    positive_meshes: int
    effective_meshes: float


def fit(raw, mesh_weights, periods=5):
    raw = np.asarray(raw, float)
    mesh_weights = np.asarray(mesh_weights, float)
    p = raw.shape[1]-1
    use = mesh_weights > 0
    raw = raw.reshape(len(mesh_weights), periods, p+1)[use].reshape(-1, p+1)
    weights = mesh_weights[use]
    q = len(weights)
    effective = float(weights.sum()**2/(weights@weights)) if q else 0.
    active = np.arange(p); constant = redundant = np.array([], dtype=int)
    anchor = offset = norms = minimum = maximum = np.full(p, np.nan)
    center_y = np.nan
    relation = np.empty((p, 0))
    def failed(reason, rank=0, condition=np.nan):
        return Fit('failed', reason, np.full(p+1, np.nan), active, constant, redundant,
                   rank, condition, anchor, offset, center_y, norms, relation,
                   minimum, maximum, q, effective)
    if not q:
        return failed('no_positive_weight_training_meshes')
    assert np.isfinite(raw).all()
    minimum, maximum = raw[:, 1:].min(0), raw[:, 1:].max(0)
    tolerance = 1e-12*np.maximum(1., np.maximum(abs(minimum), abs(maximum)))
    constant = np.flatnonzero(maximum-minimum <= tolerance)
    if np.isin([0, 1], constant).any():
        return failed('constant_mandatory_road_or_population')
    root = np.repeat(np.sqrt(weights), periods)
    w = root*root
    anchor = raw[0, 1:].copy()
    shifted = raw[:, 1:]-anchor
    offset = np.average(shifted, weights=w, axis=0)
    center = shifted-offset
    center_y = float(np.average(raw[:, 0], weights=w))
    weighted_center = center*root[:, None]
    norms = np.linalg.norm(weighted_center, axis=0)
    scaled = np.zeros_like(weighted_center)
    varying = np.setdiff1d(np.arange(p), constant)
    if (norms[varying] <= 0).any():
        return failed('nonpositive_predictor_information')
    scaled[:, varying] = weighted_center[:, varying]/norms[varying]
    # Deterministic, twice-reorthogonalized nuisance basis in contract order.
    # This represents the complete nuisance column space, including when an
    # absent reference category makes the remaining shares sum to a constant.
    controls, redundant_list, basis = [], [], []
    for j in varying[varying >= 2]:
        residual = scaled[:, j].copy()
        for _ in range(2):
            for direction in basis:
                residual -= direction*(direction@residual)
        norm = np.linalg.norm(residual)
        if norm <= 1e-10:
            redundant_list.append(int(j))
        else:
            controls.append(int(j)); basis.append(residual/norm)
    redundant = np.asarray(redundant_list, dtype=int)
    active = np.asarray([0, 1]+controls, dtype=int)
    z = scaled[:, active]
    slope_scaled, _, _, singular = np.linalg.lstsq(z, (raw[:, 0]-center_y)*root, rcond=None)
    rank = 1+int((singular*singular > 1e-12).sum())
    if rank != len(active)+1:
        return failed('mandatory_or_retained_design_not_identifiable', rank)
    condition = float(singular[0]/singular[-1])
    slopes = slope_scaled/norms[active]
    beta = np.full(p+1, np.nan)
    beta[0], beta[active+1] = center_y-(anchor[active]+offset[active])@slopes, slopes
    if not np.isfinite(beta[np.r_[0, active+1]]).all():
        return failed('nonfinite_coefficients', rank, condition)
    relation = np.empty((len(active), len(redundant)))
    if len(redundant):
        # Relations use nuisance controls only, never roads or population.
        coefficients = np.linalg.lstsq(scaled[:, controls], scaled[:, redundant], rcond=None)[0]
        assert np.max(abs(scaled[:, controls]@coefficients-scaled[:, redundant])) < 1e-9
        relation = np.zeros((len(active), len(redundant)))
        relation[2:] = coefficients/norms[controls, None]*norms[None, redundant]
    return Fit('ok', '', beta, active, constant, redundant, rank, condition,
               anchor, offset, center_y, norms, relation, minimum, maximum, q, effective)


def predict(raw_x, fitted):
    if fitted.status != 'ok':
        return None
    x = np.asarray(raw_x, float)
    centered = (x-fitted.anchor)-fitted.offset
    for j in fitted.constant:
        tol = 1e-12*np.maximum(1., np.maximum(abs(x[:, j]), abs(fitted.minimum[j])))
        if np.any(abs(x[:, j]-fitted.minimum[j]) > tol):
            return None
    if len(fitted.redundant):
        expected = centered[:, fitted.active]@fitted.relation
        delta = centered[:, fitted.redundant]-expected
        scale = np.maximum(1., fitted.maximum[fitted.redundant]-fitted.minimum[fitted.redundant])
        tol = 1e-9*scale+1e-12*np.maximum(abs(fitted.minimum[fitted.redundant]), abs(fitted.maximum[fitted.redundant]))
        if np.any(abs(delta) > tol):
            return None
    return fitted.center_y+centered[:, fitted.active]@fitted.beta[fitted.active+1]


def expanded_reference(raw, mesh_weights, fitted, periods=5):
    raw = np.asarray(raw, float)
    root = np.repeat(np.sqrt(mesh_weights), periods)
    centered = (raw[:, 1:][:, fitted.active]-fitted.anchor[fitted.active])-fitted.offset[fitted.active]
    norms = np.linalg.norm(centered*root[:, None], axis=0)
    x = np.column_stack([np.ones(len(raw)), centered/norms])
    coefficient, _, rank, _ = np.linalg.lstsq(x*root[:, None], raw[:, 0]*root, rcond=None)
    assert rank == len(fitted.active)+1
    slopes = coefficient[1:]/norms
    prediction = coefficient[0]+centered@slopes
    return prediction, slopes
