#!/usr/bin/env python3
"""Residual Spatial Autocorrelation.

Plan: one approved four-period diagnostic table (MILI-D-20261009-021).
Framework: AnaSOP Sections 5-7; national FE residuals, rook weights,
mesh-level residual wild bootstrap, refitting the same FE projection.
Run from a terminal: python3 src/analyses/table_residual_spatial_autocorrelation.py
Only NumPy, pandas, PyArrow and openpyxl are used. No source files change.
"""
from pathlib import Path
import hashlib
import json
import platform
import time

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from table_pilot_fixed_effects_baseline import absorb_balanced

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/residual-spatial-autocorrelation/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/residual-spatial-autocorrelation'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def positions(codes):
    assert all(len(c) == 8 and c.isdigit() and int(c[4]) < 8 and int(c[5]) < 8 for c in codes)
    rows = np.array([int(c[:2])*80 + int(c[4])*10 + int(c[6]) for c in codes])
    cols = np.array([(int(c[2:4])+100)*80 + int(c[5])*10 + int(c[7]) for c in codes])
    assert len(set(zip(rows, cols))) == len(codes)
    return rows, cols


def rook_graph(codes):
    rows, cols = positions(codes)
    lookup = {position: i for i, position in enumerate(zip(rows, cols))}
    left, right = [], []
    for i, (row, col) in enumerate(zip(rows, cols)):
        for neighbor in [(row+1, col), (row, col+1)]:
            j = lookup.get(neighbor)
            if j is not None:
                left.append(i); right.append(j)
    u, v = np.array(left, dtype=np.int64), np.array(right, dtype=np.int64)
    n = len(codes)
    degree = np.bincount(np.r_[u, v], minlength=n)
    assert np.all((abs(rows[u]-rows[v])+abs(cols[u]-cols[v])) == 1)
    assert not np.any(u == v) and degree.max() <= 4
    assert len(set(zip(u.tolist(), v.tolist()))) == len(u)

    # Independent, vectorized sorted-coordinate construction checks all edges,
    # including seams where mesh digit increments do not increment mesh codes.
    key = rows * 100000 + cols
    order = np.argsort(key)
    sorted_key = key[order]
    independent = []
    for offset in [1, 100000]:
        target = key + offset
        j = np.searchsorted(sorted_key, target)
        clipped = np.minimum(j, n-1)
        valid = (j < n) & (sorted_key[clipped] == target)
        independent.extend(zip(np.flatnonzero(valid).tolist(), order[clipped[valid]].tolist()))
    assert set(independent) == set(zip(u.tolist(), v.tolist()))
    row_sum = np.zeros(n)
    np.add.at(row_sum, u, 1/degree[u]); np.add.at(row_sum, v, 1/degree[v])
    assert np.allclose(row_sum[degree > 0], 1) and np.all(row_sum[degree == 0] == 0)
    weight = 1/degree[u] + 1/degree[v]
    assert np.isclose(weight.sum(), np.count_nonzero(degree))

    parent = np.arange(n)
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in zip(u, v):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra
    components = len({find(i) for i in range(n)})
    seams = sum(codes[a][:4] != codes[b][:4] for a, b in zip(u, v))
    return u, v, degree, weight, dict(undirected_edges=len(u), directed_edges=2*len(u),
        isolated_meshes=int(np.count_nonzero(degree == 0)),
        meshes_with_neighbors=int(np.count_nonzero(degree)),
        connected_components=components, primary_tile_seam_edges=seams,
        independent_all_edge_check=True, zero_diagonal=True,
        row_standardization_verified=True, no_diagonal_contacts=True)


def moran(residual, u, v, weight, s0):
    z = residual - residual.mean(axis=0, keepdims=True)
    denominator = np.sum(z*z, axis=0)
    assert np.all(denominator > 0)
    numerator = np.sum(z[u] * z[v] * weight[:, None], axis=0)
    return len(z)/s0 * numerator/denominator


