#!/usr/bin/env python3
"""National Fixed-Effects Baseline, approved expansion MILI-D-20261009-015.

Framework: AnaSOP Sections 5-7; same original-scale two-way fixed-effects
estimator and mesh-clustered inference as the pilot. No source data changes.
"""
from pathlib import Path
from table_pilot_fixed_effects_baseline import main

ROOT = Path(__file__).resolve().parents[2]

if __name__ == '__main__':
    main(contract_path=ROOT/'data/exp/estimation-framework-planning/national-fixed-effects/estimation_decisions.json',
         qa_path=ROOT/'data/exp/figure-table-generation/national-fixed-effects')
