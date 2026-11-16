"""Independent OGR direct full-polygon/mesh intersection spot checks.

Uses source spatial filtering and whole municipal polygon unions rather than the
production feature-to-mesh subdivision loop. Geometry process writes only CSV.
"""
from pathlib import Path
import csv,json,zipfile,math
from osgeo import ogr,osr
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/exp/municipality-mismatch-trial'
def ref(e):
 s=osr.SpatialReference();s.ImportFromEPSG(e);s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER);return s
def rect(code):
 r=int(code[:2])*80+int(code[4])*10+int(code[6]);c=(int(code[2:4])+100)*80+int(code[5])*10+int(code[7]);ring=ogr.Geometry(ogr.wkbLinearRing)
 for x,y in [(c/80,r/120),((c+1)/80,r/120),((c+1)/80,(r+1)/120),(c/80,(r+1)/120),(c/80,r/120)]:ring.AddPoint_2D(x,y)
 g=ogr.Geometry(ogr.wkbPolygon);g.AddGeometry(ring);return g

def main():
 ogr.UseExceptions();osr.UseExceptions();osr.SetPROJSearchPaths(['/opt/homebrew/share/proj']);geo=ref(4612)
 with (OUT/'mesh_municipality_assignment.csv').open() as f:rows=list(csv.DictReader(f))
 manifest=json.loads((ROOT/'data/exp/data-preprocessing/regional/reference/manifest.json').read_text());results=[]
 for rec in manifest:
  pref=rec['prefecture_code'];z=[r for r in rows if r['Prefecture Code']==pref and r['Municipality Name']]
  chosen=[]
  for cross in ['True','False']:
   zz=sorted([r for r in z if r['Cross Municipality Mesh']==cross],key=lambda r:r['Mesh Code'])
   if zz:chosen.append(zz[len(zz)//2])
  p=ROOT/rec['path']
  with zipfile.ZipFile(p) as zipf:member=next(n for n in zipf.namelist() if n.endswith('.shp'))
  ds=ogr.Open('/vsizip/'+str(p)+'/'+member);layer=ds.GetLayer()
  for r in chosen:
   code=r['Mesh Code'];mesh=rect(code);layer.SetSpatialFilter(mesh);parts={}
   for feat in layer:
    city=feat.GetField('N03_004');govcode=feat.GetField('N03_007')
    if not city or city=='所属未定地' or not govcode or govcode.endswith('000'):continue
    g=feat.GetGeometryRef().Clone()
    if not g.IsValid():g=g.MakeValid()
    # Actual reference matches JGD2011 and coordinate order used by allocation.
    sr=layer.GetSpatialRef().Clone();sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER);g.Transform(osr.CoordinateTransformation(sr,geo))
    if g.Intersects(mesh):parts.setdefault(city,[]).append(g)
   tile=code[:4];target=ref(4612);target.SetProjCS('Independent local mesh-tile transverse Mercator');target.SetTM(int(tile[:2])*2/3+1/3,int(tile[2:])+100.5,1,0,0);tf=osr.CoordinateTransformation(geo,target)
   areas={}
   for city,polys in parts.items():
    collection=ogr.Geometry(ogr.wkbGeometryCollection)
    for poly in polys:collection.AddGeometry(poly)
    union=collection.UnaryUnion();clip=union.Intersection(mesh);clip.Transform(tf);area=clip.GetArea()
    if area>1e-4:areas[city]=area
   largest=max(areas,key=areas.get);expected=float(r['Assigned Municipal Land Area'])*1e6;delta=abs(areas[largest]-expected)
   assert largest==r['Municipality Name'] and delta<max(.5,expected*1e-4),(code,largest,r['Municipality Name'],delta)
   results.append({'Mesh Code':code,'Prefecture Code':pref,'Municipality Name':largest,'Direct Union Area m2':areas[largest],
     'Production Area m2':expected,'Absolute Difference m2':delta,'Relative Area Difference':delta/expected,'Cross Municipality Mesh':r['Cross Municipality Mesh']})
  print(f'Independent municipality geometry {pref}: {len(chosen)} checks',flush=True);ds=None
 with (OUT/'independent_municipality_geometry_checks.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 report={'status':'passed','independent_checks':len(results),'max_area_difference_m2':max(x['Absolute Difference m2'] for x in results),'max_relative_area_difference':max(x['Relative Area Difference'] for x in results),'area_tolerance':'Max(0.5 m2, 0.0001 * production area); polygon union order changes collinear vertices before nonlinear metric projection, while chosen municipality must agree exactly','method':'Full municipal polygon union then mesh intersection; one cross-boundary and one non-cross-boundary mesh per prefecture where available'}
 (OUT/'independent_geometry_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
