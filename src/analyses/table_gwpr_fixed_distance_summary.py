#!/usr/bin/env python3
"""GWPR Fixed-Distance Summary and complete coefficient dataset.

Framework: selected range-constrained whole-mesh within-change CV; local
weighted mesh/time FE. Preserve all IDs and failed slopes as NaN.
"""
from pathlib import Path
import json
import shutil

import numpy as np
import pandas as pd
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment,Font,PatternFill

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/gwpr-twoways'
PLAN=ROOT/'data/exp/estimation-framework-planning/gwpr-twoways'


def main():
    contract=json.loads((PLAN/'execution_contract.json').read_text())
    assert contract['initial_empirical_output_plan_confirmed']
    data=pd.read_parquet(OUT/'local_coefficients.parquet'); good=data['Fit Status'].eq('ok')
    search=json.loads((OUT/'selected_bandwidth.json').read_text())
    fit=json.loads((OUT/'fit_validation.json').read_text())
    def distribution(name):
        values=data.loc[good,name].to_numpy()
        return ', '.join(f'{v:.6f}' for v in np.quantile(values,[.05,.5,.95]))
    rows=[
        ['Selected fixed radius',search['bandwidth_km'],'km','Minimum within the requested 5-50 km grid; lower-bound optimum is range-constrained.'],
        ['Common-set within-change CV MSE',search['cv_mse'],'squared radiance units','Approximate stratified-center CV with entire focal meshes excluded from training.'],
        ['Common validation centers',search['common_validation_centers'],'meshes','1,286 initial centers; use the same estimable intersection for all 46 candidates.'],
        ['Common validation weight coverage',search['common_weight_coverage'],'fraction','Design-weight coverage; not a guarantee of representativeness of excluded locations.'],
        ['National focal meshes',len(data),'meshes','All accepted original mesh IDs retained.'],
        ['Panel observations',fit['observations'],'records','Four historical periods: 2002, 2003, 2004, 2010.'],
        ['Estimable local models',int(good.sum()),'meshes','Original-scale road and population slopes under local weighted mesh and period effects.'],
        ['Non-estimable local models',int((~good).sum()),'meshes','Coefficients remain NaN with explicit reasons; no radius fallback or ridge penalty.'],
        ['Median positive-weight support',float(data.loc[good,'Positive Weight Meshes'].median()),'meshes','Includes the focal mesh in final fits; support differs under a fixed distance.'],
        ['Median effective weight support',float(data.loc[good,'Effective Weight Meshes'].median()),'meshes','(sum w)^2 / sum(w^2); a support diagnostic, not residual degrees of freedom.'],
        ['Road slope: p05, median, p95',distribution('Road Density Coefficient'),'radiance per km/km2','Distribution across estimable focal meshes; not confidence limits.'],
        ['Population slope: p05, median, p95',distribution('Population Coefficient'),'radiance per person','Population is a locally estimated control; not confidence limits.'],
    ]
    wb=Workbook(); ws=wb.active; ws.title='GWPR Summary'
    ws.merge_cells('A1:D1'); ws['A1']='GWPR Fixed-Distance Summary'; ws['A1'].font=Font(name='Calibri',size=16,bold=True,color='17324D')
    ws.merge_cells('A2:D2'); ws['A2']='Original-scale national panel | Local weighted mesh and time effects | Fixed bisquare kernel'
    for j,value in enumerate(['Diagnostic','Value','Units','Interpretation'],1):
        cell=ws.cell(4,j,value); cell.font=Font(name='Calibri',bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='17324D')
    for i,row in enumerate(rows,5):
        for j,value in enumerate(row,1):
            cell=ws.cell(i,j,value); cell.font=Font(name='Calibri',size=11); cell.alignment=Alignment(wrap_text=True,vertical='center')
            if isinstance(value,float): cell.number_format='0.000000'
            if i%2: cell.fill=PatternFill('solid',fgColor='F0F4F8')
        ws.row_dimensions[i].height=36
    notes=[
        'Bandwidth is optimal only within the user-requested 5-50 km grid. The lower-bound optimum does not establish a global bandwidth optimum. CV is conditional on a common estimable validation set; retain all candidate failures in the audit ledger.',
        'Kernel distances are great-circle distances between statistical-mesh centroids, with spherical Earth radius 6371.0088 km. Local spatial slopes are constant over the four periods; time effects are refitted locally.',
        'These are descriptive conditional associations. No causal transport effect, causal spillover, formal spatial coefficient-variation test, or local confidence/p-value map is reported. Spatial dependence and overlapping neighborhoods remain inference limitations.',
        'The map color scale saturates at the 98th percentile of absolute road slopes. Full coefficients remain unchanged in the complete saved dataset; dark gray denotes non-estimable models.',
    ]
    for i,note in enumerate(notes,19):
        ws.merge_cells(start_row=i,start_column=1,end_row=i,end_column=4)
        ws.cell(i,1,note).alignment=Alignment(wrap_text=True,vertical='top'); ws.cell(i,1).font=Font(name='Calibri',size=10,color='526679'); ws.row_dimensions[i].height=40
    for col,width in zip('ABCD',[36,34,27,72]): ws.column_dimensions[col].width=width
    ws.freeze_panes='B5'; ws.auto_filter.ref='A4:D16'; ws.sheet_view.showGridLines=False
    ws.row_dimensions[1].height=26; ws.row_dimensions[2].height=23
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=1; ws.sheet_properties.pageSetUpPr.fitToPage=True; ws.print_area='A1:D22'
    output=ROOT/'data/results/tables/Table_gwpr_fixed_distance_summary.xlsx'; output.parent.mkdir(parents=True,exist_ok=True); wb.save(output)
    exported=load_workbook(output,data_only=True)
    for i,row in enumerate(rows,5):
        for j,value in enumerate(row,1):
            actual=exported.active.cell(i,j).value
            if isinstance(value,float): assert np.isclose(actual,value,rtol=1e-13,atol=1e-15)
            else: assert actual==value
    shutil.copyfile(OUT/'local_coefficients.parquet',output.parent/'GWPR_local_coefficients.parquet')
    shutil.copyfile(OUT/'local_coefficients.csv',output.parent/'GWPR_local_coefficients.csv')
    assert len(pd.read_parquet(output.parent/'GWPR_local_coefficients.parquet'))==len(data)
    (OUT/'table_validation.json').write_text(json.dumps({'status':'passed','rows':12,'columns':4,
        'workbook_readback_verified':True,'all_coefficient_mesh_ids_retained':True,
        'output':str(output.relative_to(ROOT)),'human_output_acceptance':'pending'},indent=2)+'\n')
    print('Saved: '+str(output.relative_to(ROOT)))


if __name__=='__main__': main()
