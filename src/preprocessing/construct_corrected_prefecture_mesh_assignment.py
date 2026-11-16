#!/usr/bin/env python3
"""Apply the confirmed prefecture land-overlap rule to the corrected sample.

Geometry only; no nearest-prefecture fallback, source data or regression edits.
The nineteen no-land cases remain explicitly unassigned until a human decision.
"""
from construct_regional_mesh_assignment import ROOT, main


if __name__ == '__main__':
    main(output_dir=ROOT / 'data/exp/data-preprocessing/prefecture-population-zero-corrected',
         grouping={f'{i:02d}': [i] for i in range(1, 48)},
         decision_id='MILI-D-20261009-040', expected_meshes=228988,
         sample_path=ROOT / 'data/exp/figure-table-generation/national-pooled-population-zero-corrected/sample_membership.csv',
         manifest_path=ROOT / 'data/exp/data-preprocessing/regional/reference/manifest.json',
         unit='prefecture',
         grouping_source='https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html')
