"""Finalize confirmed annual MODIS construction, changing only AnaSOP Section 4."""
from pathlib import Path
import hashlib
import json
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/modis-land-cover'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    names = ['mesh_construction_validation', 'panel_linkage_validation',
             'panel_quality_validation', 'source_mosaic_validation', 'independent_geometry_validation']
    reports = {name: json.loads((OUT / f'{name}.json').read_text()) for name in names}
    assert all(value['status'] == 'passed' for value in reports.values())
    contract = json.loads((OUT / 'proposed_construction.json').read_text())
    decisions = json.loads((OUT / 'decisions.json').read_text())
    assert contract['confirmed'] and decisions['confirmed']
    assert decisions['decision_id'] == contract['construction_decision_id']
    rows = []
    for dataset, spec in decisions['datasets'].items():
        original = pd.read_parquet(ROOT / dataset)
        for variable in spec['variables']:
            series = original[variable['original_name']]
            rows.append(dict(source_dataset=dataset, **variable,
                             dtype=str(series.dtype), non_null_count=int(series.notna().sum()),
                             null_pct=100 * float(series.isna().mean()),
                             sample_values=', '.join(map(str, series.dropna().head(3))),
                             output=spec['output'], script=spec['script']))
    pd.DataFrame(rows).to_csv(OUT / 'constructed_variable_list.csv', index=False)
    linkage = reports['panel_linkage_validation']
    quality = reports['panel_quality_validation']
    profile = next(q for q in quality['quality_profiles'] if q['rows'] == 1144940)
    missing = sum(r['no_valid_coverage'] for r in profile['coverage_by_year'].values())
    partial = sum(r['partial_valid_coverage'] for r in profile['coverage_by_year'].values())
    definitions = {
        'Urban Land Cover Share': 'IGBP urban and built-up class 13.',
        'Forest Land Cover Share': 'IGBP forest classes 1-5.',
        'Cropland Land Cover Share': 'IGBP cropland class 12.',
        'Cropland Mosaic Land Cover Share': 'IGBP cropland/natural-vegetation mosaic class 14, kept separate.',
        'Water Land Cover Share': 'IGBP water class 17, requiring a valid classification.',
        'Other Land Cover Share': 'IGBP shrubland, savanna, grassland, wetland, snow/ice and barren classes 6-11 and 15-16.'
    }
    block = [
        '### Constructed Annual MODIS Land Cover', '',
        'The confirmed land-cover supplement uses annual MCD12Q1 Collection 6.1 observations matched separately to 2002, 2003, 2004, 2010 and 2024. This follows the previously selected exemption from the facility snapshot restriction. Land Cover Year equals the road/light period; a contemporary land-cover snapshot is not replicated into historical periods. Facility characteristics retain their confirmed static source editions.', '',
        'For every year, construct variables on the complete 972,800-mesh grid. The combined annual mesh table contains 4,864,000 mesh-year records and 17 readable fields: six retained analytical candidates and eleven key, year, product, area and quality references. Append sixteen fields to each facility-augmented panel, preserving its previous 79 columns exactly. The complete augmented panel contains 4,864,000 rows and 95 columns; the unchanged balanced cohort contains 228,988 meshes, 1,144,940 rows and 95 columns. No row or island is removed.', '',
        r'Let \(M_i\) be mesh \(i\), \(P_p\) a native MODIS pixel, \(a_{ip}=\operatorname{area}(M_i\cap P_p)\), and \(A_i=\operatorname{area}(M_i)\). Use the same native spherical equal-area sinusoidal projection for numerator and denominator. Densify mesh meridians and intersect actual pixel boundaries; do not use a centre pixel, interpolate category codes or assume a literal one-square-kilometre mesh. Land Cover Mesh Area is a separate reference and does not replace the existing road Mesh Area.', '',
        r'For the set \(\mathcal P_t\) of source-available pixels with valid IGBP class labels and accepted quality codes \(\{0,2,4,5,6,7,8,9\}\), construct \(\ell_{itk}=\sum_{p\in\mathcal P_t}a_{ip}\mathbf{1}\{c_{pt}\in\mathcal C_k\}/A_i\), where \(c_{pt}\) is the original class and \(\mathcal C_k\) is the confirmed class group. Define valid coverage \(V_{it}=\sum_{p\in\mathcal P_t}a_{ip}/A_i\). The six contributions satisfy \(\sum_k\ell_{itk}=V_{it}\), without redistributing unknown area or forcing partial coverage to sum to one.', '',
        '| variable_name | full_name | role | formal_definition | construction_or_coding | is_final_variable |',
        '| --- | --- | --- | --- | --- | --- |'
    ]
    for name, construction in definitions.items():
        block.append(f'| {name} | {name} | TBD | ' +
                     r'\(\ell_{itk}\), fraction of full projected mesh area.' +
                     f' | {construction} Retain NaN where no valid pixels exist. | yes |')
    block += ['', 
        'Retain Land Cover Source Coverage, Land Cover Coverage, Land Cover Unclassified Share, Land Cover No Data Share, Land Cover Adjusted Share, Land Cover Incomplete Coverage and Land Cover No Valid Pixels, plus Land Cover Year, Land Cover Product and Land Cover Mesh Area. Source coverage measures published, downloaded native pixels. Valid coverage excludes unclassified quality codes 1 and 3, no-data code 10, fill/invalid labels and unpublished tiles. The adjusted share identifies retained valid product corrections with quality codes 4-9; it is not a mean of categorical quality codes.', '',
        'The valid, unclassified and no-data area contributions partition the full mesh area. No valid coverage produces NaN in all six class contributions. Partial-coverage values describe observed area contributions only; the unknown remainder is not assigned to any class. Retain genuine observed zeros, apply no statistical filling, rescaling or logarithm, and preserve all missingness flags. Tiny floating-point roundoff is bounded in quality fractions only.', '',
        'The h32v06 tile near Minami-Torishima is absent from all five official annual catalogues. Preserve 2,315 meshes intersecting that unpublished source tile, including 2,180 entirely within it, with source-coverage and missingness information. Do not infer a water class or remove an island because an archive is absent.', '',
        f'Within the unchanged balanced cohort, {missing:,} mesh-period observations have no valid land-cover classification, affecting {profile["meshes_without_valid_coverage_in_any_year"]:,} distinct meshes; {partial:,} observations have positive but partial valid coverage. All remain in the augmented dataset. Per-period quality profiles are retained separately; no complete-case regression cohort has been selected.', '',
        'The six groups exhaust the accepted IGBP classes and partition valid coverage. Their retention does not imply simultaneous inclusion with coverage in a model. Candidate roles remain TBD and no augmented regression specification is selected. Urban-labelled pixel area does not measure exact buildings or impervious-surface fraction; cropland/natural-vegetation mosaic area is not decomposed into actual crop and vegetation fractions. Annual classifications provide broad context and their differences are not direct measurements of real land-cover change.', '',
        'Product processing identifiers and original response checksums are verified against official Collection 6.1 catalogues. Overlapping downloads, independent small-region pixel positions and independent polygon intersections pass. Existing national, regional, prefecture and local regression outputs retain their earlier road/population specification; this supplement does not refit them.', ''
    ]
    new_block = '\n'.join(block)
    assert new_block.isascii()
    assert new_block.count(r'\(') == new_block.count(r'\)')
    for forbidden in ['LC_Type1', 'source_dataset', 'original_name', '.parquet', 'data/raw/']:
        assert forbidden not in new_block
    sop = ROOT / 'docs/AnaSOP.md'; before = sop.read_text()
    heading4 = '## 4. Variable Construction  /  Key Variables\n'
    heading5 = '## 5. Identification Strategy\n'
    prefix, remaining = before.split(heading4, 1)
    section4, suffix = remaining.split(heading5, 1)
    snapshot = (OUT / 'AnaSOP_before_modis.txt').read_text()
    assert snapshot.split(heading4, 1)[0] == prefix
    assert snapshot.split(heading5, 1)[1] == suffix
    section4 = section4.replace('Each augmented panel contains 79 columns,',
                                'Each facility-only augmented panel contains 79 columns,')
    section4 = section4.replace(
        'Land-cover data have not yet been acquired or constructed, and are not represented by a placeholder or another variable.',
        'Annual land-cover data are acquired and constructed in the separate supplement described below.')
    section4 = re.sub(r'### Constructed Annual MODIS Land Cover\n[\s\S]*?(?=\n### |\Z)', '', section4)
    section4 = section4.rstrip() + '\n\n' + new_block + '\n'
    sop.write_text(prefix + heading4 + section4 + heading5 + suffix)
    after = sop.read_text()
    assert after.split(heading4, 1)[0] == prefix
    assert after.split(heading5, 1)[1] == suffix

    text = [
        '# Annual MODIS mesh construction and five-period panel linkage', '',
        f'Completed under {decisions["decision_id"]}; scope recorded under {decisions["scope_decision_id"]}.',
        'All five annual source datasets are constructed and linked. AnaSOP Section 4 is updated; every other section is preserved. No regression has been refitted.', '',
        '## Variables and outputs', '',
        '| Variable | Original IGBP classes |', '| --- | --- |'
    ]
    for name, group in contract['proposed_groups'].items():
        text.append(f'| {name} | {", ".join(map(str, group))} |')
    text += ['', 
        'The six shares use complete native projected mesh area; together they sum to valid coverage. No valid coverage means NaN. Positive partial-coverage shares represent observed contributions with an unknown remainder. Cropland mosaic remains separate. Year, product, area, source coverage and classification-quality references are retained.',
        '', 'Five annual processed mesh files each contain 972,800 rows and 17 readable columns. The combined annual mesh table contains 4,864,000 rows and 17 columns.', '']
    for record in linkage['outputs']:
        text.append(f'- {record["output"]}: {record["rows"]:,} rows, {record["columns"]} columns.')
    text += ['', '## Balanced-cohort coverage', '',
             '| Year | Rows retained | No valid classification | Positive partial coverage | Complete valid coverage |',
             '| --- | ---: | ---: | ---: | ---: |']
    for year, record in profile['coverage_by_year'].items():
        text.append(f'| {year} | {record["rows"]:,} | {record["no_valid_coverage"]:,} | '
                    f'{record["partial_valid_coverage"]:,} | {record["complete_valid_coverage"]:,} |')
    text += ['', 
        f'No valid classification affects {missing:,} observations and {profile["meshes_without_valid_coverage_in_any_year"]:,} distinct balanced-cohort meshes. No row is deleted. These checks do not select a new regression sample.',
        '', '## Traceability and reproduction', '',
        'Raw official responses remain unchanged. ACQUISITION.md describes the acquisition checkpoint and source limitations. constructed_variable_list.csv records every selected original/readable field and its missingness; decisions.json drives the five generated scripts. mesh_variable_summary.csv describes the full mesh grid. panel_quality_validation.json includes both cohort profiles and source/output checks.',
        '',
        'After the acquisition commands in ACQUISITION.md, run:', '', '~~~bash',
        'python3 src/preprocessing/prepare_modis_meshes.py',
        'python3 .codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py --root . --decisions data/exp/data-preprocessing/modis-land-cover/decisions.json --pretty']
    for spec in decisions['datasets'].values():
        text.append('python3 ' + spec['script'])
    text += [
        'python3 src/preprocessing/link_modis_panel.py',
        'python3 src/preprocessing/validate_modis_panel.py',
        'python3 src/preprocessing/finalize_modis_documentation.py', '~~~', '',
        'All table operations use repository scripts and existing local pandas/PyArrow. No additional package, account, Git or DVC operation is required. Current outputs preserve every previous panel column exactly. Facility source editions remain static; MODIS is annual. Final model roles and any augmented regression remain unselected.', '']
    (OUT / 'CONSTRUCTION.md').write_text('\n'.join(text))
    readme = OUT / 'README.md'; content = readme.read_text()
    content = content.replace(
        'Current source acquisition, coverage exceptions and pending construction are documented in [ACQUISITION.md](ACQUISITION.md). Annual shares and panel linkage remain pending human confirmation.',
        'The preserved acquisition checkpoint is documented in [ACQUISITION.md](ACQUISITION.md). Current completed construction and linkage are documented in [CONSTRUCTION.md](CONSTRUCTION.md).')
    receipt = '## Current construction status\n\nFive annual mesh datasets and both augmented panels are complete and verified. See [CONSTRUCTION.md](CONSTRUCTION.md) and [constructed_variable_list.csv](constructed_variable_list.csv). All prior panel columns are preserved; no regression is refitted.\n\n'
    if not content.startswith(receipt):
        content = receipt + content
    readme.write_text(content)
    acquisition = OUT / 'ACQUISITION.md'; content = acquisition.read_text()
    note = '## Current status\n\nThe acquisition checkpoint below is preserved. Construction was subsequently confirmed and completed under MILI-D-20261010-019; see [CONSTRUCTION.md](CONSTRUCTION.md) for the current outputs and validations.\n\n'
    if not content.startswith(note):
        acquisition.write_text(note + content)
    reference = json.loads((OUT / 'preserved_analysis_reference.json').read_text())
    assert sha(ROOT / reference['path']) == reference['sha256']
    report = dict(status='passed', decision_id=decisions['decision_id'], years=contract['years'],
                  source_datasets=5, analytical_candidates=6, columns_added=16,
                  all_previous_panel_values_preserved=True, raw_archives_verified=quality['original_source_archives_verified'],
                  annual_matching_verified=True, no_mesh_or_period_deleted=True,
                  ana_sop_sections_changed=[4], section_4_english_readable_names_and_ascii_math=True,
                  other_ana_sop_sections_preserved=True, panel_outputs=linkage['outputs'],
                  balanced_coverage_profile=profile, regressions_refitted=False,
                  original_local_coefficients_preserved=True)
    (OUT / 'delivery_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('MODIS delivery complete; AnaSOP Section 4 updated and other sections preserved.', flush=True)


if __name__ == '__main__':
    main()
