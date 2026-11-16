#!/usr/bin/env python3
"""Use the accepted regional geometry rule for the corrected national sample.

Geometry-only GDAL process; Arrow staging runs separately. Preserve old outputs.
"""
from pathlib import Path
from construct_regional_mesh_assignment import main

ROOT = Path(__file__).resolve().parents[2]

if __name__ == '__main__':
    main(output_dir=ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected',
         decision_id='MILI-D-20261009-034',expected_meshes=228988,
         sample_path=ROOT / 'data/exp/figure-table-generation/national-fixed-effects-population-zero-corrected/sample_membership.csv')
