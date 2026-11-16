#!/usr/bin/env python3
"""Reconstruct two internally inconsistent 2010 pilot length fields.

Only the total-length repair enters the selected processed road variables.
The class-level repair is an audited reference, not a change to raw data.
Neither repair is represented as an official correction.
"""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/exp'))
from audit_source_archives import dbf

OUT = ROOT / 'data/exp/data-preprocessing/pilot'
RAW = ROOT / 'data/raw/roads/n04_mesh/2010/N04-10_5030-jgd_GML.zip'
ACTUAL = [f'N04_{i:03d}' for i in range(7, 50, 6)]
NORMALIZED = [f'N04_{i:03d}' for i in range(8, 51, 6)]


def main():
    source_hash = hashlib.sha256(RAW.read_bytes()).hexdigest()
    with zipfile.ZipFile(RAW) as archive:
        rows, descriptors, deleted = dbf(archive.read(next(n for n in archive.namelist() if n.endswith('.dbf'))))
        fields = [d[0] for d in descriptors]
        tree = ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.xml') and not n.startswith('KS-META'))))
        gml = {}
        for element in tree.iter():
            if element.tag.endswith('}tupleList') and element.text:
                for line in element.text.strip().splitlines():
                    parts = line.strip().split(',')
                    assert parts[0] not in gml
                    gml[parts[0]] = parts
    source = pd.DataFrame(rows)
    view = pd.read_csv(ROOT / 'data/exp/data-organization/source-tables/n04_mesh_2010_N04-10_5030-jgd_GML.csv', dtype=str, keep_default_na=False)
    assert source.equals(view), 'Lossless attribute view differs from raw DBF'
    for mesh in ['50302281', '50306730']:
        row = source[source.N04_001 == mesh].iloc[0]
        assert row[fields].tolist() == gml[mesh], 'GML and DBF do not agree'
    numeric = source.apply(pd.to_numeric, errors='coerce')
    valid = numeric[ACTUAL + NORMALIZED + ['N04_002', 'N04_055', 'N04_056']].notna().all(axis=1)
    frame = numeric[valid].copy()
    pair_errors = []
    for field in ACTUAL + ['N04_055']:
        density_field = f'N04_{int(field.split("_")[1]) + 1:03d}'
        residual = frame[density_field] - frame[field] / frame.N04_002
        pair_errors.extend((str(int(frame.loc[i, 'N04_001'])), field) for i in frame.index[residual.abs() > .51])
    assert set(pair_errors) == {('50302281', 'N04_055'), ('50306730', 'N04_025')}
    repairs = []
    for mesh, field in [('50302281', 'N04_055'), ('50306730', 'N04_025')]:
        index = frame.index[frame.N04_001 == int(mesh)].item()
        row = frame.loc[index]
        if field == 'N04_055':
            replacement = int(row[ACTUAL].sum())
            derivation = 'sum of eight mutually exclusive source width-class actual lengths'
        else:
            replacement = int(row.N04_055 - row[[c for c in ACTUAL if c != field]].sum())
            derivation = 'source total actual length minus the seven other source width classes'
        density_field = f'N04_{int(field.split("_")[1]) + 1:03d}'
        assert abs(row[density_field] - replacement / row.N04_002) <= .51
        repairs.append(dict(mesh_code=mesh, road_year=2010, original_field=field,
                            original_length_m=int(row[field]), reconstructed_length_m=replacement,
                            source_area_km2=float(row.N04_002), source_normalized_length_m_per_km2=int(row[density_field]),
                            reconstructed_normalized_length_m_per_km2=replacement / row.N04_002,
                            derivation=derivation, source_representations_agree=True,
                            applied_to_selected_road_length=field == 'N04_055',
                            official_correction=False))
        frame.loc[index, field] = replacement
    assert (frame.N04_055 == frame[ACTUAL].sum(axis=1)).all()
    assert ((frame.N04_056 - frame[NORMALIZED].sum(axis=1)).abs() <= 2).all()
    maximum_residual = 0.
    for field in ACTUAL + ['N04_055']:
        density_field = f'N04_{int(field.split("_")[1]) + 1:03d}'
        residual = (frame[density_field] - frame[field] / frame.N04_002).abs()
        assert (residual <= .51).all()
        maximum_residual = max(maximum_residual, float(residual.max()))
    pd.DataFrame(repairs).to_csv(OUT / '2010_road_reconstruction.csv', index=False)
    report = dict(source=str(RAW.relative_to(ROOT)), source_sha256=source_hash,
                  raw_rows=len(source), numeric_rows=int(valid.sum()), deleted_dbf_rows=deleted,
                  repairs=repairs, maximum_post_reconstruction_normalization_residual_m_per_km2=maximum_residual,
                  exact_total_actual_class_sums_after_reconstruction=True,
                  normalized_class_sum_rounding_tolerance_m_per_km2=2,
                  normalized_total_not_changed=True, raw_not_modified=True,
                  source_geometry_or_coverage_comparability_established=False,
                  confirmed_decision='MILI-D-20261009-005')
    assert hashlib.sha256(RAW.read_bytes()).hexdigest() == source_hash
    (OUT / '2010_road_reconstruction_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
