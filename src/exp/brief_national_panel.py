#!/usr/bin/env python3
"""Update current national data briefing via its responsible bundled reader."""
from pathlib import Path
from argparse import Namespace
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('national_briefing',ROOT/'.codex/skills/data-briefing/scripts/create_data_briefing.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def update(root,output_dir,inventory,time_candidates,skipped_files,variable_count,distribution_count):
    v=json.loads((root/'data/exp/data-preprocessing/national/panel_validation.json').read_text())
    assert len(inventory)==1 and inventory[0]['rows']==v['complete_panel_rows'] and variable_count==13
    assert not skipped_files and distribution_count==0
    p=root/'docs/AnaSOP.md';old=p.read_text()
    prefix,remainder=old.split('## 3. Data Overview',1)
    section,suffix=remainder.split('## 4. Variable Construction  /  Key Variables',1)
    marker='### Current National Historical Panel'
    if marker in section:
        start=section.index(marker);end=section.find('\n### ',start+len(marker))
        section=section[:start]+(section[end:] if end>=0 else '')
    addition=f'''{marker}

The national extension reads all 605 historical road archives, 453 matched population archives, and four global light archives. Raw-file checksums agree with the acquisition manifest. The union contains {v['national_primary_tiles']} primary tiles and {v['complete_meshes']:,} standard meshes. The linked historical panel has {v['complete_panel_rows']:,} observations and thirteen readable columns; one linked dataset and thirteen columns were summarized without skipped files. Missing and zero values retain their confirmed meanings. Earlier disclosure metadata are unavailable.

The three census totals are 126,925,843, 127,767,994, and 128,057,352 persons in 2000, 2005, and 2010, matching official national totals. This validates population acquisition and aggregation totals; it does not establish road coverage equivalence. Joint numerical counts are 140,134, 169,760, 170,155, and 176,468 meshes in the four periods. The approved complete-four-period rule yields {v['balanced_estimation_meshes']:,} meshes and {v['balanced_estimation_records']:,} observations across {v['balanced_primary_tiles']} primary tiles. This is a nationwide available-data sample, not every land or inhabited mesh.

Population years remain 2000, 2005, 2005, and 2010 against road/light years 2002, 2003, 2004, and 2010. The reused middle population snapshot contributes no independent population change. Source-unlisted observations remain missing; no coast or island mask, imputation, source scaling, or log transformation is introduced. The latest period remains outside this baseline pending source harmonization.

Light aggregation measures geographic pixel-mesh intersections in local metric projections. A scalable shared-boundary implementation passed 456 independent geometric intersection checks and reproduces the existing pilot radiance within 1.6e-10. Complete raster support does not identify population or road absence. Three additional national 2010 length-normalization inconsistencies are flagged, with supplied density retained. No further anomaly correction was selected.

No additional figures were generated for the requested single national baseline table. The pilot descriptions above remain historical workflow evidence; the national panel is the active scope of the next estimate.

'''
    new=prefix+'## 3. Data Overview'+section.rstrip()+'\n\n'+addition+'## 4. Variable Construction  /  Key Variables'+suffix
    assert new.isascii() and new.split('## 4. Variable Construction  /  Key Variables',1)[1]==suffix
    p.write_text(new);return 'docs/AnaSOP.md'


if __name__=='__main__':
    module.update_anasop_data_overview=update
    result=module.create_briefing(Namespace(root=str(ROOT),output='data/exp/data-briefing/national-panel',
        inputs=['data/processed/national/road_population_light_national_preprocessed.parquet'],include_time_series='no',
        max_distribution_plots=0,max_categorical_levels=50,max_time_columns=3,max_time_series_variables=6))
    print(json.dumps(result,indent=2))
