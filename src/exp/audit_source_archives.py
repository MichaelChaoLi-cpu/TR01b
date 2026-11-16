#!/usr/bin/env python3
"""Audit source archives without extracting geometry or changing raw fields.

Raw attribute views are lossless string tables for exploratory inspection only.
These are not harmonized variables or an analysis-ready panel.
Run: python3 src/exp/audit_source_archives.py
"""
import csv
import io
import json
import statistics
import struct
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-organization'
VIEWS = OUT / 'source-tables'


def write(name, rows, fields=None):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fields:
        return
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def dbf(data):
    n, header, size = struct.unpack_from('<IHH', data, 4)
    fields = []
    offset = 32
    while data[offset] != 13:
        d = data[offset:offset+32]
        fields.append((d[:11].split(b'\0')[0].decode('ascii'), chr(d[11]), d[16], d[17]))
        offset += 32
    rows, deleted = [], 0
    for index in range(n):
        record = data[header+index*size:header+(index+1)*size]
        if record[0:1] == b'*':
            deleted += 1
            continue
        start, row = 1, {}
        for name, kind, width, decimals in fields:
            row[name] = record[start:start+width].decode('cp932').strip()
            start += width
        rows.append(row)
    return rows, fields, deleted


def number(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def tiff_metadata(stream, full=False):
    """Read only selected TIFF IFD metadata, never full global raster arrays."""
    head = stream.read(16)
    order = '<' if head[:2] == b'II' else '>'
    version = struct.unpack_from(order+'H', head, 2)[0]
    big = version == 43
    pointer = struct.unpack_from(order+('Q' if big else 'I'), head, 8 if big else 4)[0]
    # Reject unexpectedly distant directories to avoid inflating an entire ZIP member.
    if pointer > 16*1024*1024 and not full:
        return {'tiff_version': version, 'ifd_offset': pointer, 'metadata_status':'IFD beyond 16 MiB inspection budget'}
    stream.seek(pointer)
    count = struct.unpack(order+('Q' if big else 'H'), stream.read(8 if big else 2))[0]
    entries = stream.read(count*(20 if big else 12))
    tags = {}
    allowed = {256,257,258,259,273,277,278,279,322,323,324,325,339,33550,33922,34735,34736,34737,42113}
    types = {1:('B',1),2:('s',1),3:('H',2),4:('I',4),12:('d',8),16:('Q',8)}
    for i in range(count):
        d = entries[i*(20 if big else 12):(i+1)*(20 if big else 12)]
        tag, kind = struct.unpack_from(order+'HH', d)
        if tag not in allowed or kind not in types:
            continue
        length = struct.unpack_from(order+('Q' if big else 'I'), d, 4)[0]
        fmt, size = types[kind]
        payload = d[12:20] if big else d[8:12]
        total = length*size
        if total > len(payload):
            position = struct.unpack(order+('Q' if big else 'I'), payload)[0]
            if position > 16*1024*1024 and not full:
                continue
            stream.seek(position)
            payload = stream.read(total)
        else:
            payload = payload[:total]
        tags[str(tag)] = payload.decode('ascii').rstrip('\0') if kind == 2 else list(struct.unpack(order+fmt*length, payload))
    return {'tiff_version':version, 'ifd_offset':pointer, 'tags':tags}


def main():
    inventory, columns, markers, categories, units, lengths, raster, anomalies = [], [], [], [], [], [], [], []
    mesh_sets = {}
    for path in sorted((ROOT/'data/raw').rglob('*.zip')):
        rel = str(path.relative_to(ROOT))
        if not any(s in rel for s in ('nighttime_lights/', 'n01_lines/', '5030')):
            continue  # Pilot attributes only; national archives stay intact.
        source = 'ntl' if 'nighttime_lights' in rel else 'population' if 'population/' in rel else path.parent.parent.name
        year = path.parent.name
        with zipfile.ZipFile(path) as z:
            if source == 'ntl':
                item = dict(source=rel, compressed_bytes=path.stat().st_size,
                            uncompressed_bytes=sum(x.file_size for x in z.infolist()), members=z.namelist())
                member = next(n for n in z.namelist() if n.endswith('.tif'))
                with z.open(member) as f:
                    item.update(tiff_metadata(f))
                if 'tags' in item:
                    item['tags']={k:v for k,v in item['tags'].items() if k not in ('273','279','324','325')}
                raster.append(item)
                continue
            if source == 'population':
                member = next(n for n in z.namelist() if n.endswith('.txt'))
                lines = list(csv.reader(io.StringIO(z.read(member).decode('cp932'))))
                header, labels = lines[:2]
                rows = [dict(zip(header, r)) for r in lines[2:] if r]
                fields = [(name,'CSV_string',None,None) for name in header]
                deleted = 0
                identifier = 'KEY_CODE'
                total = next(name for name in header if name.endswith('001') and name.startswith('T'))
                for name, label in zip(header, labels):
                    columns.append(dict(source=rel, field=name, source_label=label, source_type='CSV_string', field_width='', decimals=''))
                    c = Counter(r.get(name,'') for r in rows)
                    for marker in ('','-','X','*'):
                        if c[marker]:markers.append(dict(source=rel, field=name, marker=marker or '<empty>', count=c[marker]))
                numeric = [int(r[total]) for r in rows if r[total].isdigit()]
                lengths.append(dict(source=rel, check='observed_population_total', n=len(numeric),
                                    minimum=min(numeric), median=statistics.median(numeric), maximum=max(numeric),
                                    note='Literal non-numeric markers excluded from this exploratory summary; not recoded.'))
            elif source in ('n01_lines','n04_mesh'):
                member = next(n for n in z.namelist() if n.endswith('.dbf'))
                rows, fields, deleted = dbf(z.read(member))
                for name, kind, width, decimals in fields:
                    columns.append(dict(source=rel, field=name, source_label='', source_type=kind,field_width=width,decimals=decimals))
                    for value,count in Counter(r[name] for r in rows).items():
                        if value in ('','unknown','-','X'):
                            markers.append(dict(source=rel,field=name,marker=value or '<empty>',count=count))
                identifier = 'N04_001' if source == 'n04_mesh' else None
                if source == 'n04_mesh':
                    xml = next(n for n in z.namelist() if n.endswith('.xml') and 'KS-META' not in n)
                    root = ET.fromstring(z.read(xml))
                    ns = {'g':'http://www.opengis.net/gml/3.2'}
                    values = root.find('.//g:CompositeValue/g:valueComponents',ns)
                    for index, value in enumerate(values):
                        units.append(dict(source=rel,field=fields[index][0],source_label=value.text,unit=value.get('uom','count_or_code')))
                    # Check explicit source unit and supplied normalized total, without changing fields.
                    area_unit = list(values)[1].get('uom')
                    actual, normalized = ('N04_055','N04_056') if year=='2010' else ('N04_037','N04_038')
                    residuals = [abs(float(r[actual])/(float(r['N04_002'])/(1e6 if area_unit=='㎡' else 1))-float(r[normalized])) for r in rows if all(number(r[n]) for n in ['N04_002',actual,normalized]) and float(r['N04_002'])>0]
                    for r in rows:
                        if all(number(r[n]) for n in ['N04_002',actual,normalized]) and float(r['N04_002'])>0:
                            difference=abs(float(r[actual])/(float(r['N04_002'])/(1e6 if area_unit=='㎡' else 1))-float(r[normalized]))
                            if difference>1:
                                anomalies.append(dict(source=rel,mesh_code=r['N04_001'],area_literal=r['N04_002'],area_unit=area_unit,actual_field=actual,actual_literal=r[actual],normalized_field=normalized,normalized_literal=r[normalized],absolute_residual=difference,action='Preserve source; no correction applied'))
                    lengths.append(dict(source=rel,check='absolute_normalization_residual_m_per_km2',n=len(residuals),minimum=min(residuals),median=statistics.median(residuals),maximum=max(residuals),note=f'Source area unit={area_unit}; actual={actual}; supplied normalized={normalized}. Audit only.'))
                else:
                    for value, count in Counter(r['N01_001'] for r in rows).items():
                        categories.append(dict(source=rel,field='N01_001',value=value,count=count))
            elif source == 'n13_lines':
                member = next(n for n in z.namelist() if n.endswith('.geojson'))
                geo = json.loads(z.read(member))
                rows = [f['properties'] for f in geo['features']]
                fields = [(name,'GeoJSON',None,None) for name in rows[0]]
                deleted, identifier = 0, None
                for name, kind, width, decimals in fields:
                    columns.append(dict(source=rel,field=name,source_label='',source_type=kind,field_width='',decimals=''))
                    counts = Counter(str(r.get(name,'')) for r in rows)
                    if len(counts)<=20:
                        for value,count in counts.items():
                            categories.append(dict(source=rel,field=name,value=value,count=count))
                del geo
            else:
                continue
            name = source+'_'+year+'_'+path.stem
            write('source-tables/'+name+'.csv',rows,[f[0] for f in fields])
            keys = [r[identifier] for r in rows] if identifier else []
            if identifier:mesh_sets[name]=set(keys)
            inventory.append(dict(source=rel,view='data/exp/data-organization/source-tables/'+name+'.csv',
                                  rows=len(rows),columns=len(fields),identifier=identifier or '',
                                  duplicate_identifiers=len(keys)-len(set(keys)),deleted_dbf_rows=deleted))
            print(source,year,len(rows),len(fields),flush=True)
    coverage=[]
    names=sorted(mesh_sets)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            coverage.append(dict(left=a,right=b,left_meshes=len(mesh_sets[a]),right_meshes=len(mesh_sets[b]),intersection=len(mesh_sets[a]&mesh_sets[b]),left_only=len(mesh_sets[a]-mesh_sets[b]),right_only=len(mesh_sets[b]-mesh_sets[a])))
    for name, rows in [('archive_inventory.csv',inventory),('raw_field_inventory.csv',columns),('source_markers.csv',markers),('road_category_counts.csv',categories),('road_field_units.csv',units),('source_value_checks.csv',lengths),('pilot_mesh_overlap.csv',coverage)]:
        write('tables/'+name,rows)
    write('tables/road_normalization_anomalies.csv',anomalies)
    (OUT/'tables/raster_archive_metadata.json').write_text(json.dumps(raster,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'attribute_archives':len(inventory),'raster_archives':len(raster),'fields':len(columns)}))


if __name__=='__main__':main()
