#!/usr/bin/env python3
"""Refine the national baseline allocation to forty-seven prefectures.

Reuse the existing source archives and validated geometric construction, while
leaving regional assignments and prior results intact. Save a separate product.
"""
from construct_regional_mesh_assignment import ROOT, main


if __name__ == '__main__':
    main(output_dir=ROOT / 'data/exp/data-preprocessing/prefecture',
         grouping={f'{i:02d}': [i] for i in range(1, 48)},
         decision_id='MILI-D-20261009-020',
         manifest_path=ROOT / 'data/exp/data-preprocessing/regional/reference/manifest.json',
         unit='prefecture',
         grouping_source='https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html')
