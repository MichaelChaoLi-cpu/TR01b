"""User-approved 3-50 km fixed-distance pooled GWPR bandwidth search.

Use the current 383,390-mesh five-period cohort, 1,286 stratified centers,
whole-mesh holdout and identical estimable validation support for all 48 radii.
Reproduce: python3 src/analyses/run_gwpr_search_3_50km.py
"""
from run_gwpr_current_bandwidth_search import main, ROOT

if __name__ == '__main__':
    main(ROOT / 'data/exp/estimation-framework-planning/gwpr-common-cohort-3-50km/execution_contract.json',
         ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km')