def main():
    start = time.monotonic()
    contract = json.loads(CONTRACT.read_text())
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261009-021'
    national_contract_path = ROOT / contract['national_contract']
    national = json.loads(national_contract_path.read_text())
    years = contract['periods']
    assert years == national['periods']
    protected = sorted((ROOT/'data/processed').rglob('*.parquet')) + [
        ROOT/'docs/AnaSOP.md', CONTRACT, national_contract_path,
        ROOT/'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv',
        ROOT/'data/exp/figure-table-generation/national-fixed-effects/validation.json',
    ] + sorted((ROOT/'data/results/tables').glob('Table_*fixed_effects*.xlsx'))
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    QA.mkdir(parents=True, exist_ok=True)
    variables = [national['outcome']] + national['explanatory']
    identifiers = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']
    source = pd.read_parquet(ROOT/national['input'], columns=identifiers+variables)
    assert len(source) == national['source_observations']
    assert not source.duplicated(['Mesh Code', 'Road Year']).any()
    finite = np.isfinite(source[variables].to_numpy()).all(axis=1)
    counts = source.assign(finite=finite).groupby('Mesh Code').finite.sum()
    codes = sorted(counts.index[counts.eq(len(years))].tolist())
    sample = source.loc[source['Mesh Code'].isin(codes)].sort_values(['Mesh Code', 'Road Year'])
    n, t = len(codes), len(years)
    assert (n, len(sample)) == (contract['expected_meshes'], contract['expected_observations'])
    membership = pd.read_csv(ROOT/'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv', dtype={'Mesh Code': 'string'})
    assert len(membership) == n*t
    for name in identifiers:
        assert np.array_equal(sample[name].to_numpy(), membership[name].to_numpy())
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(n,t), np.tile(years, (n,1)))
    array = sample[variables].to_numpy(dtype=float).reshape(n,t,3)
    del source, membership
    transformed = absorb_balanced(array)
    y, x = transformed[:,:,0].reshape(n*t), transformed[:,:,1:].reshape(n*t,2)
    assert np.linalg.matrix_rank(x) == 2
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = (y-x@beta).reshape(n,t)
    baseline = json.loads((ROOT/'data/exp/figure-table-generation/national-fixed-effects/validation.json').read_text())
    expected_beta = np.array([c['coefficient'] for c in baseline['coefficients']])
    assert np.allclose(beta, expected_beta, rtol=1e-11, atol=1e-12)

    centered = array-array.mean(axis=1, keepdims=True)
    indicators = np.eye(t)[:,1:]; indicators -= indicators.mean(axis=0)
    explicit = np.column_stack([centered[:,:,1:].reshape(n*t,2), np.tile(indicators,(n,1))])
    alternate_y = centered[:,:,0].reshape(n*t)
    alternate_beta = np.linalg.lstsq(explicit, alternate_y, rcond=None)[0]
    alternate_residual = (alternate_y-explicit@alternate_beta).reshape(n,t)
    residual_error = float(np.max(abs(residual-alternate_residual)))
    assert np.allclose(residual, alternate_residual, rtol=1e-10, atol=1e-10)
    assert np.allclose(residual.mean(axis=1), 0, atol=1e-10)
    assert np.allclose(residual.mean(axis=0), 0, atol=1e-10)
    assert np.allclose((x.T@residual.reshape(n*t))/(n*t), 0, atol=1e-9)
    u, v, degree, weight, graph = rook_graph(codes)
    s0 = float(np.count_nonzero(degree))
    observed = moran(residual, u, v, weight, s0)
    # Independent directed spatial-lag calculation verifies all four numerators.
    z = residual-residual.mean(axis=0, keepdims=True)
    lag = np.zeros_like(z)
    np.add.at(lag,u,z[v]/degree[u,None]); np.add.at(lag,v,z[u]/degree[v,None])
    alternate_i = n/s0*np.sum(z*lag,axis=0)/np.sum(z*z,axis=0)
    assert np.allclose(observed, alternate_i, rtol=1e-12, atol=1e-13)
    print(f'Reconstructed {n:,} meshes; {len(u):,} rook edges; {graph["isolated_meshes"]:,} isolates.',flush=True)
    print('Observed residual Moran I: '+', '.join(f'{year}: {value:.8f}' for year,value in zip(years,observed)),flush=True)

    rng = np.random.default_rng(contract['seed'])
    b = contract['bootstrap_draws']
    draws = np.empty((b,t))
    xtx = x.T@x
    bootstrap_projection_error = None
    for k in range(b):
        multiplier = rng.integers(0,2,size=n,dtype=np.int8)*2-1
        perturbed = residual*multiplier[:,None]
        absorbed = absorb_balanced(perturbed)
        delta = np.linalg.solve(xtx,x.T@absorbed.reshape(n*t))
        boot_residual = (absorbed.reshape(n*t)-x@delta).reshape(n,t)
        if k == 0:
            # Explicit refit of fitted outcome plus bootstrapped residuals,
            # represented after mesh demeaning with original period indicators.
            boot_y = alternate_y-alternate_residual.reshape(n*t)+perturbed.reshape(n*t)
            boot_y = (boot_y.reshape(n,t)-boot_y.reshape(n,t).mean(axis=1,keepdims=True)).reshape(n*t)
            direct_beta = np.linalg.lstsq(explicit,boot_y,rcond=None)[0]
            direct_residual = (boot_y-explicit@direct_beta).reshape(n,t)
            bootstrap_projection_error = float(np.max(abs(boot_residual-direct_residual)))
            assert np.allclose(boot_residual,direct_residual,rtol=1e-10,atol=1e-10)
            assert np.allclose(boot_residual.mean(axis=1),0,atol=1e-10)
            assert np.allclose(boot_residual.mean(axis=0),0,atol=1e-10)
        draws[k] = moran(boot_residual,u,v,weight,s0)
        if (k+1)%100 == 0 or k == b-1:
            print(f'Bootstrap {k+1}/{b}; elapsed {time.monotonic()-start:.1f}s',flush=True)
    lower = np.sum(draws<=observed[None,:],axis=0)
    upper = np.sum(draws>=observed[None,:],axis=0)
    p = np.minimum(1,2*np.minimum((1+lower)/(b+1),(1+upper)/(b+1)))
    means, sd = draws.mean(axis=0), draws.std(axis=0,ddof=1)
    rows = [[year,float(i),float(prob),float(mu),float(sigma),n,graph['meshes_with_neighbors'],graph['isolated_meshes']]
            for year,i,prob,mu,sigma in zip(years,observed,p,means,sd)]

    workbook = Workbook(); sheet = workbook.active; sheet.title = 'Residual Moran'
    sheet.merge_cells('A1:H1'); sheet['A1'] = contract['table_title']
    sheet['A1'].font = Font(name='Calibri',size=16,bold=True,color='17324D')
    sheet.merge_cells('A2:H2'); sheet['A2'] = 'National mesh and period fixed effects | Rook adjacency | Mesh-level wild bootstrap with refitting'
    sheet['A2'].font = Font(name='Calibri',size=11,color='526679')
    headers = ['Road Year','Residual Moran I','Bootstrap p (two-sided)','Bootstrap null mean','Bootstrap null SD','Meshes','Meshes with neighbors','Isolated meshes']
    for j,value in enumerate(headers,1):
        cell=sheet.cell(4,j,value); cell.font=Font(name='Calibri',bold=True,color='FFFFFF')
        cell.fill=PatternFill('solid',fgColor='17324D'); cell.alignment=Alignment(wrap_text=True,vertical='center')
    for i,row in enumerate(rows,5):
        for j,value in enumerate(row,1):
            cell=sheet.cell(i,j,value); cell.font=Font(name='Calibri',size=11)
            cell.alignment=Alignment(horizontal='right',vertical='center')
            cell.number_format='0.00000000' if 2<=j<=5 else '#,##0' if j>5 else '0'
            if i%2: cell.fill=PatternFill('solid',fgColor='F0F4F8')
        sheet.row_dimensions[i].height=26
    notes = [
        'Residuals are from the accepted national model: Nighttime Radiance on Road Length Density and Population, with mesh and common period effects. The same 134,830 meshes appear in every period.',
        'Full statistical-grid shared-edge (rook) adjacency is row-standardized among sampled meshes; diagonals and unobserved mesh gaps are not linked. Administrative and primary-tile boundaries do not block neighbors.',
        f'All {n:,} meshes are retained; {graph["isolated_meshes"]:,} have zero weight rows. Isolates are included in centering and denominator. The sum of weights is {s0:,.0f}; adjacency is not road-network connectivity.',
        f'Inference: {b:,} residual wild-bootstrap draws; seed {contract["seed"]}. One independent Rademacher multiplier per mesh is shared by its four residuals; national effects and both slopes are refitted in each draw.',
        'Null: cross-mesh independent mean-zero errors conditional on the specified model. Heteroskedasticity and within-mesh temporal dependence are allowed. This is approximate bootstrap inference, not an exact permutation test or guaranteed finite-sample calibration.',
        'P-values are equal-tail two-sided, with plus-one tail counts, and unadjusted across the four periods. The minimum reportable p-value is 0.001; a value at that floor does not establish a smaller probability.',
        'A positive significant statistic indicates remaining spatial clustering of residuals. It does not prove geographic coefficient differences, causal road effects, causal spillovers, or a need for a specific geographically weighted estimator.',
        'Historical source comparability and modeled fine-scale light dependence remain limitations. All processed inputs and previous regression workbooks are preserved; no additional regression specification is introduced.',
    ]
    for i,note in enumerate(notes,11):
        sheet.merge_cells(start_row=i,start_column=1,end_row=i,end_column=8)
        sheet.cell(i,1,note).font=Font(name='Calibri',size=10,color='526679')
        sheet.cell(i,1).alignment=Alignment(wrap_text=True,vertical='top'); sheet.row_dimensions[i].height=33
    for col,width in zip('ABCDEFGH',[13,21,25,23,22,17,24,20]): sheet.column_dimensions[col].width=width
    sheet.row_dimensions[1].height=27; sheet.row_dimensions[2].height=24; sheet.row_dimensions[4].height=36
    sheet.freeze_panes='B5'; sheet.auto_filter.ref='A4:H8'; sheet.sheet_view.showGridLines=False
    sheet.page_setup.orientation='landscape'; sheet.page_setup.paperSize=sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth=1; sheet.page_setup.fitToHeight=1
    sheet.sheet_properties.pageSetUpPr.fitToPage=True; sheet.print_area='A1:H18'
    out=ROOT/contract['output_workbook']; out.parent.mkdir(parents=True,exist_ok=True); workbook.save(out)
    exported=load_workbook(out,data_only=True)
    assert exported.sheetnames==['Residual Moran']
    for i,row in enumerate(rows,5):
        for j,value in enumerate(row,1):
            actual=exported.active.cell(i,j).value
            assert np.isclose(actual,value,rtol=1e-13,atol=1e-15)

    edges=pd.DataFrame({'Mesh Code From':np.asarray(codes)[u],'Mesh Code To':np.asarray(codes)[v],
        'Weight From To':1/degree[u],'Weight To From':1/degree[v]})
    edges.to_parquet(QA/'rook_edges.parquet',index=False)
    pd.DataFrame({'Mesh Code':codes,'Neighbor Count':degree}).to_csv(QA/'mesh_neighbors.csv',index=False)
    residual_frame=sample[identifiers].copy(); residual_frame['National FE Residual']=residual.reshape(n*t)
    residual_frame.to_parquet(QA/'national_residuals.parquet',index=False)
    pd.DataFrame(draws,columns=[str(year) for year in years]).to_csv(QA/'bootstrap_moran.csv',index=False)
    assert all(sha(ROOT/path)==digest for path,digest in before.items())
    result=dict(status='passed',decision_id=contract['decision_id'],table_title=contract['table_title'],
        periods=years,meshes=n,observations=n*t,graph=graph,
        coefficients=beta.tolist(),baseline_coefficient_max_difference=float(np.max(abs(beta-expected_beta))),
        equivalent_residual_max_difference=residual_error,
        residual_orthogonality_verified=True,independent_spatial_lag_max_difference=float(np.max(abs(observed-alternate_i))),
        bootstrap_projection_max_difference=bootstrap_projection_error,bootstrap_draws=b,seed=contract['seed'],
        results=[dict(year=row[0],moran_i=row[1],p_two_sided=row[2],bootstrap_mean=row[3],bootstrap_sd=row[4],
            meshes=row[5],meshes_with_neighbors=row[6],isolated_meshes=row[7],
            bootstrap_lower_count=int(lower[k]),bootstrap_upper_count=int(upper[k])) for k,row in enumerate(rows)],
        approximate_residual_bootstrap=True,coefficient_heterogeneity_test=False,multiple_comparison_adjustment=False,
        protected_sha256=before,protected_files_unchanged=True,workbook_readback_verified=True,
        output=contract['output_workbook'],output_sha256=sha(out),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
        human_output_acceptance='pending')
    (QA/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Saved: '+str(out.relative_to(ROOT)),flush=True)
    print(json.dumps(result['results'],indent=2),flush=True)
    print('All membership, residual, graph, bootstrap refit, protected checksum and workbook checks passed.',flush=True)


if __name__=='__main__':
    main()
