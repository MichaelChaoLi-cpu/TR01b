"""Audit prefecture land overlap for the latest core-complete candidate grid.

This prepares candidate geometry only; no sample selection or nearest-land rule.
Arrow extraction and GDAL geometry run as separate processes/stages.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/expanded-analysis-geography'


def extract():
    import pandas as pd
    pointer = json.loads((ROOT / 'data/exp/data-preprocessing/active_panel.json').read_text())
    source = ROOT / pointer['core_balanced_panel']
    frame = pd.read_parquet(source, columns=['Mesh Code', 'Road Year'])
    assert not frame.duplicated().any()
    codes = frame['Mesh Code'].astype(str).drop_duplicates().sort_values()
    assert frame.groupby('Mesh Code')['Road Year'].nunique().eq(5).all()
    OUT.mkdir(parents=True, exist_ok=True)
    codes.to_frame().to_csv(OUT / 'candidate_meshes.csv', index=False)
    with source.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    (OUT / 'candidate_contract.json').write_text(json.dumps(dict(
        purpose='Geometry audit of all current core-complete candidates; no sample selection',
        source=pointer['core_balanced_panel'], source_sha256=checksum,
        meshes=len(codes), observations=len(frame), periods=[2002, 2003, 2004, 2010, 2024],
        administrative_reference_year=2024, automatic_nearest_land_assignment=False,
        data_decision_id=pointer['decision_id']), indent=2) + '\n')
    print('Extracted candidate keys:', len(codes), flush=True)


def geometry():
    from construct_regional_mesh_assignment import main
    contract = json.loads((OUT / 'candidate_contract.json').read_text())
    main(output_dir=OUT / 'prefecture-overlap',
         grouping={f'{i:02d}': [i] for i in range(1, 48)},
         decision_id='Execution requested; analysis cohort decision pending',
         expected_meshes=contract['meshes'], sample_path=OUT / 'candidate_meshes.csv',
         manifest_path=ROOT / 'data/exp/data-preprocessing/regional/reference/manifest.json',
         unit='prefecture', grouping_source='https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html',
         compact_console=True)


def audit():
    import pandas as pd
    frame = pd.read_csv(OUT / 'prefecture-overlap/mesh_prefecture_confirmed_input.csv',
                        dtype={'mesh_code': str, 'prefecture_code': str})
    previous = pd.read_parquet(ROOT / 'data/processed/national/five_period/mesh_prefecture_national_preprocessed.parquet')
    previous['Mesh Code'] = previous['Mesh Code'].astype(str)
    joined = previous.merge(frame, left_on='Mesh Code', right_on='mesh_code',
                            how='left', validate='one_to_one')
    assigned = ~joined['No Land Overlap']
    assert joined.loc[assigned, 'Prefecture Code'].astype(str).str.zfill(2).equals(
        joined.loc[assigned, 'prefecture_code'].str.zfill(2))
    exceptions = joined.loc[joined['No Land Overlap']]
    assert len(exceptions) == 19 and exceptions['total_land_overlap'].eq(0).all()
    contract = json.loads((OUT / 'candidate_contract.json').read_text())
    assert len(frame) == contract['meshes'] and frame.mesh_code.is_unique
    with (ROOT / contract['source']).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == contract['source_sha256']
    report = dict(candidate_meshes=len(frame), assignment_status_counts=frame.assignment_status.value_counts().to_dict(),
                  previous_assigned_prefectures_unchanged=True, reviewed_exceptions=len(exceptions),
                  potential_common_meshes=int(frame.prefecture_code.notna().sum()+len(exceptions)),
                  sample_selected=False, models_fitted=False)
    (OUT / 'geography_audit_summary.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'README.md').write_text(
        '# Expanded analysis geography: candidate audit\n\n'
        f"Audit {len(frame):,} meshes from the latest core-balanced panel. "
        f"Positive prefectural administrative-area overlap occurs in {frame.prefecture_code.notna().sum():,} meshes. "
        f"The previously approved {len(exceptions)} zero-overlap assignment exceptions are separately verified. "
        f"A potential shared administrative cohort therefore contains {report['potential_common_meshes']:,} meshes. "
        'No analytical sample is selected, and no regression or nearest-land fallback is executed. '
        'These are frozen 2024 administrative polygon overlaps, rather than a newly measured annual coastline. '
        'The previous ordinary prefecture assignments remain identical. All source archives and candidate keys '
        'are checksum-verified. Original processed data and AnaSOP are unchanged.\n\n'
        'Reproduce each stage in a separate process:\n\n```sh\n'
        'python3 src/preprocessing/prepare_expanded_analysis_geography.py --stage extract\n'
        'python3 src/preprocessing/prepare_expanded_analysis_geography.py --stage geometry\n'
        'python3 src/preprocessing/prepare_expanded_analysis_geography.py --stage audit\n```\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['extract', 'geometry', 'audit'], required=True)
    {'extract': extract, 'geometry': geometry, 'audit': audit}[parser.parse_args().stage]()
