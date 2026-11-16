"""National Pooled Regression: approved current common cohort.
Framework: AnaSOP Sections 5-7; intercept, road density, population,
mesh-clustered CR1, original units, five periods and no fixed effects.
Reproduce from a local terminal: python3 src/analyses/table_current_national_pooled.py
"""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from rerun_current_common_pooled import main
if __name__ == '__main__':
    main('national')
