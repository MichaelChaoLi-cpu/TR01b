#!/usr/bin/env python3
"""Audit candidate road filters and source-field mappings, not density variables.

No final width threshold, road sample, geometry aggregation, or analytical
panel is selected. Run: python3 src/exp/audit_road_harmonization.py
"""
import csv
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-organization/tables'


def write(name, rows):
    with (OUT/name).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    source=next((ROOT/'data/exp/data-organization/source-tables').glob('n13_lines_2024_*.csv'))
    total=Counter();ordinary=Counter()
    for row in csv.DictReader(source.open(encoding='utf8')):
        total[row['N13_006']]+=1
        if row['N13_002']=='1' and row['N13_004'] in ('1','2','3','4'):
            ordinary[row['N13_006']]+=1
    labels={'1':'below 3 m','2':'3 to below 5.5 m','3':'5.5 to below 13 m',
            '4':'13 to below 19.5 m','5':'19.5 m and above','6':'unknown'}
    counts=[dict(width_code=k,width_label=labels[k],all_segments=total[k],ordinary_centerline_known_nonconstruction_status=ordinary[k],
                 note='Candidate attribute filter only; counts are line segments, not road length or density') for k in sorted(labels)]
    write('2024_candidate_filter_counts.csv',counts)
    mapping=[]
    for year in (2002,2003,2004,2010,2024):
        if year==2024:
            actual='qualified clipped line geometry'
            normalized='not supplied; must compute length divided by common mesh area'
            candidate='N13_006 codes 3,4,5; N13_002 code 1; N13_004 codes 1,2,3,4'
            area='common target mesh area in km2'
        elif year==2010:
            actual='N04_055';normalized='N04_056'
            candidate='N04_008 + N04_014 + N04_020 + N04_026 + N04_032'
            area='N04_002 in km2'
        else:
            actual='N04_037';normalized='N04_038'
            candidate='N04_008 + N04_014'
            area='N04_002 in m2'
        mapping.append(dict(road_year=year,total_actual_length_source=actual,total_normalized_length_source=normalized,source_area=area,
                            provisional_at_least_5_5m_classification=candidate,
                            final_width_rule_selected=False,
                            qualification='Matching class labels does not establish equivalent physical width, source coverage, or geometry representation'))
    write('candidate_road_density_crosswalk.csv',mapping)
    print('2024 pilot segments:',sum(total.values()))
    print('Ordinary centerline with known nonconstruction status:',sum(ordinary.values()))
    print('Provisional width-class >=5.5 m segments:',sum(ordinary[k] for k in ('3','4','5')))


if __name__=='__main__':main()
