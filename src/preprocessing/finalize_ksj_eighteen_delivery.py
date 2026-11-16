"""Document validated construction, changing only AnaSOP Section 4."""
from pathlib import Path
import hashlib
import json
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'
ACQ = ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def separate_section(text):
    start = re.search(r'^## 4\. ', text, re.M).start()
    end = re.search(r'^## 5\. ', text, re.M).start()
    return text[:start], text[start:end], text[end:]


def main():
    decisions = json.loads((OUT / 'decisions.json').read_text())
    validation = json.loads((OUT / 'construction_validation.json').read_text())
    assert validation['status'] == 'passed' and decisions['confirmed']
    geometry = json.loads((OUT / 'geometry_construction_report.json').read_text())
    link = validation['panel_validation']
    frame = pd.DataFrame(validation['datasets'])
    frame.to_csv(OUT / 'mesh_construction_summary.csv', index=False)
    years = {r['kind']: r for r in geometry['datasets']}
    constructions = {
        'fuel_stations': 'Observed station locations; exact address, coordinates and official class.',
        'roadside_stations': 'Observed named stations; retain all official functional flags as duplicate partitions.',
        'expressway_nodes': 'Current 2025 records with end year 9999 and start year at most 2025; retain official types 1-4 and inconsistent relation IDs.',
        'ports': 'Observed representative port points; preserve both official classifications.',
        'fishing_ports': 'Observed representative fishing-port points; retain official class.',
        'scheduled_passenger_routes_nodes': 'Observed named passenger-route port nodes; route lines remain references.',
        'heliports': 'Observed named landing locations; preserve official type and category.',
        'welfare': 'Observed named welfare functional records; retain the three-level classification.',
        'culture': 'Observed cultural and sports records; retain official class and closed-status references.',
        'municipal_offices_meeting_facilities': 'Observed municipal offices and meeting facilities; retain official class.',
        'national_prefectural_offices': 'Observed national and prefectural institution points; retain official class.',
        'police': 'Observed police facility points by official class; jurisdiction polygons remain references.',
        'fire_services': 'Observed fire-service facility points by official class; jurisdiction polygons remain references.',
        'post_offices': 'Observed postal facility points by official class; retain suspended facilities.',
        'research_institutions': 'Observed named research institutions; preserve operator class.',
        'local_industry': 'Observed named local-industry functional records; retain four functional flags as partitions.',
        'urban_parks_legacy': 'Observed named representative urban-park points; retain official park class.',
        'tourism_resources': 'Native Point and MultiPoint resources; count a deduplicated parent at most once per occupied mesh. Preserve lines and polygons as excluded references.',
    }
    subsection = '\n### Constructed Eighteen Additional KSJ Snapshot Counts\n\n'
    subsection += (
        'The confirmed additional supplement constructs eighteen analytical count candidates on the existing '
        '972,800-mesh grid. The complete augmented panel retains 4,864,000 observations and the balanced cohort '
        'retains 228,988 meshes and 1,144,940 observations. Both now contain 208 readable columns: their previous '
        '95 fields are preserved exactly, and the supplement adds eighteen counts and 95 source-year, coverage, '
        'duplicate, geometry, datum and static-assumption references. Candidate regression roles remain TBD; '
        'this construction does not select or refit a regression.\n\n'
        'For selected deduplicated units of category \\(k\\) in snapshot \\(s\\), let '
        '\\(\\mathcal{P}_j^{(s)}\\) contain the native point locations of unit \\(j\\). Define '
        '\\(C_{ik}^{(s)}=\\sum_{j\\in\\mathcal{F}_k^{(s)}}\\mathbf{1}\\{\\mathcal{P}_j^{(s)}\\cap M_i\\ne\\varnothing\\}\\). '
        'Each unit contributes at most once per mesh. Ordinary point units occupy one mesh; native multi-location '
        'tourism resources may occupy multiple meshes. Under the approved static assumption, '
        '\\(C_{itk}=C_{ik}^{(s)}\\) in 2002, 2003, 2004, 2010 and 2024.\n\n'
        '| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |\n'
        '| --- | --- | --- | --- | --- | --- |\n')
    table_lines = []
    summary = '| Category | Archive / reference year | Selected units | Exact duplicate records | Unit-mesh counts | Positive meshes |\n| --- | --- | ---: | ---: | ---: | ---: |\n'
    for item in geometry['datasets']:
        name = item['analytical_name']; kind = item['kind']
        table_lines.append(f'| {name} | {name} | TBD | \\(C_{{ik}}^{{(s)}}\\), replicated unchanged across five periods. | {constructions[kind]} | yes |')
        date = '; reference date 2019-01-01' if kind == 'roadside_stations' else ''
        summary += f"| {name} | {item['archive_year']} / {item['reference_year']}{date} | {item['unique_units']:,} | {item['exact_duplicate_records']} | {item['in_grid_unit_mesh_memberships']:,} | {item['positive_meshes']:,} |\n"
    subsection += '\n'.join(table_lines) + '\n\n'
    subsection += (
        'Merge records only within a category when the original nonmissing name or address, native coordinate '
        'geometry and agreed official class or function partition match exactly. Preserve anonymous records '
        'individually. Apply no name normalization, proximity merge, cross-category merge or additional operating-status '
        'filter. All original attributes, source identifiers, duplicate memberships and reference geometries remain '
        'traceable in the source and construction ledgers. No combined total across categories is defined.\n\n'
        'Use each file datum where available and the documented official product datum where its projection file is '
        'absent; retain the latter as a mesh quality flag. Transform locations to the established JGD2000 common-grid '
        'datum and preserve the established boundary convention. Every selected point is located within this grid. '
        'All 294 original archives remain checksum-verified and unchanged. Source text decoding is verified against '
        'the complete native character-field byte inventory before name-based duplicate decisions.\n\n'
        'The selected records yield 697,404 deduplicated units after removing 36 duplicate count contributions. '
        'The expressway supplement retains 2,384 current records and flags three inconsistent relation IDs without '
        'collapsing their distinct names, classes or locations. The tourism supplement retains 17,245 deduplicated '
        'point-based resources and 17,293 resource-mesh memberships, excluding 85 line and 1,797 polygon source '
        'features from the point count while retaining them as reference geometries. Jurisdiction polygons, port '
        'boundaries, passenger routes and expressway lines do not add facility counts.\n\n'
        'Retain actual source editions: fuel stations use archive 2015 and reference 2016; roadside stations use '
        'edition 2018 with reference date 2019-01-01; expressway nodes use 2025; ports use 2014; fishing ports use '
        '2006; passenger-route ports use 2012; heliports use 2013; welfare facilities use 2023; cultural and sports '
        'facilities use 2013; municipal/meeting facilities and national/prefectural institutions use 2022; police '
        'and fire facilities use 2012; post offices use 2013; research and local-industry facilities use 2012; urban '
        'parks use 2011; tourism resources use 2014. These editions remain explicit throughout temporal replication, '
        'including the 2025 expressway edition. They are not historical observations in each study period.\n\n'
        'Count zero means that no selected observed unit is allocated to the mesh under completed downloaded archive '
        'coverage. It does not establish exhaustive real-world coverage or absence of all facilities. The tourism '
        'indicator is explicitly point-based. Retain unavailable source coverage as missing if encountered; no such '
        'archive-coverage gap occurs in these selected inputs. Apply no imputation, rescaling, logarithm, row '
        'deletion or island exclusion. Existing population zeros, road missingness, annual land-cover values and '
        'prior national, regional, prefecture and local estimates are preserved.\n\n')
    # Numeric narrative is checked against executed results rather than assumed.
    assert sum(r['unique_units'] for r in geometry['datasets']) == 697404
    assert sum(r['exact_duplicate_records'] for r in geometry['datasets']) == 36
    assert years['tourism_resources']['unique_units'] == 17245
    assert years['tourism_resources']['in_grid_unit_mesh_memberships'] == 17293
    assert link['columns_added'] == 113 and all(o['columns'] == 208 for o in link['outputs'])
    before = (OUT / 'AnaSOP_before_ksj.txt').read_bytes().decode('utf-8')
    current = (ROOT / 'docs/AnaSOP.md').read_bytes().decode('utf-8')
    pre, section, post = separate_section(current)
    bpre, _, bpost = separate_section(before)
    assert pre == bpre and post == bpost
    heading = '### Constructed Eighteen Additional KSJ Snapshot Counts'
    if heading in section:
        section = section[:section.index(heading)].rstrip() + '\n\n'
    updated = pre + section.rstrip() + '\n' + subsection + post
    (ROOT / 'docs/AnaSOP.md').write_bytes(updated.encode('utf-8'))
    check = (ROOT / 'docs/AnaSOP.md').read_bytes().decode('utf-8')
    apre, _, apost = separate_section(check)
    assert apre == bpre and apost == bpost
    assert subsection.isascii()
    assert not re.search(r'\b(?:P\d\d|N\d\d|C\d\d)_\d{3}\b|\.parquet|data/', subsection)
    report = '# Eighteen KSJ snapshot counts: completed construction\n\n'
    report += f"Confirmed under {decisions['decision_id']}; all source, ledger, mesh-sum and panel-preservation checks passed.\n\n"
    report += summary + '\n'
    report += (
        'Counts enumerate selected observed units and are not an exhaustive operating-facility census. Tourism '
        'counts use native point membership; 85 line and 1,797 polygon features remain excluded references. '
        'The 2025 expressway edition is retained explicitly and statically repeated with the other snapshots. '
        'No model was refitted.\n\n'
        'Eighteen source-specific readable-name parquets and the combined mesh supplement are in '
        'data/processed/national/ksj_eighteen_facilities/. Each source table retains all 972,800 meshes. '
        'The combined mesh table has 114 columns.\n\n')
    for item in link['outputs']:
        report += f"- {item['output']}: {item['rows']:,} rows, {item['columns']} columns; every prior value in 95 original fields preserved exactly.\n"
    report += (
        '\nReference fields preserve actual archive/reference years, roadside reference date, completed archive '
        'coverage, declared-datum fallback, duplicate flags, inconsistent expressway relation IDs, tourism '
        'multi-location membership and point-only scope, and the static assumption. All selected units are '
        'located and in-grid. Coverage zero is a selected-record zero rather than imputed missing data.\n\n'
        'Original attributes remain in source-inventory/, while construction-ledgers/ links every original '
        'feature to its deduplicated unit or exclusion reason and preserves each unit\'s source/target coordinates. '
        'source_archive_audit.json includes a full DBF character-byte encoding audit. Missing CPG files in modern '
        'bundles are decoded using the verified bytes rather than an assumed CP932 encoding. Raw ZIP bytes '
        'remain unchanged.\n\n'
        '## Reproduce locally\n\n'
        'Run each line sequentially from the repository root, using the existing local Python environment.\n\n'
        '```sh\n'
        'python3 src/preprocessing/inspect_ksj_eighteen_sources.py --stage extract\n'
        'python3 src/preprocessing/inspect_ksj_eighteen_sources.py --stage summarize\n'
        'python3 src/preprocessing/audit_ksj_eighteen_geometry.py\n'
        'python3 src/preprocessing/construct_ksj_eighteen_mesh.py --stage prepare\n'
        'python3 src/preprocessing/construct_ksj_eighteen_mesh.py --stage geometry\n'
        'python3 src/preprocessing/construct_ksj_eighteen_mesh.py --stage tables\n'
        'python3 .codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py --root . --decisions data/exp/data-preprocessing/ksj-eighteen-facilities/decisions.json --pretty\n'
        'python3 src/preprocessing/run_ksj_eighteen_readable_scripts.py\n'
        'python3 src/preprocessing/link_ksj_eighteen_panel.py\n'
        'python3 src/preprocessing/validate_ksj_eighteen_construction.py\n'
        'python3 src/preprocessing/finalize_ksj_eighteen_delivery.py\n'
        '```\n\n'
        'GDAL extraction/geoprocessing and pandas/Arrow table writing use separate processes to avoid a local '
        'binary-runtime conflict. No new dependency or host-only table API is required. AnaSOP changes are '
        'restricted to Section 4; candidate model roles remain TBD.\n')
    (OUT / 'CONSTRUCTION_REPORT.md').write_text(report)
    readme = (OUT / 'README.md').read_text()
    if '\n## Scope and status\n' in readme:
        readme = readme.split('\n## Scope and status\n')[0]
    readme += ('\n## Scope and status\n\nFull source discovery and approved construction are complete under '
               f"{decisions['decision_id']}. The field inventory above remains a complete disclosure of original "
               'attributes. Eighteen analytical counts and provenance/quality references are now linked to both '
               'five-period panels; no model has been refitted. See [CONSTRUCTION_REPORT.md](CONSTRUCTION_REPORT.md), '
               'mesh_construction_summary.csv and construction_validation.json.\n')
    (OUT / 'README.md').write_text(readme)
    proposal = (OUT / 'CONSTRUCTION_PROPOSAL.md').read_text()
    proposal = re.sub(r'^Status:.*$', f"Status: approved under {decisions['decision_id']} and executed; "
                     'see CONSTRUCTION_REPORT.md and construction_validation.json. The proposal below is retained '
                     'as the approved construction contract.', proposal, count=1, flags=re.M)
    (OUT / 'CONSTRUCTION_PROPOSAL.md').write_text(proposal)
    acqreadme = (ACQ / 'README.md').read_text()
    acqreadme = re.sub(r'^Current next step:.*$', 'Current construction status: eighteen approved mesh counts '
                      'and both five-period panels are complete and validated. See '
                      '[CONSTRUCTION_REPORT.md](../../data-preprocessing/ksj-eighteen-facilities/CONSTRUCTION_REPORT.md). '
                      'No regression term has been selected or refitted.', acqreadme, flags=re.M)
    (ACQ / 'README.md').write_text(acqreadme)
    delivery = dict(status='passed', decision_id=decisions['decision_id'], selected_categories=18,
        new_mesh_variables_written=True, five_period_panel_updated=True, analytical_columns_added=18,
        references_added=95, mesh_rows=972800, mesh_columns=114,
        raw_archives_unchanged=True, source_record_accounting_verified=True,
        all_previous_panel_values_preserved_exactly=True, no_sample_or_island_exclusion=True,
        anasop_section_4_updated=True, anasop_other_sections_unchanged=True,
        added_anasop_text_english_ascii=True, added_anasop_uses_readable_names_only=True,
        anasop_sha256=sha(ROOT / 'docs/AnaSOP.md'), regressions_refitted=False,
        outputs=link['outputs'])
    (OUT / 'delivery_validation.json').write_text(json.dumps(delivery, indent=2) + '\n')
    print('Delivery passed; AnaSOP Section 4 updated, all other sections preserved.', flush=True)


if __name__ == '__main__':
    main()
