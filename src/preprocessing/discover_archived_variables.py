#!/usr/bin/env python3
"""Apply the installed variable-inventory skill to lossless archive views.

The default reader cannot inspect ZIP/GIS archives. Prior archive audits
provide unchanged attribute names and native-pixel views under data/exp.
Only active source years are inventoried here; no variables are selected.
"""
import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'.codex/skills/data-preprocessing/scripts/prepare_variable_list.py'
spec=importlib.util.spec_from_file_location('prepare_variable_list',SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def archives(root):
    files=[]
    for path in (root/'data/exp/data-organization/source-tables').glob('*.csv'):
        if '_1995_' not in path.name and not path.name.startswith('n01_'):
            files.append(path)
    files.extend(p for p in (root/'data/exp/data-organization/nighttime-pilot').glob('*_native_pixels.csv') if not p.name.startswith('1995'))
    return sorted(files)


module.discover_data_files=archives
sys.argv=[str(SCRIPT),'--root',str(ROOT),'--pretty']
if __name__=='__main__':module.main()
