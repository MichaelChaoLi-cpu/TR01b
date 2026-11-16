#!/usr/bin/env python3
"""Municipal Mismatch, Traffic and Fiscal Correlations.

Plan: eight scopes and nine columns, descriptive Spearman and available pair counts.
Framework: AnaSOP Sections 5-7, supporting point 3; UMD context fractions versus
whole-government traffic and fiscal outcomes, without new regressions or tests.
Run locally: uv run python src/analyses/table_municipal_mismatch_traffic_and_fiscal_correlations.py
"""
from pathlib import Path
import hashlib
import json
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font,Alignment,Border,Side
from openpyxl.utils import get_column_letter

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/exp/umd-municipal-context'
OUT=ROOT/'data/results/tables/Table_municipal_mismatch_traffic_and_fiscal_correlations.xlsx'
AUDIT=ROOT/'data/exp/figure-table-generation/municipal-mismatch-traffic-and-fiscal-correlations'
X='Candidate Fraction of Supported Meshes'
OUTCOMES=['Length Weighted 24h Volume','Maintenance Share of Expenditure',
          'Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio']
CONTEXTS=['Forest','Shrublands and Grasslands','Urban','Cropland','Water','Barren','Incomplete coverage']
SCOPES=['All municipal governments',*['Land context: '+c for c in CONTEXTS]]

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    paths=[SOURCE/n for n in ['municipal_evidence_2024.parquet','municipal_land_context_summary.parquet',
           'municipal_context_rank_correlations.csv','validation.json']]
    before={str(p.relative_to(ROOT)):sha(p) for p in paths}
    validation=json.loads(paths[-1].read_text())
    assert validation['status']=='passed' and validation['classification']=='UMD'
    assert validation['output_sha256']==sha(paths[0]) and validation['correlation_sha256']==sha(paths[2])
    assert validation['geographic_assignments_unchanged'] and validation['fiscal_and_traffic_values_unchanged']
    for path,digest in validation['source_hashes'].items():assert sha(ROOT/path)==digest
    municipal=pd.read_parquet(paths[0]);land=pd.read_parquet(paths[1]);corr=pd.read_csv(paths[2],float_precision='round_trip')
    assert len(municipal)==1741 and municipal['Government Code'].is_unique
    assert not land.duplicated(['Government Code','Land Context']).any()
    assert set(land['Land Context'])==set(CONTEXTS)
    assert len(corr)==32 and not corr.duplicated(['Scope','Outcome']).any()
    assert set(corr['Scope'])==set(SCOPES) and corr['Predictor'].eq(X).all()
    assert municipal['Fiscal Year'].eq(2023).all() and municipal['Traffic Year'].eq(2021).all()
    assert municipal['Road Year'].eq(2024).all() and municipal['Population Year'].eq(2020).all()
    assert municipal[X].notna().all() and municipal[OUTCOMES[0]].isna().sum()==7
    assert municipal[OUTCOMES[1:]].notna().all().all()
    assert land['Cohort Meshes'].sum()==validation['linked_meshes']
    assert land['Candidate Meshes'].sum()==municipal['Candidate Meshes'].sum()==validation['linked_candidates']
    assert land['Supported Meshes'].sum()==municipal['Supported Meshes'].sum()
    for d in [municipal,land]:
        n=d['Supported Meshes'].to_numpy();k=d['Candidate Meshes'].to_numpy()
        expected=np.divide(k,n,out=np.full(len(n),np.nan),where=n>0)
        np.testing.assert_allclose(d[X],expected,rtol=1e-12,atol=1e-14,equal_nan=True)
        assert d[X].dropna().between(0,1).all()
    rows=[];checks=[];pair_exports=[]
    for scope in SCOPES:
        if scope==SCOPES[0]:d=municipal
        else:
            d=land.loc[land['Land Context'].eq(scope.removeprefix('Land context: '))].merge(
                municipal[['Government Code',*OUTCOMES]],on='Government Code',validate='one_to_one')
        row=['Overall' if scope==SCOPES[0] else scope.removeprefix('Land context: ')]
        for outcome in OUTCOMES:
            stat=corr.loc[corr['Scope'].eq(scope)&corr['Outcome'].eq(outcome)]
            assert len(stat)==1;stat=stat.iloc[0]
            pairs=d[['Government Code',X,outcome]].replace([np.inf,-np.inf],np.nan).dropna(subset=[X,outcome])
            n=len(pairs);assert n==stat['Municipalities']
            if n>1:
                x,y=[pairs[c].rank(method='average').to_numpy() for c in [X,outcome]]
                x=x-x.mean();y=y-y.mean();den=np.sqrt((x@x)*(y@y))
                rho=float((x@y)/den) if den>0 else np.nan
            else:rho=np.nan
            np.testing.assert_allclose(rho,stat['Spearman'],atol=1e-12,rtol=1e-12,equal_nan=True)
            if n==0:assert np.isnan(rho)
            row.extend([float(stat['Spearman']),n])
            checks.append({'scope':scope,'outcome':outcome,'paired_governments':n,
                           'spearman':rho if np.isfinite(rho) else None,'independent_rank_check':'passed'})
            pair_exports.append(pairs.rename(columns={outcome:'Outcome Value'}).assign(Scope=scope,Outcome=outcome))
        rows.append(row)
    columns=['Scope']
    for outcome in OUTCOMES:columns.extend([outcome+' — Spearman',outcome+' — N'])
    table=pd.DataFrame(rows,columns=columns);assert table.shape==(8,9)
    notes=pd.DataFrame([
        ('Definition','Each coefficient is the descriptive Spearman rank correlation of Candidate Fraction of Supported Meshes with the specified whole-government outcome. Average-tie ranks and pairwise available data are used; N is the number of paired governments.'),
        ('Scopes','Overall and seven retained UMD contexts. Context-specific fractions divide candidate meshes by supported meshes in that context within each government. Outcomes remain whole-government measures, not context-specific traffic or spending.'),
        ('Traffic','Length Weighted 24h Volume: surveyed segment-length-weighted vehicles per 24 hours, primarily major roads within government territory. Seven outcomes remain missing; no zero filling. Territorial traffic differs from own-government maintenance accounts.'),
        ('Maintenance / expenditure','Own-government road-plus-bridge maintenance expenditure divided by total expenditure, using actual fiscal year 2023.'),
        ('Maintenance / fiscal scale','Own-government road-plus-bridge maintenance expenditure divided by standard fiscal scale, using actual fiscal year 2023.'),
        ('Revenue / need','Single-year standard fiscal revenue divided by standard fiscal need, using actual fiscal year 2023.'),
        ('Years','Road/light and UMD land context 2024, matched Population 2020, surveyed traffic 2021 and fiscal year 2023. This is a linked cross-section, not five-period replicated municipal data.'),
        ('Missing and small samples','Barren has no supported context fractions: all four correlations are unavailable, N=0. Incomplete coverage has only ten traffic pairs and thirteen pairs for each fiscal outcome; its correlations are descriptive small-sample summaries.'),
        ('Geography','The verified 1,741 government units consolidate designated-city wards to their financial parent. The fixed mesh ledger retains 320 unlinked meshes, including 38 candidates, without reassignment; 66,059 of 66,097 national candidates link to a government.'),
        ('Inference','No significance stars or p values are added to this descriptive rank-correlation table. The Pearson p values in the separately accepted scatter figure concern a different statistic. No spatial or multiple-comparison adjustment or causal test is selected here.'),
        ('Interpretation','Realized maintenance spending differs from required or deferred maintenance. Territorial traffic and own-government spending are not ownership-matched. Associations do not identify excessive-road costs or a causal fiscal effect.'),
        ('Display','The comparison displays three decimal places and integer pair counts; an em dash marks unavailable correlations in the image and corresponding workbook cells remain empty. Full numerical values are retained in Correlation details and the audit export.'),
    ],columns=['Topic','Note'])
    OUT.parent.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(OUT,engine='openpyxl') as writer:
        table.to_excel(writer,sheet_name='Municipal correlations',index=False)
        corr.to_excel(writer,sheet_name='Correlation details',index=False)
        notes.to_excel(writer,sheet_name='Notes',index=False)
        for ws in writer.book:
            ws.sheet_view.showGridLines=False;ws.freeze_panes='B2'
            for row in ws:
                for c in row:
                    c.font=Font(name='Times New Roman',size=11,bold=c.row==1)
                    c.alignment=Alignment(wrap_text=True,vertical='center',horizontal='left' if c.column==1 else 'center')
            ws.row_dimensions[1].height=64
            for i in range(1,ws.max_column+1):ws.column_dimensions[get_column_letter(i)].width=25
        ws=writer.book['Municipal correlations'];ws.column_dimensions['A'].width=33
        for col in range(2,10):ws.column_dimensions[get_column_letter(col)].width=28 if col%2==0 else 11
        for row in ws.iter_rows(min_row=2):
            ws.row_dimensions[row[0].row].height=38
            for c in row[1:]:c.number_format='0.000' if c.column%2==0 else '#,##0'
        line=Side(style='thin',color='000000')
        for c in ws[1]:c.border=Border(top=line,bottom=line)
        for c in ws[9]:c.border=Border(bottom=line)
        ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1;ws.print_area=ws.dimensions
        ws=writer.book['Correlation details']
        for row in ws.iter_rows(min_row=2):row[4].number_format='0.000000000000'
        ws=writer.book['Notes'];ws.column_dimensions['A'].width=30;ws.column_dimensions['B'].width=135
        for i in range(2,len(notes)+2):ws.row_dimensions[i].height=60
    pd.testing.assert_frame_equal(table,pd.read_excel(OUT,sheet_name='Municipal correlations'),check_dtype=False,rtol=1e-12)
    pd.testing.assert_frame_equal(corr,pd.read_excel(OUT,sheet_name='Correlation details'),check_dtype=False,rtol=1e-12)
    pd.testing.assert_frame_equal(notes,pd.read_excel(OUT,sheet_name='Notes'))
    wb=load_workbook(OUT);assert wb['Municipal correlations'].max_row==9 and wb['Municipal correlations'].max_column==9
    assert not any(c.data_type=='f' for ws in wb for row in ws for c in row)
    table.to_csv(AUDIT/'table_values.csv',index=False)
    corr.to_parquet(AUDIT/'unrounded_correlations.parquet',index=False)
    pd.concat(pair_exports,ignore_index=True).to_parquet(AUDIT/'available_pairs.parquet',index=False)
    caption=('Municipal Mismatch, Traffic and Fiscal Correlations. Descriptive Spearman correlations and actual pairwise available government counts for overall and seven UMD land contexts. The predictor is the fraction of supported meshes flagged as potential mismatch candidates; context-specific fractions are paired with whole-government outcomes. Traffic is surveyed segment-length-weighted 24-hour volume. Maintenance denominators are total expenditure and standard fiscal scale. Fiscal revenue/need is the single-year standard fiscal-resource ratio. Barren correlations are unavailable (N=0); Incomplete coverage has only 10 traffic and 13 fiscal pairs. Years: road/light and land context 2024, Population 2020, traffic 2021 and fiscal year 2023. Correlations use average-tie ranks without new significance tests, spatial adjustment or causal interpretation. Three decimals are shown and full numerical values are retained separately. Traffic territory and fiscal ownership differ; maintenance spending does not measure costs attributable to flagged roads.\n')
    OUT.with_suffix('.caption.md').write_text(caption)
    plt.rcParams.update({'font.family':'DejaVu Serif'})
    display=[]
    for r in rows:
        name=r[0].replace('Shrublands and Grasslands','Shrublands and\nGrasslands').replace('Incomplete coverage','Incomplete\ncoverage')
        display.append([name,*[('—' if pd.isna(v) else f'{v:.3f}') if i%2==0 else f'{v:,}' for i,v in enumerate(r[1:])]])
    fig,ax=plt.subplots(figsize=(16,6.5));ax.axis('off')
    drawing=ax.table(cellText=display,colLabels=['Scope',*['ρ','N']*4],cellLoc='center',
                     colWidths=[.24,*[.095]*8],bbox=[0,.24,1,.64])
    drawing.auto_set_font_size(False);drawing.set_fontsize(11)
    for (r,c),cell in drawing.get_celld().items():
        cell.set_facecolor('white');cell.set_edgecolor('black');cell.set_linewidth(.7)
        cell.visible_edges='TB' if r==0 else 'B' if r==8 else ''
        if r==0:cell.get_text().set_weight('bold')
        if c==0:cell.get_text().set_ha('left')
    for i,label in enumerate(['Surveyed traffic','Maintenance /\nexpenditure','Maintenance /\nfiscal scale','Fiscal revenue /\nneed']):
        ax.text(.335+.19*i,.94,label,ha='center',va='center',transform=ax.transAxes,fontsize=11,fontweight='bold')
    ax.plot([0,1],[.995,.995],color='black',lw=.7,transform=ax.transAxes)
    footnotes=['ρ: descriptive Spearman correlation; N: available paired governments. Predictor: potential mismatch fraction.',
               'Context-specific fractions are paired with whole-government outcomes. Traffic 2021; fiscal year 2023; screen 2024.',
               '— unavailable. Barren: no supported pairs. Incomplete coverage: only 10–13 pairs.']
    for j,note in enumerate(footnotes):ax.text(0,.17-.06*j,note,transform=ax.transAxes,fontsize=10)
    fig.subplots_adjust(left=.02,right=.98,top=.98,bottom=.03)
    fig.savefig(AUDIT/'preview.png',dpi=120,facecolor='white')
    fig.savefig(OUT.with_suffix('.png'),dpi=600,facecolor='white');plt.close(fig)
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in paths}
    report={'title':'Municipal Mismatch, Traffic and Fiscal Correlations','status':'generated_pending_visual_and_human_review',
            'human_review':'pending','rows':8,'columns':9,'classification':'UMD','source_hashes':before,
            'source_files_unchanged':True,'available_pair_checks':checks,'all_three_sheets_readback_verified':True,
            'no_new_regressions_or_significance_tests':True,'workbook_sha256':sha(OUT),'script_sha256':sha(Path(__file__))}
    (AUDIT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved: {OUT.relative_to(ROOT)}')
    print('Verified: all 32 scope/outcome correlations and pair counts, eight rows and nine columns.')

if __name__=='__main__':main()
