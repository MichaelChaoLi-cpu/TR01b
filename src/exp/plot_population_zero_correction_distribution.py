#!/usr/bin/env python3
"""Focused population distribution for the corrected historical data briefing."""
from pathlib import Path
import math
import os

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/tr01b_population_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    data = pd.read_parquet(ROOT / 'data/processed/national/population_zero_corrected/balanced_historical_panel_preprocessed.parquet',columns=['Population'])
    values = data.Population
    assert values.notna().all() and (values >= 0).all()
    folder = ROOT / 'data/exp/data-briefing/population-zero-correction/figures/distributions'
    folder.mkdir(parents=True,exist_ok=True)
    fig, ax = plt.subplots(figsize=(8,5),layout='constrained')
    ax.hist(values,bins=min(50,max(10,int(math.sqrt(len(values))))),color='#4C78A8',edgecolor='white')
    ax.set(title='Population in the corrected historical sample',xlabel='Population (persons per mesh)',ylabel='Mesh-period observations')
    ax.text(0.98,0.98,f'{len(values):,} observations; {values.eq(0).sum():,} zeros',
            transform=ax.transAxes,ha='right',va='top',fontsize=9)
    fig.savefig(folder / 'population_corrected_historical_sample.png',dpi=160)
    plt.close(fig)
    print('Saved focused population distribution, original scale and all zeros retained.')


if __name__ == '__main__':
    main()
