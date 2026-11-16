#!/usr/bin/env python3
"""Independently clip each observed prefecture boundary combination and interior.
"""
from verify_regional_geometry import ROOT, main


if __name__ == '__main__':
    main(output_dir=ROOT / 'data/exp/data-preprocessing/prefecture', unit='prefecture',
         expected_strata=47,
         manifest_path=ROOT / 'data/exp/data-preprocessing/regional/reference/manifest.json')
