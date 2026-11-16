"""Acquire official e-Stat/MLIT snapshots for the authorized municipal trial."""
from pathlib import Path
import argparse, json, csv
from urllib.parse import urljoin
import acquire_road_mismatch_trial_sources as base
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/municipality-mismatch-trial'
base.SOURCES=OUT/'source_snapshots'
INDEX='https://www.e-stat.go.jp/stat-search/files?cycle=7&layout=datalist&result_back=1&tclass1=000001077756&tclass2=000001077757&toukei=00200251&tstat=000001077755&year=20240'
def main():
 p=argparse.ArgumentParser();p.add_argument('--name');p.add_argument('--url');p.add_argument('--suffix',default='.csv');a=p.parse_args()
 if a.name:
  path=base.fetch(a.name,a.url,a.suffix);print(str(path.relative_to(ROOT)));return
 path=base.fetch('fiscal_municipality_index',INDEX,'.html');parser=base.Links();parser.feed(path.read_text())
 rows=[{'url':urljoin(INDEX,url),'label':label.strip()} for url,label in parser.links if 'file-download' in url or 'stat_infid=' in url]
 with (OUT/'fiscal_index_links.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['url','label']);w.writeheader();w.writerows(rows)
 print(json.dumps({'index':str(path.relative_to(ROOT)),'links':len(rows),'tables':rows[:12]},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
