#!/usr/bin/env python3
"""National Road Associations.

AnaSOP Sections 5-7: same-sample baseline/extended pooled OLS in original
units, mesh-clustered CR1 covariance and normal 95% intervals; no fixed effects.
Render the validated UMD estimates without refitting models or changing data.
Reproduce: uv run python src/analyses/table_national_road_associations.py
"""
from pathlib import Path
import hashlib
import json
import os
import textwrap

os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, Border, Side
from scipy.stats import norm
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/umd-four-layer'
OUT = ROOT / 'data/results/tables/Table_national_road_associations.xlsx'
AUDIT = ROOT / 'data/exp/figure-table-generation/national-road-associations'
TERMS = ['Intercept', 'Road Length Density', 'Population', 'Urban Land Cover Share',
         'Forest Land Cover Share', 'Cropland Land Cover Share', 'Shrublands and Grasslands',
         'Barren', 'Distance to Railway Station', 'Distance to Passenger Airport',
         'School Facility Count', 'Medical Facility Count', 'Logistics Facility Count',
         'Visitor and Event Facility Count']
Z95 = 1.959963984540054

def stars(p_value):
    return '***' if p_value < .01 else '**' if p_value < .05 else '*' if p_value < .10 else ''


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    paths = [SOURCE / p for p in ['national_coefficients.csv', 'national_validation.json',
             'pooled_validation.json', 'delivery_validation.json', 'independent_delivery_validation.json',
             'inputs/model_panel.parquet']]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    c = pd.read_csv(paths[0], float_precision='round_trip')
    nv, pv, delivery, independent = [json.loads(p.read_text()) for p in paths[1:5]]
    assert all(v['status'] == 'passed' for v in [nv, pv, delivery, independent])
    assert pv['input_sha256'] == sha(paths[-1])
    assert delivery['classification'] == 'UMD' and delivery['land_cover_reference'] == 'Water Land Cover Share'
    assert delivery['effects'] == [] and pv['same_sample_verified']
    assert len(nv['results']) == 1 and nv['results'][0]['group'] == 'Japan'
    models = {'Baseline': nv['results'][0]['baseline_same_sample'],
              'Extended': nv['results'][0]['extended']}
    assert len(c) == 17 and c['Group'].eq('Japan').all()
    assert not c.duplicated(['Specification', 'variable']).any()
    assert c['status'].eq('estimated').all()
    checks = []
    for spec, model in models.items():
        assert model['status'] == 'ok'
        assert model['meshes'] == 383386 and model['observations'] == 1916930
        assert not model['omitted_constant_controls'] and not model['omitted_redundant_controls']
        expected = TERMS[:3] if spec == 'Baseline' else TERMS
        assert model['retained_terms'] == expected
        assert model['rank'] == model['parameters'] == len(expected)
        subset = c.loc[c['Specification'].eq(spec)].set_index('variable')
        assert subset.index.tolist() == expected
        covariance = np.asarray(model['covariance_retained'])
        np.testing.assert_allclose(covariance, covariance.T, rtol=1e-9, atol=1e-12)
        se_from_cov = np.sqrt(np.diag(covariance))
        cr1 = 383386 / (383386-1) * (1916930-1) / (1916930-len(expected))
        np.testing.assert_allclose(model['cr1_factor'], cr1, rtol=1e-12)
        r_squared = 1 - model['rss'] / model['outcome_tss']
        np.testing.assert_allclose(model['ordinary_pooled_r_squared'], r_squared, rtol=1e-12)
        assert subset['Meshes'].eq(383386).all() and subset['Observations'].eq(1916930).all()
        np.testing.assert_allclose(subset['R Squared'], r_squared, rtol=1e-12)
        for i, coef in enumerate(model['coefficients']):
            row = subset.loc[coef['variable']]
            for field in ['coefficient', 'clustered_standard_error', 'confidence_lower', 'confidence_upper', 'p_value']:
                np.testing.assert_allclose(row[field], coef[field], rtol=1e-12, atol=1e-14)
            np.testing.assert_allclose(row['clustered_standard_error'], se_from_cov[i], rtol=1e-12)
            log_p = np.log(2.) + norm.logsf(abs(row['coefficient'] / se_from_cov[i]))
            independent_stars = '***' if log_p < np.log(.01) else '**' if log_p < np.log(.05) else '*' if log_p < np.log(.10) else ''
            assert stars(row['p_value']) == independent_stars
            np.testing.assert_allclose([row['confidence_lower'], row['confidence_upper']],
                [row['coefficient'] - Z95*se_from_cov[i], row['coefficient'] + Z95*se_from_cov[i]],
                rtol=1e-12, atol=1e-14)
        checks.append({'model': spec, 'parameters_checked': len(expected),
                       'covariance_diagonal_se': 'passed', 'normal_95_intervals': 'passed',
                       'r_squared_from_rss_tss': 'passed', 'cr1_factor': cr1})
    assert models['Baseline']['outcome_tss'] == models['Extended']['outcome_tss']
    columns = ['Term or diagnostic', 'Baseline coefficient or value', 'Baseline SE', 'Baseline 95% CI',
               'Extended coefficient or value', 'Extended SE', 'Extended 95% CI']
    rows = []
    for term in TERMS:
        row = [term]
        for spec in ['Baseline', 'Extended']:
            found = c.loc[c['Specification'].eq(spec) & c['variable'].eq(term)]
            if found.empty:
                assert spec == 'Baseline' and term not in TERMS[:3]
                row.extend([np.nan, np.nan, np.nan])
            else:
                v = found.iloc[0]
                row.extend([float(v['coefficient']), float(v['clustered_standard_error']),
                            f'[{v["confidence_lower"]:.6f}, {v["confidence_upper"]:.6f}]'])
        rows.append(row)
    diagnostics = [
        ('Meshes', 383386, 383386), ('Observations', 1916930, 1916930),
        ('Periods', 5, 5),
        ('Centered R-squared', models['Baseline']['ordinary_pooled_r_squared'], models['Extended']['ordinary_pooled_r_squared']),
        ('Covariance method', 'Mesh-clustered CR1', 'Mesh-clustered CR1'),
        ('Fixed effects', 'No', 'No'),
    ]
    for label, b, e in diagnostics:rows.append([label, b, np.nan, np.nan, e, np.nan, np.nan])
    table = pd.DataFrame(rows, columns=columns)
    assert table.shape == (20, 7)
    assert table.loc[3:13, columns[1:4]].isna().all().all()
    notes = pd.DataFrame([
        ('Outcome', 'Nighttime Radiance, an economic-activity proxy measured in nW/cm2/sr. Coefficients describe conditional associations, not causal effects.'),
        ('Baseline', 'Intercept, Road Length Density and Population.'),
        ('Extended', 'Baseline plus Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands, Barren, Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count and Visitor and Event Facility Count.'),
        ('Reference', 'Water Land Cover Share is the omitted land-cover reference. The six UMD shares are based on full mesh area and are not normalized under incomplete coverage. All fourteen national parameters are estimable; no national controls are dropped.'),
        ('Units', 'Original scales: road density km/km2; population persons/mesh; land cover area proportions; station/airport distances km; facilities counts/mesh. No logarithms or standardization.'),
        ('Sample', 'Both models use the identical balanced cohort of 383,386 meshes and 1,916,930 observations, five records per mesh. Four original meshes with unavailable land cover are outside the approved extension; source materials retain them.'),
        ('Dates', 'Road/light and annual land-cover periods: 2002, 2003, 2004, 2010, 2024. Matched population years: 2000, 2005, 2005, 2010, 2020. Facility source snapshots repeat across periods under the approved static assumption.'),
        ('Inference', 'Mesh-clustered CR1 standard errors combine all five records of each mesh. Correction uses three retained baseline parameters or fourteen extended parameters. Individual 95 percent confidence intervals use a normal reference. They are not a formal test of the difference between model coefficients.'),
        ('Fit', 'Centered ordinary pooled R-squared summarizes the complete model. It is not the fraction of radiance explained by roads alone. Both models use the same outcome total sum of squares.'),
        ('Fixed effects', 'No mesh, time or other fixed effects in either model.'),
        ('Blank entries', 'Blank baseline control cells mean the variable is not included in that model, not an estimated zero. SE and CI are not applicable to diagnostic rows.'),
        ('Display', 'Stargazer-style three-column layout: coefficients with significance stars above parenthesized mesh-clustered standard errors. Constant denotes Intercept, displayed last. Six decimal places retain small nonzero estimates and standard errors. Full-precision coefficients, standard errors, p values and confidence bounds remain in Estimation details.'),
        ('Stars', '* p < 0.10; ** p < 0.05; *** p < 0.01. Stars use existing two-sided normal-reference coefficient p values based on mesh-clustered CR1 standard errors. A stored zero p value is numerical underflow, not proof of an exact zero probability.'),
        ('Comparability', 'Historical supplied road density and 2024 centerline-derived density retain source-equivalence limits. Nearest-year population matching and static facility replication do not reconstruct continuous historical change.'),
    ], columns=['Topic', 'Note'])
    OUT.parent.mkdir(parents=True, exist_ok=True);AUDIT.mkdir(parents=True, exist_ok=True)
    styled_rows = []
    for term in TERMS[1:] + ['Intercept']:
        coefficients, standard_errors = [], []
        for spec in ['Baseline', 'Extended']:
            found = c.loc[c['Specification'].eq(spec) & c['variable'].eq(term)]
            if found.empty:
                coefficients.append('');standard_errors.append('')
            else:
                v = found.iloc[0]
                coefficients.append(f'{v["coefficient"]:.6f}{stars(v["p_value"])}')
                standard_errors.append(f'({v["clustered_standard_error"]:.6f})')
        styled_rows.append(['Constant' if term == 'Intercept' else term, *coefficients])
        styled_rows.append(['', *standard_errors])
    for label, b, e in diagnostics:
        if isinstance(b, str):values=[b,e]
        elif label == 'Centered R-squared':values=[f'{b:.6f}',f'{e:.6f}']
        else:values=[f'{b:,}',f'{e:,}']
        styled_rows.append([label, *values])
    styled = pd.DataFrame(styled_rows, columns=['Term or diagnostic', '(1) Baseline', '(2) Extended'])
    assert styled.shape == (34,3)
    legend = '* p < 0.10; ** p < 0.05; *** p < 0.01'
    footnotes = ['Mesh-clustered CR1 standard errors in parentheses.',
                 legend, 'Water is the omitted land-cover reference; neither model includes fixed effects.']
    with pd.ExcelWriter(OUT, engine='openpyxl') as writer:
        styled.to_excel(writer,sheet_name='National associations',startrow=4,header=False,index=False)
        c.to_excel(writer,sheet_name='Estimation details',index=False)
        notes.to_excel(writer,sheet_name='Notes',index=False)
        ws=writer.book['National associations'];ws.sheet_view.showGridLines=False
        ws.merge_cells('B1:C1');ws['B1']='Dependent variable:'
        ws.merge_cells('B2:C2');ws['B2']='Nighttime Radiance'
        ws['B3']='Baseline';ws['C3']='Extended';ws['B4']='(1)';ws['C4']='(2)'
        for row in ws.iter_rows(min_row=1,max_row=38,max_col=3):
            for cell in row:
                cell.font=Font(name='Times New Roman',size=12)
                cell.alignment=Alignment(horizontal='left' if cell.column==1 else 'center',vertical='center',wrap_text=True)
            ws.row_dimensions[row[0].row].height=23
        ws['B1'].font=Font(name='Times New Roman',size=11,italic=True)
        ws['B3'].font=ws['C3'].font=Font(name='Times New Roman',size=12,bold=True)
        for i in range(6,33,2):
            ws.row_dimensions[i].height=19
            for cell in ws[i]:cell.font=Font(name='Times New Roman',size=11)
        for r in [1,4,33,38]:
            for cell in ws[r]:
                side=Side(style='thin',color='000000')
                cell.border=Border(top=side) if r in [1,33] else Border(bottom=side)
        for i,line in enumerate(footnotes,40):
            ws.merge_cells(start_row=i,start_column=1,end_row=i,end_column=3)
            ws.cell(i,1,line).font=Font(name='Times New Roman',size=10)
            ws.cell(i,1).alignment=Alignment(wrap_text=True,vertical='center')
            ws.row_dimensions[i].height=25
        for col,width in zip('ABC',[48,28,28]):ws.column_dimensions[col].width=width
        ws.freeze_panes='B5';ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_setup.orientation='portrait';ws.page_setup.paperSize=ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1;ws.print_area='A1:C42'
        for name in ['Estimation details','Notes']:
            detail=writer.book[name];detail.freeze_panes='A2';detail.auto_filter.ref=detail.dimensions
            for row in detail:
                for cell in row:
                    cell.font=Font(name='Times New Roman',size=11,bold=cell.row==1)
                    cell.alignment=Alignment(wrap_text=True,vertical='center')
                    if isinstance(cell.value,float):cell.number_format='0.000000000000'
            for i in range(1,detail.max_column+1):detail.column_dimensions[get_column_letter(i)].width=25
        writer.book['Notes'].column_dimensions['B'].width=130
        for i in range(2,len(notes)+2):writer.book['Notes'].row_dimensions[i].height=60
    readback = pd.read_excel(OUT,sheet_name='National associations',header=None,skiprows=4,nrows=34,keep_default_na=False)
    assert readback.to_numpy().tolist()==styled.to_numpy().tolist()
    pd.testing.assert_frame_equal(c,pd.read_excel(OUT,sheet_name='Estimation details'),check_dtype=False,rtol=1e-12,atol=1e-300)
    pd.testing.assert_frame_equal(notes,pd.read_excel(OUT,sheet_name='Notes'))
    wb=load_workbook(OUT)
    assert not any(cell.data_type=='f' for sheet in wb for row in sheet for cell in row)
    styled.to_csv(AUDIT/'table_values.csv',index=False)
    table.to_csv(AUDIT/'separate_column_details.csv',index=False)
    c.to_parquet(AUDIT/'unrounded_source_estimates.parquet',index=False)
    OUT.with_suffix('.caption.md').write_text('National Road Associations. Stargazer-style presentation of original-scale Nighttime Radiance pooled OLS models. Coefficients are followed by mesh-clustered CR1 standard errors in parentheses; * p < 0.10, ** p < 0.05, *** p < 0.01, using the existing two-sided normal-reference coefficient tests. Both models share 383,386 meshes, 1,916,930 records and five periods, without fixed effects. Water is the omitted UMD reference. Blank baseline cells denote excluded controls, not estimated zeros. R-squared describes complete-model fit. Full numerical details and 95 percent confidence bounds are retained in Estimation details. See Notes for dates, units and interpretation limits. Layout follows the R stargazer convention, rendered reproducibly with local Python without model refitting.\n')
    plt.rcParams.update({'font.family':'DejaVu Serif','mathtext.fontset':'dejavuserif'})
    fig,ax=plt.subplots(figsize=(10,13.5));ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    left,right=.025,.975; centers=[.66,.88]
    ax.hlines(.983,left,right,color='black',linewidth=1.1)
    ax.text(.77,.965,'Dependent variable:',ha='center',va='center',fontsize=10,style='italic')
    ax.text(.77,.941,'Nighttime Radiance',ha='center',va='center',fontsize=12)
    ax.hlines(.925,.53,right,color='black',linewidth=.6)
    for x,label,num in zip(centers,['Baseline','Extended'],['(1)','(2)']):
        ax.text(x,.907,label,ha='center',va='center',fontsize=11)
        ax.text(x,.885,num,ha='center',va='center',fontsize=10)
    ax.hlines(.87,left,right,color='black',linewidth=.8)
    y=.847;step=.0217
    for i,row in enumerate(styled_rows):
        if i==28:
            y-=.012;ax.hlines(y+.014,left,right,color='black',linewidth=.8)
        ax.text(left,y,row[0],ha='left',va='center',fontsize=10.2)
        for x,value in zip(centers,row[1:]):
            if value.endswith('*'):
                numeric=value.rstrip('*');mark=value[len(numeric):]
                value=rf'${numeric}^{{{mark}}}$'
            ax.text(x,y,value,ha='center',va='center',fontsize=10.2)
        y-=step
    ax.hlines(y+.010,left,right,color='black',linewidth=.8)
    for i,line in enumerate(footnotes):ax.text(left,y-.010-i*.021,line,ha='left',va='center',fontsize=8)
    fig.subplots_adjust(left=.015,right=.985,top=.995,bottom=.005)
    fig.canvas.draw()
    for item in ax.texts:
        box=item.get_window_extent().transformed(fig.transFigure.inverted())
        assert box.x0>=0 and box.x1<=1 and box.y0>=0 and box.y1<=1,item.get_text()
    fig.savefig(AUDIT/'preview.png',dpi=120,facecolor='white')
    fig.savefig(OUT.with_suffix('.png'),dpi=600,facecolor='white');plt.close(fig)
    assert hashes=={str(p.relative_to(ROOT)):sha(p) for p in paths}
    report={'status':'generated_pending_visual_and_human_review','human_review':'pending',
            'title':'National Road Associations','rows':34,'columns':3,
            'parameter_blocks':14,'diagnostic_rows':6,'style':'R stargazer convention',
            'decision_id':'MILI-D-20261011-040','star_thresholds':[.10,.05,.01],
            'same_sample_meshes':383386,'same_sample_observations':1916930,'periods':5,
            'fixed_effects':False,'model_refit':False,'classification':'UMD',
            'land_reference':'Water Land Cover Share','source_hashes':hashes,
            'source_files_unchanged':True,'numerical_checks':checks,
            'star_classification_independently_verified':True,'all_labels_inside_canvas':True,
            'workbook_all_cells_readback_verified':True,
            'workbook_sha256':sha(OUT),'script_sha256':sha(Path(__file__))}
    (AUDIT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved: {OUT.relative_to(ROOT)}')
    print(styled.to_string(index=False))

if __name__=='__main__':main()
