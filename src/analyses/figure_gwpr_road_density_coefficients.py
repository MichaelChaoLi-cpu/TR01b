#!/usr/bin/env python3
"""GWPR Road Density Coefficients: one approved road-coefficient map.

Framework: weighted local two-way FE, selected common fixed radius, original
four-period national sample. No significance or causal interpretation.
"""
from pathlib import Path
import json
import os

os.environ.setdefault('MPLCONFIGDIR','/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/gwpr-twoways'
PLAN=ROOT/'data/exp/estimation-framework-planning/gwpr-twoways'


def main():
    contract=json.loads((PLAN/'execution_contract.json').read_text())
    assert contract['initial_empirical_output_plan_confirmed']
    data=pd.read_parquet(OUT/'local_coefficients.parquet')
    good=data['Fit Status'].eq('ok'); bad=~good
    beta=data.loc[good,'Road Density Coefficient'].to_numpy()
    limit=float(np.quantile(abs(beta),.98))
    assert limit>0
    boundary=json.loads((OUT/'map_reference_lines.json').read_text())
    fig,ax=plt.subplots(figsize=(9,10))
    context=PolyCollection(boundary['lines'],facecolors='#f2f2f2',edgecolors='#b7b7b7',linewidths=.18,zorder=0)
    ax.add_collection(context)
    ax.scatter(data.loc[bad,'Longitude'],data.loc[bad,'Latitude'],s=5,color='#696969',linewidths=0,zorder=2,label='Non-estimable')
    artist=ax.scatter(data.loc[good,'Longitude'],data.loc[good,'Latitude'],c=beta,
        s=1.8,cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit),linewidths=0,rasterized=True,zorder=3)
    bar=fig.colorbar(artist,ax=ax,fraction=.042,pad=.03,extend='both')
    bar.set_label('Road density coefficient\n(radiance units per km/km²)',fontsize=10)
    ax.set_xlabel('Longitude (degrees east)'); ax.set_ylabel('Latitude (degrees north)')
    ax.set_xlim(data.Longitude.min()-1,data.Longitude.max()+1)
    ax.set_ylim(data.Latitude.min()-1,data.Latitude.max()+1)
    ax.set_aspect(1/np.cos(np.deg2rad(36)))
    if bad.any(): ax.legend(loc='upper left',frameon=False,fontsize=9)
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    path=ROOT/'data/results/figures/Figure_gwpr_road_density_coefficients.png'
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=150,bbox_inches='tight'); plt.close(fig)
    report={'status':'generated_pending_visual_review','output':str(path.relative_to(ROOT)),
        'meshes':len(data),'estimable_meshes':int(good.sum()),'non_estimable_meshes':int(bad.sum()),
        'color_limit_absolute_98th_percentile':limit,'color_clipped_meshes':int(np.count_nonzero(abs(beta)>limit)),
        'coefficient_data_clipped_or_modified':False,'legend':'positive red, negative blue, non-estimable dark gray',
        'boundary_background':boundary['source'],'background_role':'context only; no historical land-mask claim',
        'single_panel':True,'title_embedded':False,'significance_map':False}
    (OUT/'figure_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Saved: '+str(path.relative_to(ROOT)))


if __name__=='__main__': main()
