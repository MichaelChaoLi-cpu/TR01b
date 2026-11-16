#!/usr/bin/env python3
"""Prefecture Road Association Comparison.

AnaSOP Sections 5-7: forty-seven separate original-scale pooled OLS comparisons,
identical baseline/extended prefecture samples, mesh-clustered CR1 and normal
95% intervals. Render validated UMD road estimates without refitting models.
Run: uv run python src/analyses/table_prefecture_road_association_comparison.py
"""
from pathlib import Path
import hashlib
import json
import os

os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy.stats import norm
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, Border, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/umd-four-layer'
OUT = ROOT / 'data/results/tables/Table_prefecture_road_association_comparison.xlsx'
AUDIT = ROOT / 'data/exp/figure-table-generation/prefecture-road-association-comparison'
Z95 = 1.959963984540054

def stars(p_value):
    return '***' if p_value < .01 else '**' if p_value < .05 else '*' if p_value < .10 else ''

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    paths = [SOURCE / name for name in ['prefecture_coefficients.csv','prefecture_validation.json',
             'pooled_validation.json','delivery_validation.json','execution_contract.json','inputs/model_panel.parquet']]
    before = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    coeff = pd.read_csv(paths[0], float_precision='round_trip')
    validation, pooled, delivery, contract = [json.loads(p.read_text()) for p in paths[1:5]]
    assert all(v['status']=='passed' for v in [validation,pooled,delivery])
    assert contract['confirmed'] and contract['classification']=='UMD'
    assert pooled['input_sha256']==contract['panel_sha256']==sha(paths[-1])
    assert pooled['same_sample_verified'] and contract['effects']==[]
    assert delivery['land_cover_reference']==contract['land_cover_reference']=='Water Land Cover Share'
    assert contract['periods']==[2002,2003,2004,2010,2024]
    panel = pd.read_parquet(paths[-1],columns=['Mesh Code','Road Year','Prefecture'])
    assert len(panel)==1916930 and panel['Mesh Code'].nunique()==383386
    assert not panel.duplicated(['Mesh Code','Road Year']).any()
    assert panel.groupby('Mesh Code').size().eq(5).all()
    assert panel.groupby('Mesh Code')['Prefecture'].nunique().eq(1).all()
    counts=panel.groupby('Prefecture').agg(meshes=('Mesh Code','nunique'),observations=('Mesh Code','size'))
    fits={r['group']:r for r in validation['results']}
    groups=sorted(fits)
    assert len(groups)==47 and [int(g.split(' / ')[0]) for g in groups]==list(range(1,48))
    PREFECTURES=[g.split(' / ')[1] for g in groups]
    assert set(panel['Prefecture'])==set(PREFECTURES)
    road=coeff.loc[coeff['variable'].eq('Road Length Density')].copy()
    assert len(road)==94 and not road.duplicated(['Group','Specification']).any()
    rows,checks=[],[]
    for group,prefecture in zip(groups,PREFECTURES):
        records=[]
        outcome_tss=[]
        for key,spec in [('baseline_same_sample','Baseline'),('extended','Extended')]:
            fit=fits[group][key]
            g,n,k=[fit[q] for q in ['meshes','observations','parameters']]
            assert fit['status']=='ok' and fit['rank']==k==len(fit['retained_terms'])
            assert g==counts.loc[prefecture,'meshes'] and n==counts.loc[prefecture,'observations']==5*g
            omitted=fit['omitted_constant_controls']+fit['omitted_redundant_controls']
            assert k==(3 if spec=='Baseline' else 14-len(omitted))
            assert 'Road Length Density' in fit['retained_terms'] and 'Population' in fit['retained_terms']
            assert set(omitted)<=set(contract['explanatory'])-{'Road Length Density','Population'}
            values=road.loc[road['Group'].eq(group)&road['Specification'].eq(spec)]
            assert len(values)==1
            v=values.iloc[0]
            term=next(t for t in fit['coefficients'] if t['variable']=='Road Length Density')
            assert term['status']==v['status']=='estimated'
            for field in ['coefficient','clustered_standard_error','confidence_lower','confidence_upper']:
                np.testing.assert_allclose(v[field],term[field],rtol=1e-12,atol=1e-14)
            i=fit['retained_terms'].index('Road Length Density')
            se=np.sqrt(fit['covariance_retained'][i][i])
            np.testing.assert_allclose(v['clustered_standard_error'],se,rtol=1e-12)
            np.testing.assert_allclose([v['confidence_lower'],v['confidence_upper']],
                [v['coefficient']-Z95*se,v['coefficient']+Z95*se],rtol=1e-12,atol=1e-14)
            assert np.isfinite(v['p_value']) and 0 <= v['p_value'] <= 1
            np.testing.assert_allclose(v['p_value'],term['p_value'],rtol=1e-12,atol=1e-300)
            log_p=np.log(2.)+norm.logsf(abs(v['coefficient']/se))
            independent_stars='***' if log_p < np.log(.01) else '**' if log_p < np.log(.05) else '*' if log_p < np.log(.10) else ''
            assert stars(v['p_value'])==independent_stars
            np.testing.assert_allclose(fit['cr1_factor'],g/(g-1)*(n-1)/(n-k),rtol=1e-12)
            r2=1-fit['rss']/fit['outcome_tss']
            np.testing.assert_allclose([v['R Squared'],fit['ordinary_pooled_r_squared']],[r2,r2],rtol=1e-12)
            assert v['Meshes']==g and v['Observations']==n
            outcome_tss.append(fit['outcome_tss'])
            records.append(v)
            checks.append({'prefecture':prefecture,'model':spec,'meshes':g,'observations':n,
                           'road_estimate_and_interval':'passed','covariance_diagonal_se':'passed',
                           'cr1_retained_rank':'passed','r_squared_from_rss_tss':'passed',
                           'significance_stars':stars(v['p_value']),
                           'normal_reference_star_check':'passed','retained_rank':k,
                           'omitted_constant_controls':fit['omitted_constant_controls'],
                           'omitted_redundant_controls':fit['omitted_redundant_controls']})
        assert outcome_tss[0]==outcome_tss[1]
        formatted=[f'{v["coefficient"]:.6f}{stars(v["p_value"])}\n[{v["confidence_lower"]:.6f}, {v["confidence_upper"]:.6f}]' for v in records]
        rows.append([prefecture,*formatted,int(counts.loc[prefecture,'meshes']),
                     float(records[0]['R Squared']),float(records[1]['R Squared'])])
    columns=['Prefecture','Baseline road coefficient [95% CI]','Extended road coefficient [95% CI]',
             'Meshes','Baseline R-squared','Extended R-squared']
    table=pd.DataFrame(rows,columns=columns)
    assert table.shape==(47,6) and table['Meshes'].sum()==383386
    notes=pd.DataFrame([
        ('Outcome and units','Dependent variable: Nighttime Radiance (nW/cm2/sr), used as an economic-activity proxy. Road Length Density is in km/km2. Road coefficients are conditional associations in original units, not causal effects.'),
        ('Models','Baseline includes an intercept, Road Length Density and Population. Extended adds five UMD land-cover proportions and six static facility measures. Water Land Cover Share is the omitted reference. Neither model includes fixed effects.'),
        ('Added controls','Urban, Forest, Cropland, Shrublands and Grasslands, and Barren shares; Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count, Visitor and Event Facility Count. Road Length Density and Population are identifiable in all forty-seven fits. Constant or redundant added controls are omitted as recorded below; inference uses the actual retained rank.'),
        ('Samples','Each Prefecture uses identical baseline and extended mesh-period records. Every mesh has five observations, so each prefecture observation count equals five times the displayed mesh count. Forty-seven mutually exclusive Prefectures sum to 383,386 meshes and 1,916,930 records.'),
        ('Inference','Square brackets report individual normal-reference 95 percent confidence intervals based on mesh-clustered CR1 standard errors with actual retained rank. The intervals do not constitute a formal test of between-Prefecture differences.'),
        ('Significance','Stars on road coefficients use existing two-sided normal-reference p values from mesh-clustered CR1 standard errors: * p < 0.10; ** p < 0.05; *** p < 0.01. They describe individual coefficient tests, without multiple-testing adjustment.'),
        ('Periods','Road/light and annual land cover: 2002, 2003, 2004, 2010, 2024. Matched population: 2000, 2005, 2005, 2010, 2020. Facility source snapshots repeat across periods under the approved static assumption.'),
        ('Omitted controls','The extended models omit constant Barren in Tochigi, Saitama, Gifu and Nara. Nara also omits redundant Shrublands and Grasslands. All other Prefectures retain all fourteen parameters. Omitted coefficients are unavailable, not measured zero. Tokyo retains all fourteen parameters.'),
        ('Prefecture order','All forty-seven Prefectures appear in official code order, Hokkaido through Okinawa. Codes remain in the full numerical details; the comparison itself has six columns.'),
        ('Boundary allocation','Reuse the frozen direct largest-positive-Prefecture-land-overlap assignments and the nineteen explicitly approved nearest-land exceptions. Hold assignments fixed across periods, retaining exception flags in source data. Do not reconstruct assignments from mesh centroids.'),
        ('Fit','R-squared is centered ordinary pooled complete-model fit, not road-only explanatory power. Baseline and extended share each Prefecture\'s outcome total sum of squares.'),
        ('Scope','Coverage is conditional on the approved extension cohort; four original meshes with unavailable land cover remain outside it and source records retain their missing values. Historical supplied road density and 2024 centerline-derived density retain source-equivalence limitations.'),
        ('Display','Six decimal places are displayed for road coefficients, confidence bounds and R-squared. Full numerical road estimates and standard errors remain in Road estimate details and the audit export. No trimming or significance shading.'),
    ],columns=['Topic','Note'])
    OUT.parent.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(OUT,engine='openpyxl') as writer:
        table.to_excel(writer,sheet_name='Prefecture comparison',index=False)
        road.to_excel(writer,sheet_name='Road estimate details',index=False)
        notes.to_excel(writer,sheet_name='Notes',index=False)
        for ws in writer.book:
            ws.sheet_view.showGridLines=False;ws.freeze_panes='A2'
            for row in ws:
                for cell in row:
                    cell.font=Font(name='Times New Roman',size=11,bold=cell.row==1)
                    cell.alignment=Alignment(wrap_text=True,vertical='center',horizontal='left' if cell.column==1 else 'center')
            ws.row_dimensions[1].height=38
            for i in range(1,ws.max_column+1):ws.column_dimensions[get_column_letter(i)].width=25
        ws=writer.book['Prefecture comparison']
        for i,width in enumerate([25,37,37,17,23,23],1):ws.column_dimensions[get_column_letter(i)].width=width
        for row in ws.iter_rows(min_row=2):
            ws.row_dimensions[row[0].row].height=46
            row[3].number_format='#,##0';row[4].number_format=row[5].number_format='0.000000'
        thin=Side(style='thin',color='000000')
        for cell in ws[1]:cell.border=Border(top=thin,bottom=thin)
        for cell in ws[48]:cell.border=Border(bottom=thin)
        ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1;ws.print_area=ws.dimensions;ws.print_title_rows='1:1'
        detail=writer.book['Road estimate details']
        for row in detail.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value,float):cell.number_format='0.000000000000'
        ws=writer.book['Notes'];ws.column_dimensions['A'].width=27;ws.column_dimensions['B'].width=135
        for i in range(2,len(notes)+2):ws.row_dimensions[i].height=60
    pd.testing.assert_frame_equal(table,pd.read_excel(OUT,sheet_name='Prefecture comparison'),check_dtype=False,rtol=1e-12)
    pd.testing.assert_frame_equal(road.reset_index(drop=True),pd.read_excel(OUT,sheet_name='Road estimate details'),check_dtype=False,rtol=1e-12,atol=1e-300)
    pd.testing.assert_frame_equal(notes,pd.read_excel(OUT,sheet_name='Notes'))
    wb=load_workbook(OUT);assert wb['Prefecture comparison'].max_row==48 and wb['Prefecture comparison'].max_column==6
    assert not any(cell.data_type=='f' for sheet in wb for row in sheet for cell in row)
    table.to_csv(AUDIT/'table_values.csv',index=False)
    road.to_parquet(AUDIT/'unrounded_road_estimates.parquet',index=False)
    OUT.with_suffix('.caption.md').write_text('Prefecture Road Association Comparison. Forty-seven separate original-scale pooled OLS road coefficients for Nighttime Radiance, controlling for Population in the baseline and adding the approved five UMD land-cover and six facility controls in the extension. Both models use identical prefecture samples with an intercept and no fixed effects. Square brackets show mesh-clustered CR1 normal-reference 95 percent confidence intervals. Stars use existing two-sided normal-reference p values: * p < 0.10; ** p < 0.05; *** p < 0.01, without multiple-testing adjustment. Every mesh contributes five records, so observations are five times the displayed mesh count. R-squared is centered complete-model fit. Water is the omitted land-cover reference. Individual intervals do not test between-Prefecture differences. Extended fits omit constant Barren in Tochigi, Saitama, Gifu and Nara; Nara also omits redundant Shrublands and Grasslands. All forty-seven road coefficients are estimable. Full numerical details and date, geography and interpretation notes accompany the workbook.\n')
    plt.rcParams.update({'font.family':'DejaVu Serif'})
    display=[[r[0],r[1],r[2],f'{r[3]:,}',f'{r[4]:.6f}',f'{r[5]:.6f}'] for r in rows]
    labels=['Prefecture','Baseline road coefficient\n[95% CI]','Extended road coefficient\n[95% CI]',
            'Meshes','Baseline\nR-squared','Extended\nR-squared']
    pages=[]
    for page,(start,end) in enumerate([(0,47)],1):
        display_page=display[start:end]
        fig,ax=plt.subplots(figsize=(15,23));ax.axis('off')
        drawing=ax.table(cellText=display_page,colLabels=labels,cellLoc='center',
                         colWidths=[.17,.245,.245,.10,.12,.12],bbox=[0,.105,1,.885])
        drawing.auto_set_font_size(False);drawing.set_fontsize(10)
        for (r,col),cell in drawing.get_celld().items():
            cell.set_facecolor('white');cell.set_edgecolor('black');cell.set_linewidth(.7)
            cell.visible_edges='TB' if r==0 else 'B' if r==len(display_page) else ''
            if r==0:cell.get_text().set_weight('bold')
            if col==0:cell.get_text().set_ha('left')
        footnotes=[
            'Dependent variable: Nighttime Radiance. Brackets: mesh-clustered CR1 normal-reference 95% intervals.',
            'Same prefecture sample in both models; no fixed effects; observations = 5 × meshes.',
            '* p < 0.10; ** p < 0.05; *** p < 0.01 (individual two-sided normal-reference tests).',
            'Extended: constant Barren omitted in Tochigi, Saitama, Gifu and Nara;',
            'redundant Shrublands and Grasslands also omitted in Nara. All 47 road coefficients are estimable.',
        ]
        for j,note in enumerate(footnotes):
            ax.text(0,.083-j*.015,note,transform=ax.transAxes,fontsize=9)
        fig.subplots_adjust(left=.02,right=.98,top=.99,bottom=.03)
        preview=AUDIT/'preview.png'
        full=OUT.with_suffix('.png')
        fig.savefig(preview,dpi=120,facecolor='white')
        fig.savefig(full,dpi=600,facecolor='white');plt.close(fig)
        pages.append({'page':page,'first_prefecture':display_page[0][0],
                      'last_prefecture':display_page[-1][0],'rows':len(display_page),
                      'output':str(full.relative_to(ROOT))})
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in paths}
    report={'status':'generated_pending_visual_and_human_review','human_review':'pending',
            'title':'Prefecture Road Association Comparison','rows':47,'columns':6,
            'source_hashes':before,'source_files_unchanged':True,'model_refit':False,
            'numerical_checks':checks,'preview_pages':pages,'same_sample_verified':True,'prefecture_partition_verified':True,
            'meshes':383386,'observations':1916930,'all_three_sheets_readback_verified':True,
            'fixed_effects':False,'classification':'UMD','land_reference':'Water Land Cover Share',
            'workbook_sha256':sha(OUT),'script_sha256':sha(Path(__file__))}
    (AUDIT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved: {OUT.relative_to(ROOT)}')
    print('Verified: 47 Prefectures, 94 road estimates; one complete table image.')

if __name__=='__main__':main()
