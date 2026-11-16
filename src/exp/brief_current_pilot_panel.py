#!/usr/bin/env python3
"""Reuse the briefing reader and append current coverage to the historical overview."""
from pathlib import Path
from argparse import Namespace
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.codex/skills/data-briefing/scripts/create_data_briefing.py'
spec = importlib.util.spec_from_file_location('pilot_briefing', SCRIPT)
briefing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(briefing)


def update_current_overview(root, output_dir, inventory, time_candidates,
                            skipped_files, variable_count, distribution_count):
    assert len(inventory) == 1 and inventory[0]['rows'] == 32000 and variable_count == 13
    assert not skipped_files and distribution_count == 0
    path = root / 'docs/AnaSOP.md'
    old = path.read_text()
    prefix, remainder = old.split('## 3. Data Overview', 1)
    section, suffix = remainder.split('## 4. Variable Construction  /  Key Variables', 1)
    title = '### Current Processed Panel and Initial Baseline Sample'
    if title in section:
        start = section.index(title)
        end = section.find('\n### ', start + len(title))
        section = section[:start] + (section[end:] if end >= 0 else '')
    context = '\nThe initial source-audit descriptions below refer to the pre-processing inspection. The current processed-panel subsection records subsequent linkage and supersedes earlier statements that grid aggregation had not yet occurred.\n'
    if context.strip() not in section:
        section = context + section
    addition = '''### Current Processed Panel and Initial Baseline Sample

The linked pilot panel contains 32,000 observations, thirteen readable columns, 6,400 mesh identifiers, and five road-anchored periods. One linked panel and all thirteen columns were summarized in the focused update; no files were skipped. The sixteen separately preserved processed pilot datasets include the linked panels and per-source outputs. This is a Fukuoka-area pilot, not a completed nationwide panel.

| Road period | Matched population year | Light year | Jointly numerical meshes |
| --- | ---: | ---: | ---: |
| 2002 | 2000 | 2002 | 2,704 |
| 2003 | 2005 | 2003 | 3,088 |
| 2004 | 2005 | 2004 | 3,098 |
| 2010 | 2010 | 2010 | 3,206 |
| 2024 | 2020 | 2024 | 3,206 |

The approved initial baseline uses the 2,663 meshes with numerical Road Length Density, Population, and Nighttime Radiance in all four historical periods, totaling 10,652 observations. This analytical subset leaves all stored meshes and periods intact. The national sample remains pending acquisition and comparability checks. The latest period remains a stored candidate and is outside this initial trial because cross-source equivalence remains unresolved.

These are irregular snapshots. The 2005 population snapshot is reused in the two middle periods, and population-road offsets remain explicit. Unknown and unlisted historical road observations and unlisted population observations are missing rather than confirmed zeros. All light observations retain their geographically aligned full-mesh mean and valid-pixel coverage. Numeric coverage and nonzero recorded variation do not establish invariant road measurement, causal identification, or local-model feasibility.

No additional distribution or time-series figures were generated for this focused update; the user selected a single initial regression table. Existing exploratory distributions remain available from the initial briefing.

'''
    new = prefix + '## 3. Data Overview' + section.rstrip() + '\n\n' + addition + '## 4. Variable Construction  /  Key Variables' + suffix
    assert new.isascii()
    assert new.split('## 3. Data Overview', 1)[0] == prefix
    assert new.split('## 4. Variable Construction  /  Key Variables', 1)[1] == suffix
    path.write_text(new)
    return 'docs/AnaSOP.md'


def main():
    briefing.update_anasop_data_overview = update_current_overview
    result = briefing.create_briefing(Namespace(root=str(ROOT),
        output='data/exp/data-briefing/current-pilot-panel',
        inputs=['data/processed/pilot/road_population_light_pilot_preprocessed.parquet'],
        include_time_series='no', max_distribution_plots=0, max_categorical_levels=50,
        max_time_columns=3, max_time_series_variables=6))
    result['figure_scope'] = 'User approved one regression table; no new figures.'
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
