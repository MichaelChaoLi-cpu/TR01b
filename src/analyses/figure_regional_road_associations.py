#!/usr/bin/env python3
"""Regional Road Associations.

Plan: nine-region baseline/extended forest comparison and extended-coefficient map.
Framework: AnaSOP Sections 5-7, same-sample pooled OLS and mesh-clustered CR1.
Run locally: uv run python src/analyses/figure_regional_road_associations.py
"""
from administrative_association_map_helpers import generate

if __name__ == "__main__":
    generate("regional", "Regional Road Associations", "regional_road_associations")
