#!/usr/bin/env python3
"""Prefecture Road Associations.

Plan: forty-seven-prefecture forest comparison and extended-coefficient map.
Framework: AnaSOP Sections 5-7, UMD pooled models with identifiable core terms,
constant/redundant nuisance controls omitted, and retained-rank mesh-clustered CR1.
Run locally: uv run python src/analyses/figure_prefecture_road_associations.py
"""
from administrative_association_map_helpers import generate

if __name__ == "__main__":
    generate("prefecture", "Prefecture Road Associations", "prefecture_road_associations")
