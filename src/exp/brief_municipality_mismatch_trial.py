"""Focused municipal evidence briefing, no source or scientific-value changes."""
from pathlib import Path
import os,json
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];TRIAL=ROOT/'data/exp/municipality-mismatch-trial';OUT=ROOT/'data/exp/data-briefing/municipality-mismatch-trial'
def main():
 OUT.mkdir(parents=True,exist_ok=True);a=pd.read_parquet(TRIAL/'municipal_evidence_2024.parquet')
 cols=['Candidate Fraction of Supported Meshes','Length Weighted 24h Volume','Maintenance Share of Expenditure','Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio']
 rows=[]
 for c in cols:
  x=a[c];rows.append({'Variable':c,'Rows':len(x),'Missing':int(x.isna().sum()),'Zero':int(x.eq(0).sum()),'Min':float(x.min()),'Median':float(x.median()),'Mean':float(x.mean()),'Max':float(x.max())})
 pd.DataFrame(rows).to_csv(OUT/'variable_summary.csv',index=False)
 pd.read_csv(TRIAL/'source_inventory.csv').to_csv(OUT/'source_inventory.csv',index=False)
 pd.DataFrame([{'Dataset':'Municipal evidence','Rows':len(a),'Columns':len(a.columns)},{'Dataset':'Municipal mesh ledger','Rows':383386,'Columns':len(pd.read_parquet(TRIAL/'municipal_mesh_ledger_2024.parquet').columns)}]).to_csv(OUT/'dataset_inventory.csv',index=False)
 fig,axs=plt.subplots(2,3,figsize=(13,7),layout='constrained')
 for ax,c in zip(axs.flat,cols):
  x=a[c].dropna();ax.hist(x,bins=40,color='#397b92');ax.set_title(c,fontsize=9);ax.set_ylabel('Municipalities');ax.grid(axis='y',alpha=.15)
 axs.flat[-1].axis('off');fig.suptitle('Municipal evidence distributions: source values retained');fig.savefig(OUT/'municipal_distributions.png',dpi=160);plt.close(fig)
 report={'datasets_read':2,'numerical_variables_summarized':5,'distribution_figures':1,'skipped_selected_files':0,'single_cross_section':True,'time_series_visualization_selected':False,'source_values_modified':False}
 (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'README.md').write_text('# Municipal evidence briefing\n\nTwo selected datasets read with local pandas/pyarrow; five numerical variables summarized; one five-panel distribution figure; no selected files skipped. Municipal evidence contains 1,741 governments and actual source dates 2020, 2021, 2023 and 2024. It is a linked cross-section, not five repeated municipal fiscal periods. Traffic means are unavailable for seven governments and remain NaN; the selected fiscal fields are complete. All source meshes remain represented separately. The generic briefing helper was run on an isolated numerical view and falsely identified fraction/year-named numerical variables as time candidates; no actual date axis or time-series visualization is used. No new final-model variables are selected.\n')
 print(report)
if __name__=='__main__':main()
