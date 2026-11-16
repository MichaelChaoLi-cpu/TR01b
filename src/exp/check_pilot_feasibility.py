#!/usr/bin/env python3
"""Supplement name-matching feasibility with explicit source-field evidence.

Counts diagnostic joint coverage only. No final sample is selected and no
analytical variables or harmonized road series are constructed.
"""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
VIEWS=ROOT/'data/exp/data-organization/source-tables'
OUT=ROOT/'data/exp/feasibility-check'


def rows(pattern):
    p=next(VIEWS.glob(pattern))
    return str(p.relative_to(ROOT)),list(csv.DictReader(p.open(encoding='utf8')))


def numeric(value):
    try:float(value);return True
    except ValueError:return False


def write(name,data):
    with (OUT/name).open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,list(data[0]));w.writeheader();w.writerows(data)


def main():
    coverage=[];mapping=[];joint={};flags=[]
    for road,pop,table in [(2002,2000,'T000146'),(2003,2005,'T000148'),(2004,2005,'T000148'),(2010,2010,'T000608')]:
        rp,roadrows=rows(f'n04_mesh_{road}_*.csv')
        pp,poprows=rows(f'population_{pop}_*.csv')
        total='N04_056' if road==2010 else 'N04_038'
        actual='N04_055' if road==2010 else 'N04_037'
        goodroad={r['N04_001'] for r in roadrows if all(numeric(r[n]) for n in ['N04_002',actual,total])}
        goodpop={r['KEY_CODE'] for r in poprows if numeric(r[table+'001'])}
        joint[road]=goodroad&goodpop
        coverage.append(dict(road_year=road,population_year=pop,road_listed=len(roadrows),road_numeric=len(goodroad),population_listed=len(poprows),population_numeric=len(goodpop),joint_numeric=len(joint[road]),source_anomalies_not_excluded=int(road==2010),note='Diagnostic counts; numerical validity is not measurement comparability or final sample eligibility'))
        mapping.extend([dict(construct='mesh_identifier',year=road,source_view=rp,field='N04_001',unit='standard third-level mesh code'),
                        dict(construct='actual_total_road_length',year=road,source_view=rp,field=actual,unit='m'),
                        dict(construct='supplied_normalized_road_length',year=road,source_view=rp,field=total,unit='m per km2'),
                        dict(construct='mesh_area',year=road,source_view=rp,field='N04_002',unit='km2' if road==2010 else 'm2'),
                        dict(construct='population_count',year=pop,source_view=pp,field=table+'001',unit='persons')])
    common=set.intersection(*joint.values())
    universe=set.union(*joint.values())
    for key in sorted(universe):
        r=dict(mesh_code=key)
        r.update({f'joint_numeric_{year}':int(key in ids) for year,ids in joint.items()})
        r['joint_numeric_all_four']=int(key in common)
        flags.append(r)
    write('pilot_joint_coverage.csv',coverage)
    write('candidate_field_mapping.csv',mapping)
    write('pilot_joint_coverage_flags.csv',flags)
    summary=dict(core_candidate_waves=4,joint_numeric_common_meshes=len(common),joint_numeric_union_meshes=len(universe),final_sample_selected=False,
                 six_wave_road_definition='unresolved',line_to_grid_length='not_constructed',population_absent_mesh_rule='not_decided',geographic_panel='not_constructed')
    (OUT/'pilot_feasibility_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
