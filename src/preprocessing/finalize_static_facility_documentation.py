"""Finalize the approved construction contract and AnaSOP Section 4 only.

Executed within the data-preprocessing skill after successful input, linkage and
independent geographic validation. Historical estimates remain separate.
"""
from pathlib import Path
import hashlib
import json

import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/static-facilities'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    reports={name:json.loads((OUT/(name+'.json')).read_text()) for name in [
        'mesh_construction_validation','panel_linkage_validation','source_preservation_validation','independent_geodesic_validation']}
    assert all(r['status']=='passed' for r in reports.values())
    contract=json.loads((OUT/'decisions.json').read_text())
    temporal=json.loads((OUT/'temporal_contract.json').read_text())
    temporal['facility_identity_and_filters']='Confirmed and executed under MILI-D-20261010-017; bus variables remain candidates with identity-review flags.'
    temporal['augmented_panel_written']=True
    (OUT/'temporal_contract.json').write_text(json.dumps(temporal,indent=2)+'\n')
    rows=[]
    for dataset,spec in contract['datasets'].items():
        for var in spec['variables']:
            rows.append(dict(source_dataset=dataset,**var,output=spec['output'],script=spec['script']))
    pd.DataFrame(rows).to_csv(OUT/'constructed_variable_list.csv',index=False)

    definitions={
        'schools':'Observed school/campus records, retaining school type and campus code; merge only identical names and geometries within those partitions.',
        'medical':'Observed hospital and general/dental clinic records; merge exact name/geometry/type duplicates. Suspended and in-company records remain included.',
        'logistics':'Observed freight-related facilities; merge exact name/geometry/type/subtype duplicates. Preserve all six observed broad classes.',
        'visitor_facilities':'Observed visitor/event facilities; merge exact name/geometry/type duplicates. Preserve all six classes; these data do not enumerate all commerce.',
        'railway':'Official passenger-station groups; use the designated station sections to locate each group. Preserve the one missing designated-code flag and use its sole observed section.',
        'airports':'Operating airports with jet or propeller scheduled services, represented by linked terminal points. Shared terminal identifiers are counted once.',
        'bus_candidates':'Name-screened candidate stop locations; merge only exact original name/coordinate duplicates across both sources. Keep all screening flags and pending facility-identity review.'}
    block=[
        '### Constructed Static Facility Mesh Variables','',
        'The approved static supplements are now constructed for the complete 972,800-mesh grid and linked to both five-period datasets. The complete panel retains 4,864,000 rows; the unchanged balanced cohort retains 228,988 meshes and 1,144,940 rows. Each augmented panel contains 79 columns, including 38 retained analytical facility candidates plus source-year, linkage and quality references. Existing substantive columns are preserved exactly. The candidate role is TBD: retaining a variable does not add it to any regression.',
        '',
        r'For observed selected facility locations \(\mathcal{F}_k^{(s)}\), define \(C_{ik}^{(s)}=\sum_{j\in\mathcal{F}_k^{(s)}}\mathbf{1}\{p_j\in M_i\}\). Allocate points to the common mesh datum and use south/west-inclusive, north/east-exclusive boundaries. For a mesh centre \(c_i\), define \(d_{ik}^{(s)}=\min_{j\in\mathcal{F}_k^{(s)}}\operatorname{dist}_{\mathrm{GRS80}}(c_i,p_j)/1000\), in kilometres. Distances represent geographic proximity to observed representative points, rather than network travel time.',
        '',
        '| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |',
        '| --- | --- | --- | --- | --- | --- |']
    for dataset,spec in contract['datasets'].items():
        kind=Path(spec['script']).stem.removeprefix('preprocess_static_')
        for var in spec['variables']:
            if var['is_final_variable']!='yes':continue
            name=var['readable_name']
            formal=r'\(d_{ik}^{(s)}\), km, repeated unchanged across five periods.' if name.startswith('Distance to') else r'\(C_{ik}^{(s)}\), observed selected records or locations, repeated unchanged across five periods.'
            block.append(f'| {name} | {var["full_name"]} | TBD | {formal} | {definitions[kind]} | yes |')
    block += ['',
        'School, medical, logistics and visitor/event category counts partition their corresponding total counts. Retaining a total and all its categories does not imply simultaneous use in a model because these columns are exactly collinear. Quantity variables enumerate deduplicated observed functional records or locations; they do not independently certify all distinct operating institutions.',
        '',
        'All 284 selected source ZIPs remain checksum- and CRC-verified. All selected geocoded facilities lie within the study grid; no missing coordinates were filled. Count zero denotes no selected observed record in a mesh under the complete downloaded archive coverage, and does not certify the absence of every real facility. Source omissions and changing historical coverage are not resolved by the static assumption. Retain all five periods, population zeros, islands and existing road missingness.',
        '',
        'The bus supplement contains 778 exact-name-coordinate candidate locations from 1,736 source records. Retain peripheral, air-related, port-related, freight-related and abbreviation flags, plus explicit coverage-limited and identity-review-pending fields. The separately documented 63 unlocated ordinary-stop records cannot be located or filled. Bus candidates are not a verified terminal inventory. Airport selection contains 87 eligible airport reference sites represented by 86 distinct terminal service points; one shared terminal reference is counted once. The railway supplement contains 9,048 official station groups and preserves one source representative-code inconsistency. Independent exhaustive geodesic checks agree within one millimetre.',
        '',
        'Preserve actual source editions and the Facility Static Assumption field on every augmented record. Land-cover data have not yet been acquired or constructed, and are not represented by a placeholder or another variable. Existing national, regional, prefecture and local estimates retain their prior road/population specification; this data construction does not refit those models.',
        '']
    section='\n'.join(block)
    assert section.isascii()
    assert r'\sum' in section and r'\mathbf{1}' in section
    assert section.count(r'\(')==section.count(r'\)')
    sop=ROOT/'docs/AnaSOP.md';text=sop.read_text()
    prefix,remaining=text.split('## 4. Variable Construction  /  Key Variables\n',1)
    old4,suffix=remaining.split('## 5. Identification Strategy\n',1)
    updated=old4.replace('Hold selected passenger-airport characteristics fixed; source eligibility remains a separate construction choice.',
        'Hold passenger-airport characteristics fixed under the operating and scheduled-service filter; count shared terminal points once.')
    updated=updated.replace('Facility identities, passenger-airport selection and final readable analytical variables require the remaining construction choices; no augmented regression is implied as completed.',
        'The confirmed constructions below are attached to the panel. Bus identity review remains pending; no augmented regression is implied as completed.')
    if '### Constructed Static Facility Mesh Variables\n' in updated:
        updated=updated.split('### Constructed Static Facility Mesh Variables\n',1)[0]
    updated=updated.rstrip()+'\n\n'+section+'\n'
    sop.write_text(prefix+'## 4. Variable Construction  /  Key Variables\n'+updated+'## 5. Identification Strategy\n'+suffix)
    rewritten=sop.read_text();assert rewritten.split('## 4. Variable Construction  /  Key Variables\n',1)[0]==prefix
    assert rewritten.split('## 5. Identification Strategy\n',1)[1]==suffix
    for row in rows:assert row['readable_name'].isascii()

    linkage=reports['panel_linkage_validation']
    table=['# Static facility mesh construction and five-period linkage','',
           'Completed under MILI-D-20261010-016 and MILI-D-20261010-017. This document is the current construction status; earlier discovery/acquisition inventories remain provenance checkpoints.','',
           '| Dataset | Retained units | Source edition |','| --- | ---: | ---: |',
           '| Schools and campuses | 56,807 | 2023 |','| Medical institutions | 181,149 | 2020 |',
           '| Logistics facilities | 8,348 | 2013 |','| Visitor/event facilities | 15,826 | 2014 |',
           '| Passenger railway station groups | 9,048 | 2024 |',
           '| Scheduled-service airport terminal points | 86, linked to 87 eligible reference sites | 2021 |',
           '| Bus terminal candidate name/location units | 778 | P11 2022 and P36 2023 |','',
           'Every retained location falls within the 972,800-mesh study grid. Counts and nearest-facility distances use the common mesh datum. Source years remain explicit. The time-invariance assumption repeats the same characteristics in 2002, 2003, 2004, 2010 and 2024.','',
           '## Saved outputs','',f'- Mesh table: `{linkage["mesh_table"]}` (972,800 rows, 67 columns).',
           '- Each of the seven source groups has its own readable-name processed parquet file in `data/processed/national/static_facilities/`.']
    for output in linkage['panel_outputs']:
        table.append(f'- `{output["output"]}`: {output["rows"]:,} rows, {output["columns"]} columns; all original columns preserved exactly.')
    table += ['',
        'Thirty-eight analytical candidate fields are documented in `constructed_variable_list.csv`; source-year and quality fields bring the additions to 66 columns. `static_variable_summary.csv` describes the complete mesh table. Category counts partition their total; totals and every category must not be inserted simultaneously into a regression.',
        '', '## Construction and limitations','']
    for kind,definition in definitions.items():table.append(f'- {kind}: {definition}')
    table += ['',
        'There are no statistical imputations, log transformations, rescaling, road-zero recoding, new island exclusions or model refits. Counts are observed selected records, not certifications that no unobserved facility exists. The original source records and duplicate membership remain in the source inventories; retained locations and source review flags are in `facility-ledgers/`.',
        '',
        'Airport regular-flight codes include both jet and propeller services. The two Fukuoka airport reference areas sharing one terminal identifier are represented by one passenger-terminal point. Railway group 010179 has no matching representative station code; its sole observed Echizen-Takefu section provides the point and the original identifier remains flagged. No source opening date is used to fabricate historical facilities.',
        '',
        'The 63 unlocated P11 stops remain separately documented and unfilled. Bus counts include named peripheral, airport, port, freight and abbreviation candidates with explicit flags; no candidate is silently certified as a bus terminal. Source archive coverage is complete, but terminal identity and actual-world inventory completeness are unresolved.',
        '',
        'Land cover is not acquired and is not added to these outputs. The previously saved coefficient artifacts continue to describe the original road/population regressions.',
        '', '## Reproduce locally','', '```bash',
        'python3 src/preprocessing/prepare_static_facility_meshes.py --stage bus-input',
        'PROJ_DATA=/opt/homebrew/share/proj python3 src/preprocessing/prepare_static_facility_meshes.py --stage geometry',
        'python3 src/preprocessing/prepare_static_facility_meshes.py --stage prepare',
        'python3 .codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py --root . --decisions data/exp/data-preprocessing/static-facilities/decisions.json --pretty']
    for spec in contract['datasets'].values():table.append('python3 '+spec['script'])
    table += ['python3 src/preprocessing/link_static_facility_panel.py',
              'python3 src/preprocessing/validate_static_facility_panel.py --stage prepare-checks',
              'PROJ_DATA=/opt/homebrew/share/proj python3 src/preprocessing/validate_static_facility_panel.py --stage geometry-checks',
              'python3 src/preprocessing/finalize_static_facility_documentation.py', '```','',
              'The source-inventory extraction is separately reproducible with `inspect_static_facility_sources.py --stage extract` followed by `--stage summarize`. GDAL geometry and Arrow-writing stages use separate processes to avoid the host libraries registering conflicting filesystem factories. All table operations use repository Python scripts and local pandas/PyArrow.','',
              '## Validation','',
              '- SHA256 and CRC rechecks of all 284 selected source archives pass.',
              '- Independent mesh-bound containment checks cover every retained facility location.',
              '- Count totals equal retained allocated source units; category sums equal each POI total.',
              '- Both panel outputs pass complete batched comparisons of all original columns and all static additions.',
              '- Independent exhaustive GDAL geodesic searches pass for all three proximity variables, including coincident points.',
              '- AnaSOP Section 4 uses English readable analytical names and ASCII mathematics; every other section is preserved.','',
              'Primary codebooks: [school classes](https://nlftp.mlit.go.jp/ksj/gml/codelist/SchoolClassCd-v2_0.html), [visitor facility classes](https://nlftp.mlit.go.jp/ksj/gml/codelist/facilityTypeCode.html), [logistics classes](https://nlftp.mlit.go.jp/ksj/gml/codelist/DistributionCenterCd.html), [regular flights](https://nlftp.mlit.go.jp/ksj/gml/codelist/RegularFlightCd.html).','']
    (OUT/'CONSTRUCTION.md').write_text('\n'.join(table))
    oldreadme=(OUT/'README.md').read_text()
    receipt='## Current construction status\n\nThe facility mesh data and both augmented five-period panels are complete and verified under MILI-D-20261010-017. See [CONSTRUCTION.md](CONSTRUCTION.md) and [constructed_variable_list.csv](constructed_variable_list.csv). Earlier pending construction statements below describe the preserved discovery checkpoint.\n\n'
    if not oldreadme.startswith(receipt):(OUT/'README.md').write_text(receipt+oldreadme)
    protected=ROOT/'data/exp/gwpr-pooled-five-period-2024/mesh-map-3km/local_coefficients.parquet'
    assert sha(protected)=='b0fa621c3567c96a893a0ab8a364a54cec1e17964e84a479b0b873900b8b79bf'
    report=dict(status='passed',decision_id='MILI-D-20261010-017',source_archives_verified=284,
                numerical_outputs_verified=True,geodesic_reference_verified=True,ana_sop_sections_changed=[4],
                section_4_readable_names_and_ascii_mathematics=True,other_ana_sop_sections_preserved=True,
                original_local_coefficient_hash_preserved=True,panel_outputs=linkage['panel_outputs'],
                land_cover_added=False,regressions_refitted=False)
    (OUT/'delivery_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Static-facility delivery verified; AnaSOP Section 4 and scoped construction documentation updated.',flush=True)


if __name__=='__main__':main()
