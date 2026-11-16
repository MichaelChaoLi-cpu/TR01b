#!/usr/bin/env python3
"""Independently check corrected prefecture boundary and interior allocations."""
from verify_regional_geometry import ROOT, main


if __name__ == '__main__':
    main(output_dir=ROOT / 'data/exp/data-preprocessing/prefecture-population-zero-corrected',
         unit='prefecture', expected_strata=47,
         manifest_path=ROOT / 'data/exp/data-preprocessing/regional/reference/manifest.json')
