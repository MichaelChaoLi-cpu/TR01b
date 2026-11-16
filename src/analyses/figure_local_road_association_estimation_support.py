#!/usr/bin/env python3
"""Local Road Association Estimation Support.

Plan: independent appendix map of local estimability and small-neighborhood flags.
Framework: AnaSOP Sections 5-7, unchanged extended UMD pooled local estimates at
the selected 5 km radius; actual mesh footprints, no significance inference.
Run locally: uv run python src/analyses/figure_local_road_association_estimation_support.py
"""
from figure_local_road_associations_across_japan import main

if __name__ == "__main__":
    main("support")
