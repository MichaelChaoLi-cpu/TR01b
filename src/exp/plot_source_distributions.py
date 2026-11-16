#!/usr/bin/env python3
"""Plot pilot source distributions without defining analysis variables.

Literal unknown/suppression markers remain in the source views. Numeric-only
histograms describe observed values; they do not imply missing equals zero.
"""
import csv
import os
import tempfile
from pathlib import Path

os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'tr01b-cache'))
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'tr01b-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
VIEWS=ROOT/'data/exp/data-organization/source-tables'
OUT=ROOT/'data/exp/data-briefing/figures/distributions'


def observed(path, field):
    rows=list(csv.DictReader(path.open(encoding='utf8')))
    values=[]
    for row in rows:
        try:values.append(float(row[field]))
        except ValueError:pass
    return values,len(rows)-len(values)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    specifications=[('population','Population per listed mesh (persons)',[(1995,'T000751001'),(2000,'T000146001'),(2005,'T000148001'),(2010,'T000608001'),(2020,'T001100001')]),
                    ('n04_mesh','Supplied normalized road length (m per square kilometre)',[(2002,'N04_038'),(2003,'N04_038'),(2004,'N04_038'),(2010,'N04_056')])]
    receipt=[]
    for source,label,waves in specifications:
        fig,axes=plt.subplots(1,len(waves),figsize=(3.3*len(waves),3.6),sharey=True)
        for ax,(year,field) in zip(axes,waves):
            path=next(VIEWS.glob(f'{source}_{year}_*.csv'))
            values,excluded=observed(path,field)
            ax.hist(values,bins=35,color='#356a9b',edgecolor='white',linewidth=.3)
            ax.set_title(f'{year}\nObserved n={len(values):,}; nonnumeric={excluded:,}',fontsize=10)
            ax.tick_params(labelsize=8)
            ax.set_xlabel('Population (persons)' if source=='population' else 'Normalized road length (m/km2)',fontsize=8)
            receipt.append(dict(source_view=str(path.relative_to(ROOT)),field=field,year=year,observed_values=len(values),excluded_literal_markers=excluded))
        axes[0].set_ylabel('Number of listed mesh records')
        fig.suptitle('Pilot source distributions: coverage varies across years',fontsize=12)
        fig.tight_layout()
        fig.savefig(OUT/f'{source}_pilot_distributions.png',dpi=160)
        plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(11,6.5))
    for ax,path in zip(axes.flat,sorted((ROOT/'data/exp/data-organization/nighttime-pilot').glob('*_native_pixels.csv'))):
        values,excluded=observed(path,'source_radiance')
        ax.hist(values,bins=40,color='#356a9b',edgecolor='white',linewidth=.3)
        ax.set_title(f'{path.name[:4]}: n={len(values):,}; literal zero={sum(v==0 for v in values):,}',fontsize=10)
        ax.set_xlabel('Native pixel radiance (nW/cm2/sr)',fontsize=9)
        ax.set_ylabel('Pixels',fontsize=9)
        ax.tick_params(labelsize=8)
        receipt.append(dict(source_view=str(path.relative_to(ROOT)),field='source_radiance',year=path.name[:4],observed_values=len(values),excluded_literal_markers=excluded))
    fig.suptitle('Pilot nighttime-light distributions: native grids, including sea; no aggregation')
    fig.tight_layout()
    fig.savefig(OUT/'nighttime_pilot_distributions.png',dpi=160)
    plt.close(fig)
    with (ROOT/'data/exp/data-briefing/tables/distribution_receipt.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,list(receipt[0]));w.writeheader();w.writerows(receipt)
    print('Saved three pilot distribution figures; no time-series plots generated.')


if __name__=='__main__':main()
