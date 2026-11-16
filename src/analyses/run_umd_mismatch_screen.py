"""UMD 2024 comparable-context screen with unchanged accepted screening rules.

AnaSOP Sections 4-7; MILI-D-20261011-027. Does not refit regressions or
overwrite IGBP/municipal evidence. Every peer group is independently checked.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from gwpr_twoways import mesh_centroids
from run_road_economy_mismatch_trial import sha, PEERS, FACILITIES

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / 'data/exp/umd-four-layer/inputs/model_panel.parquet'
CONTEXT = ROOT / 'data/processed/national/modis_umd/mismatch_context_2024_preprocessed.parquet'
OLD = ROOT / 'data/exp/road-economy-mismatch-light-zero-audit/revised_mesh_screen_2024.parquet'
OUT = ROOT / 'data/exp/umd-mismatch-screen'

def main():
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in [PANEL, CONTEXT, OLD]}
    d = pd.read_parquet(PANEL, filters=[('Road Year', '==', 2024)])
    c = pd.read_parquet(CONTEXT, columns=['Mesh Code', 'Land Context'])
    d = d.merge(c, on='Mesh Code', how='left', validate='one_to_one')
    assert len(d) == 383386 and d['Mesh Code'].is_unique and d['Land Context'].notna().all()
    assert d['Population Year'].eq(2020).all() and d['Nighttime Light Year'].eq(2024).all()
    assert np.isfinite(d[['Road Length Density', 'Population', 'Nighttime Radiance']]).all().all()
    assert d[['Road Length Density', 'Population', 'Nighttime Radiance']].ge(0).all().all()
    np.testing.assert_allclose(d['Road Length Density'], d['Road Length'] / d['Mesh Area'], atol=1e-10)
    d['Population Band'] = pd.cut(d['Population'], [-1, 0, 9, 49, 199, 999, 4999, np.inf],
                                 labels=['0', '1-9', '10-49', '50-199', '200-999', '1000-4999', '5000+']).astype(str)
    d['Facility Presence'] = np.where(d[FACILITIES].sum(axis=1) > 0,
                                     'At least one selected facility', 'No selected facility')
    d['Rail Proximity Band'] = pd.cut(d['Distance to Railway Station'], [-np.inf, 1, 5, np.inf],
                                     right=False, labels=['<1 km', '1-5 km', '>=5 km']).astype(str)
    assert d[PEERS].notna().all().all()
    g = d.groupby(PEERS, observed=True, sort=True)
    d['Peer Meshes'] = g['Mesh Code'].transform('size')
    # pandas' default quantile uses the accepted linear interpolation.
    for col, source, q in [('Peer Road Q75', 'Road Length Density', .75),
                           ('Peer Radiance Q25', 'Nighttime Radiance', .25)]:
        quantiles = g[source].quantile(q, interpolation='linear').rename(col).reset_index()
        d = d.merge(quantiles, on=PEERS, how='left', validate='many_to_one', sort=False)
    g = d.groupby(PEERS, observed=True, sort=True)
    d['Peer Maximum Radiance'] = g['Nighttime Radiance'].transform('max')
    d['Peer Minimum Radiance'] = g['Nighttime Radiance'].transform('min')
    d['Peer Zero Radiance Fraction'] = d['Nighttime Radiance'].eq(0).groupby(
        [d[x] for x in PEERS], observed=True).transform('mean')
    d['Peer All Zero Radiance'] = d['Peer Maximum Radiance'].eq(0) & d['Peer Minimum Radiance'].eq(0)
    d['Peer Road Percentile'] = g['Road Length Density'].rank(method='average', pct=True)
    d['Peer Radiance Percentile'] = g['Nighttime Radiance'].rank(method='average', pct=True)
    small = d['Peer Meshes'].lt(30)
    az = d['Peer All Zero Radiance']
    eligible = ~small & d['Peer Maximum Radiance'].gt(0)
    high = d['Road Length Density'].gt(0) & d['Road Length Density'].gt(d['Peer Road Q75'])
    low = d['Nighttime Radiance'].le(d['Peer Radiance Q25'])
    d['Supported Comparison'] = eligible
    d['Potential Mismatch Candidate'] = pd.Series(pd.NA, index=d.index, dtype='boolean')
    d.loc[eligible, 'Potential Mismatch Candidate'] = (high & low).loc[eligible]
    d['Screen Status'] = 'Other supported comparison'
    d.loc[eligible & high & ~low, 'Screen Status'] = 'Higher roads; other radiance'
    d.loc[eligible & ~high & low, 'Screen Status'] = 'Other roads; lower radiance'
    d.loc[eligible & high & low, 'Screen Status'] = 'Potential mismatch candidate'
    d.loc[small, 'Screen Status'] = 'Insufficient peers'
    d.loc[az, 'Screen Status'] = 'Information insufficient: all-zero peer radiance'
    d['Screen Support Reason'] = np.select([small & az, small, az],
        ['Insufficient peers and all-zero radiance', 'Insufficient peers', 'All-zero peer radiance'], default='Supported')
    cand = d['Potential Mismatch Candidate'].fillna(False)
    d['Candidate Count'] = cand.astype(int)
    d['Candidate Road Length'] = d['Road Length'].where(cand, 0)
    coords = mesh_centroids(d['Mesh Code'].astype(str).to_numpy())
    d['Latitude'], d['Longitude'] = coords[:, 0], coords[:, 1]
    # Validate every peer group with direct NumPy calculations and distinct mesh IDs.
    for _, z in d.groupby(PEERS, observed=True, sort=True):
        roads, radiance = z['Road Length Density'].to_numpy(), z['Nighttime Radiance'].to_numpy()
        qd, qr = np.quantile(roads, .75, method='linear'), np.quantile(radiance, .25, method='linear')
        np.testing.assert_allclose(z['Peer Road Q75'], qd, atol=1e-12)
        np.testing.assert_allclose(z['Peer Radiance Q25'], qr, atol=1e-12)
        support = z['Mesh Code'].nunique() >= 30 and radiance.max() > 0
        assert z['Supported Comparison'].eq(support).all()
        assert z['Peer Meshes'].eq(len(z)).all()
        if support:
            expected = (roads > 0) & (roads > qd) & (radiance <= qr)
            assert np.array_equal(z['Potential Mismatch Candidate'].to_numpy(dtype=bool), expected)
        else:
            assert z['Potential Mismatch Candidate'].isna().all()
    old = pd.read_parquet(OLD).set_index('Mesh Code').sort_index()
    new = d.set_index('Mesh Code').sort_index()
    assert old.index.equals(new.index)
    preserved = ['Road Year', 'Population Year', 'Nighttime Light Year', 'Road Length Density',
                 'Nighttime Radiance', 'Population', 'Region', 'Prefecture Code', 'Prefecture',
                 'Road Length', 'Mesh Area', 'Road Density Originally Missing', 'Road Density Source Status',
                 'Distance to Railway Station', 'Distance to Passenger Airport', *FACILITIES,
                 'Population Band', 'Facility Presence', 'Rail Proximity Band']
    for col in preserved:
        pd.testing.assert_series_equal(old[col], new[col], check_dtype=False)
    def states(x):
        return np.where(x['Potential Mismatch Candidate'].isna(), 'Unavailable',
                        np.where(x['Potential Mismatch Candidate'].fillna(False), 'Candidate', 'Noncandidate'))
    transitions = pd.crosstab(pd.Series(states(old), name='IGBP'), pd.Series(states(new), name='UMD'))
    context_transitions = pd.crosstab(old['Land Context'], new['Land Context'])
    bycontext = d.groupby('Land Context', sort=True).agg(
        **{'Cohort Meshes': ('Mesh Code', 'size'), 'Supported Meshes': ('Supported Comparison', 'sum'),
           'Candidate Meshes': ('Candidate Count', 'sum')}).reset_index()
    zero = d.loc[cand].groupby('Land Context')['Nighttime Radiance'].apply(lambda x: x.eq(0).sum())
    bycontext['Candidate Zero Radiance Meshes'] = bycontext['Land Context'].map(zero).fillna(0).astype(int)
    bycontext['Candidate Fraction of Supported Meshes'] = bycontext['Candidate Meshes'] / bycontext['Supported Meshes'].replace(0, np.nan)
    bycontext['Candidate Zero Radiance Fraction'] = bycontext['Candidate Zero Radiance Meshes'] / bycontext['Candidate Meshes'].replace(0, np.nan)
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'mesh_screen_2024.parquet'
    d.to_parquet(output, index=False)
    bycontext.to_csv(OUT / 'land_context_summary.csv', index=False)
    transitions.to_csv(OUT / 'igbp_to_umd_screen_states.csv')
    context_transitions.to_csv(OUT / 'igbp_to_umd_land_context.csv')
    peer = d.groupby(PEERS, observed=True).agg(
        **{'Meshes': ('Mesh Code', 'size'), 'Road Q75': ('Peer Road Q75', 'first'),
           'Radiance Q25': ('Peer Radiance Q25', 'first'), 'Maximum Radiance': ('Peer Maximum Radiance', 'first'),
           'Supported': ('Supported Comparison', 'first'), 'Candidates': ('Candidate Count', 'sum')}).reset_index()
    peer.to_csv(OUT / 'peer_strata.csv', index=False)
    pd.testing.assert_frame_equal(d, pd.read_parquet(output))
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in [PANEL, CONTEXT, OLD]}
    stats = {'status': 'passed', 'decision_id': 'MILI-D-20261011-027', 'classification': 'UMD',
             'meshes': len(d), 'supported_meshes': int(eligible.sum()), 'unsupported_meshes': int((~eligible).sum()),
             'candidate_meshes': int(cand.sum()), 'candidate_fraction_supported': float(cand.sum() / eligible.sum()),
             'candidate_zero_radiance_meshes': int((cand & d['Nighttime Radiance'].eq(0)).sum()),
             'candidate_zero_radiance_fraction': float(d.loc[cand, 'Nighttime Radiance'].eq(0).mean()),
             'contexts': {str(k): int(v) for k, v in d['Land Context'].value_counts().items()},
             'peer_groups': len(peer), 'all_peer_groups_independently_checked': True,
             'all_zero_peer_meshes': int(az.sum()), 'all_zero_supported_meshes': int((az & eligible).sum()),
             'insufficient_peer_meshes': int(small.sum()),
             'status_counts': {str(k): int(v) for k, v in d['Screen Status'].value_counts().items()},
             'land_context_changed_meshes': int(old['Land Context'].ne(new['Land Context']).sum()),
             'screen_state_changed_meshes': int((states(old) != states(new)).sum()),
             'preserved_igbp_source_fields': preserved, 'source_hashes': hashes,
             'sources_unchanged': True, 'output_sha256': sha(output), 'municipal_results_updated': False}
    (OUT / 'validation.json').write_text(json.dumps(stats, indent=2) + '\n')
    contract = {'decision_id': stats['decision_id'], 'classification': 'UMD', 'peer_dimensions': PEERS,
                'support_rule': 'At least 30 distinct meshes and peer maximum radiance > 0',
                'candidate_rule': 'Road density > 0 and > peer Q75; radiance <= peer Q25',
                'quantiles': 'linear', 'thresholds_changed': False, 'regressions_refitted': False,
                'zero_radiance_retained': True, 'unsupported_indicator': 'null',
                'municipal_context': 'IGBP historical evidence; UMD reconciliation pending'}
    (OUT / 'screening_contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    (OUT / 'README.md').write_text(
        '# UMD potential mismatch screen\n\nReproduce after preprocess_umd_mismatch_context.py with '
        '`python src/analyses/run_umd_mismatch_screen.py`. Decision MILI-D-20261011-027 changes only '
        'the land-context classification of the accepted comparable-context screen. Latest road/light '
        'year is 2024; matched census year is 2020. All peer groups pass direct NumPy checks; all '
        'core values, geographic assignments and non-land peer bands agree with the audited IGBP '
        'screen. Source hashes and parquet roundtrip pass. IGBP sources are preserved. Municipal '
        'results have not yet been reconciled to UMD. Candidates are relative high-road/low-radiance '
        'patterns, not verified overprovision or measured economic inactivity.\n')
    print(json.dumps({k: stats[k] for k in ['status', 'meshes', 'supported_meshes', 'unsupported_meshes',
        'candidate_meshes', 'candidate_fraction_supported', 'contexts', 'screen_state_changed_meshes']}, indent=2), flush=True)

if __name__ == '__main__':
    main()
