"""Current three-kilometre geographically weighted pooled baseline.

Five periods; intercept, road density and population; all 383,390 focal meshes.
Reproduce from a local terminal: python3 src/analyses/run_gwpr_local_3km.py
"""
from run_gwpr_current_local import main, ROOT

if __name__ == '__main__':
    main(ROOT / 'data/exp/estimation-framework-planning/gwpr-common-cohort-local-3km/execution_contract.json',
         ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km',
         ROOT / 'data/exp/gwpr-pooled-current-common-cohort/local-fit-3km')
