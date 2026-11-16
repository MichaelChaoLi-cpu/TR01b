"""Geometry-only municipal allocation for the authorized exploratory trial.

Keeps approved Prefecture membership and assigns within that prefecture to the
largest positive municipal land intersection. No nearest-boundary filling.
Runs separately from Arrow; writes CSV. All input meshes survive with status.
"""
from collections import defaultdict
from pathlib import Path
import csv,json,hashlib,math,zipfile,time
import numpy as np
from osgeo import ogr,osr
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/municipality-mismatch-trial'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(e):
 s=osr.SpatialReference();s.ImportFromEPSG(e);s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER);return s
def box(r,c):
 ring=ogr.Geometry(ogr.wkbLinearRing)
 for x,y in [(c/80,r/120),((c+1)/80,r/120),((c+1)/80,(r+1)/120),(c/80,(r+1)/120),(c/80,r/120)]:ring.AddPoint_2D(x,y)
 g=ogr.Geometry(ogr.wkbPolygon);g.AddGeometry(ring);return g
def main():
 ogr.UseExceptions();osr.UseExceptions();osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
 src=OUT/'mesh_geography_input.csv';digest=sha(src)
 with src.open() as f:sample=list(csv.DictReader(f))
 manifest=json.loads((ROOT/'data/exp/data-preprocessing/regional/reference/manifest.json').read_text())
 geo=ref(4612);transforms={};results=[];overlaps=[];audits=[]
 for k,rec in enumerate(manifest,1):
  pref=rec['prefecture_code'];codes=[x['Mesh Code'] for x in sample if x['Prefecture Code']==pref]
  positions={};rows=defaultdict(list)
  for code in codes:
   r=int(code[:2])*80+int(code[4])*10+int(code[6]);c=(int(code[2:4])+100)*80+int(code[5])*10+int(code[7]);positions[(r,c)]=code;rows[r].append(c)
  rows={r:np.array(sorted(c)) for r,c in rows.items()};rr=np.array(sorted(rows));boxes={};full=defaultdict(set);partial=defaultdict(lambda:defaultdict(list))
  p=ROOT/rec['path'];assert sha(p)==rec['sha256']
  with zipfile.ZipFile(p) as z:member=next(n for n in z.namelist() if n.endswith('.shp'))
  ds=ogr.Open('/vsizip/'+str(p)+'/'+member);layer=ds.GetLayer();sr=layer.GetSpatialRef().Clone();sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER);tf=osr.CoordinateTransformation(sr,geo)
  features=tests=clipped=invalid=unidentified=0
  for feat in layer:
   features+=1;city=feat.GetField('N03_004');code=feat.GetField('N03_007')
   if not city or city=='所属未定地' or not code or code.endswith('000'):unidentified+=1;continue
   g=feat.GetGeometryRef().Clone();g.Transform(tf);xmin,xmax,ymin,ymax=g.GetEnvelope()
   rlo,rhi=math.floor(ymin*120+1e-9),math.ceil(ymax*120-1e-9);clo,chi=math.floor(xmin*80+1e-9),math.ceil(xmax*80-1e-9)
   selected=rr[np.searchsorted(rr,rlo):np.searchsorted(rr,rhi)]
   if not len(selected):continue
   if not g.IsValid():g=g.MakeValid();invalid+=1
   prepared=g.CreatePreparedGeometry()
   for r in selected:
    cs=rows[r]
    for c in cs[np.searchsorted(cs,clo):np.searchsorted(cs,chi)]:
     mesh=positions[(r,c)]
     if city in full[mesh]:continue
     tests+=1
     if mesh not in boxes:boxes[mesh]=box(r,c)
     b=boxes[mesh]
     if prepared.Contains(b):full[mesh].add(city);partial[mesh].pop(city,None)
     elif prepared.Intersects(b):
      inter=g.Intersection(b)
      if not inter.IsEmpty() and inter.GetArea()>0:partial[mesh][city].append(inter);clipped+=1
  ds=None
  for mesh in codes:
   tile=mesh[:4]
   if tile not in transforms:
    south=int(tile[:2])*2/3;west=int(tile[2:])+100;target=ref(4612);target.SetProjCS('Local mesh-tile transverse Mercator');target.SetTM(south+1/3,west+.5,1,0,0);transforms[tile]=osr.CoordinateTransformation(geo,target)
   areas={}
   for city in sorted(full[mesh]|set(partial[mesh])):
    if city in full[mesh]:g=boxes[mesh].Clone()
    else:
     fragments=partial[mesh][city]
     if len(fragments)==1:g=fragments[0].Clone()
     else:
      g=ogr.Geometry(ogr.wkbGeometryCollection)
      for part in fragments:g.AddGeometry(part)
      g=g.UnaryUnion()
    g.Transform(transforms[tile]);area=g.GetArea()
    if area>1e-4:areas[city]=area;overlaps.append({'Mesh Code':mesh,'Prefecture Code':pref,'Municipality Name':city,'Municipal Land Overlap':area/1e6})
   ordered=sorted(areas,key=lambda a:(-areas[a],a));tie=len(ordered)>1 and abs(areas[ordered[0]]-areas[ordered[1]])<=1e-6;city=ordered[0] if ordered and not tie else None
   results.append({'Mesh Code':mesh,'Prefecture Code':pref,'Municipality Name':city,'Cross Municipality Mesh':len(ordered)>1,
    'Assigned Municipal Land Area':areas[city]/1e6 if city else None,'Total Municipal Land Overlap':sum(areas.values())/1e6,
    'Municipal Land Share':areas[city]/sum(areas.values()) if city else None,'Municipality Assignment Status':'assigned' if city else ('area_tie' if tie else 'no_identified_municipal_land_overlap')})
  audits.append({'Prefecture Code':pref,'Source Features':features,'Mesh Tests':tests,'Partial Intersections':clipped,'Invalid Geometries Repaired':invalid,'Unidentified Area Features':unidentified,'SHA256':rec['sha256']})
  print(f'Municipal geometry {k}/47: prefecture {pref}, {len(codes):,} meshes, {clipped:,} partial intersections',flush=True)
 for name,rows in [('mesh_municipality_assignment.csv',results),('mesh_municipality_overlaps.csv',overlaps),('municipal_geometry_source_audit.csv',audits)]:
  with (OUT/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 assert len(results)==383386 and len({x['Mesh Code'] for x in results})==383386 and sha(src)==digest
 report={'status':'completed_with_explicit_assignment_gaps','meshes':len(results),'assigned_meshes':sum(x['Municipality Name'] is not None for x in results),
         'unassigned_meshes':[x['Mesh Code'] for x in results if x['Municipality Name'] is None],
         'cross_municipality_meshes':sum(x['Cross Municipality Mesh'] for x in results),'source_sha256':digest,
         'method':'Largest positive identified municipal land area within the already approved prefecture; metric area; designated-city wards united by parent-city name; no fallback',
         'thresholds':'Area > 1e-4 m2; tied maximum within 1e-6 m2 retained unavailable',
         'decision':'MILI-D-20261011-002','implementation_conventions':'Agent-specified exploratory allocation; not new human-selected final geography rule'}
 (OUT/'municipal_geometry_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='unassigned_meshes'},indent=2),flush=True)
if __name__=='__main__':main()
