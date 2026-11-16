#!/usr/bin/env python3
"""Validate the confirmed geographic allocation and stage typed input for Arrow.

Run after the separate GDAL geometry process; preserve Mesh Code as text.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/regional'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output_dir=OUT, expected_meshes=134830, expected_cross_region_meshes=236):
    csv_path = output_dir / 'mesh_region_confirmed_input.csv'
    geometry = json.loads((output_dir / 'geometry_validation.json').read_text())
    assert geometry['status'] == 'passed' and not geometry['unassigned_meshes']
    frame = pd.read_csv(csv_path, dtype={'mesh_code': 'string', 'region': 'string', 'assignment_status': 'string'})
    overlap = pd.read_csv(output_dir / 'mesh_region_overlaps.csv', dtype={'mesh_code': 'string', 'region': 'string'})
    assert len(frame) == expected_meshes and frame.mesh_code.is_unique
    assert frame.mesh_code.str.fullmatch(r'[0-9]{8}').all()
    assert frame.assignment_status.eq('assigned').all() and frame.notna().all().all()
    assert not overlap.duplicated(['mesh_code', 'region']).any()
    assert overlap.land_overlap_m2.gt(0).all()
    indexed = frame.set_index('mesh_code')
    winner = overlap.sort_values(['mesh_code', 'land_overlap_m2'], ascending=[True, False]).drop_duplicates('mesh_code').set_index('mesh_code')
    assert winner.region.reindex(indexed.index).equals(indexed.region)
    totals = overlap.groupby('mesh_code').land_overlap_m2.sum().reindex(indexed.index)
    assert np.allclose(totals / 1e6, indexed.total_land_overlap, rtol=1e-12, atol=1e-12)
    assert np.allclose(winner.land_overlap_m2.reindex(indexed.index) / 1e6, indexed.region_land_area, rtol=1e-12, atol=1e-12)
    assert np.allclose(indexed.region_land_area / indexed.total_land_overlap, indexed.region_land_share, rtol=1e-12, atol=1e-12)
    assert overlap.groupby('mesh_code').size().gt(1).reindex(indexed.index).equals(indexed.cross_region_mesh)
    assert int(frame.cross_region_mesh.sum()) == (geometry['cross_region_meshes'] if expected_cross_region_meshes is None else expected_cross_region_meshes)
    assert frame.region.value_counts().to_dict() == geometry['region_mesh_counts']
    staged = output_dir / 'mesh_region_confirmed_input.parquet'
    frame.to_parquet(staged, index=False)
    pd.DataFrame([{'Region': name, 'Meshes': count, 'Observations': count * 4} for name, count in geometry['region_mesh_counts'].items()]).to_csv(output_dir / 'region_sample_counts.csv', index=False)
    report = dict(status='passed', mesh_codes_preserved_as_text=True, unique_meshes=len(frame),
                  maximum_area_assignment_verified=True, boundary_flags_verified=True,
                  area_and_share_readback_verified=True, region_counts=geometry['region_mesh_counts'],
                  geometry_source_sha256=sha(csv_path), confirmed_input_sha256=sha(staged),
                  substantive_panel_modified=False)
    (output_dir / 'classification_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
