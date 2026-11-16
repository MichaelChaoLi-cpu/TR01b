"""Verify current administrative tables and the three-kilometre local baseline.

Read-only with respect to data inputs and estimates; writes delivery diagnostics.
Reproduce: python3 src/analyses/check_four_layers_3km.py
"""
from check_current_four_layers import main, ROOT

if __name__ == '__main__':
    main(ROOT / 'data/exp/estimation-framework-planning/gwpr-common-cohort-local-3km/delivery_contract.json',
         ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km',
         ROOT / 'data/exp/gwpr-pooled-current-common-cohort/local-fit-3km',
         ROOT / 'data/exp/four-layer-current-baseline-3km')
