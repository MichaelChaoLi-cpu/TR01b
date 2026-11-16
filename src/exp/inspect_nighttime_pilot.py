#!/usr/bin/env python3
"""Inspect six TIFFs and copy a geographic pilot window using standard Python.

Supports the uncompressed, single-band, float32, strip- or tile-organized source TIFFs.
Global rasters are inflated as streams and never extracted to disk. The copied
pixel values remain on the native raster grid; this is not 1 km aggregation.
"""
import csv
import json
import math
import statistics
import struct
import zipfile
from pathlib import Path
from audit_source_archives import tiff_metadata

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-organization'


def main():
    summaries=[]
    metadata=[]
    for path in sorted((ROOT/'data/raw/nighttime_lights').rglob('*.zip')):
        year=path.parent.name
        with zipfile.ZipFile(path) as z:
            member=next(n for n in z.namelist() if n.endswith('.tif'))
            with z.open(member) as f:
                header=f.read(2)
                f.seek(0)
                cache=OUT/'nighttime-pilot'/f'{year}_tiff_index.json'
                cache.parent.mkdir(parents=True,exist_ok=True)
                prior=OUT/'tables'/f'{year}_tiff_internal_metadata.json'
                details=json.loads(cache.read_text()) if cache.exists() else json.loads(prior.read_text()) if prior.exists() else tiff_metadata(f,full=True)
                if not cache.exists():cache.write_text(json.dumps(details)+'\n')
                tags=details['tags']
                details['tags']={k:v for k,v in tags.items() if k not in ('273','279','324','325')}
                details.update(year=year,archive=str(path.relative_to(ROOT)),member=member,
                               uncompressed_bytes=z.getinfo(member).file_size)
                metadata.append(details)
                if tags['259']!=[1] or tags['258']!=[32] or tags['339']!=[3] or tags['277']!=[1] or not ('273' in tags or '324' in tags):
                    raise ValueError(f'{year}: unsupported TIFF storage; use a geospatial reader')
                width,height=tags['256'][0],tags['257'][0]
                dx,dy=tags['33550'][:2]
                x0,y0=tags['33922'][3:5]
                if tags['33922'][:3]!=[0.0,0.0,0.0]:raise ValueError('Nonzero tiepoint origin')
                keys=tags['34735']
                epsg=next(keys[i+3] for i in range(4,len(keys),4) if keys[i]==2048)
                pixel=next(keys[i+3] for i in range(4,len(keys),4) if keys[i]==1025)
                if epsg!=4326 or pixel!=1:raise ValueError('Unexpected CRS or raster origin convention')
                c0=max(0,math.floor((130-x0)/dx));c1=min(width,math.ceil((131-x0)/dx))
                r0=max(0,math.floor((y0-34)/dy));r1=min(height,math.ceil((y0-100/3)/dy))
                nodata=float(tags['42113']) if '42113' in tags else None
                values=[];zero=negative=invalid=0
                copied=[]
                order='<' if header==b'II' else '>'
                if '273' in tags:
                    rows_per_strip=tags['278'][0]
                    offsets=tags['273']
                    for row in range(r0,r1):
                        offset=offsets[row//rows_per_strip]+((row%rows_per_strip)*width+c0)*4
                        f.seek(offset)
                        raw=f.read((c1-c0)*4)
                        pixels=struct.unpack(order+'f'*(c1-c0),raw)
                        copied.extend((row,col,value) for col,value in enumerate(pixels,c0))
                else:
                    tw,th=tags['322'][0],tags['323'][0]
                    across=math.ceil(width/tw)
                    selected=[]
                    for tr in range(r0//th,(r1-1)//th+1):
                        for tc in range(c0//tw,(c1-1)//tw+1):
                            index=tr*across+tc
                            selected.append((tags['324'][index],tags['325'][index],tr,tc))
                    for offset,size,tr,tc in sorted(selected):
                        f.seek(offset)
                        block=struct.unpack(order+'f'*(tw*th),f.read(size))
                        for row in range(max(r0,tr*th),min(r1,(tr+1)*th)):
                            for col in range(max(c0,tc*tw),min(c1,(tc+1)*tw)):
                                copied.append((row,col,block[(row-tr*th)*tw+col-tc*tw]))
                target=OUT/'nighttime-pilot'/f'{year}_native_pixels.csv'
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('w',newline='') as dest:
                    writer=csv.writer(dest);writer.writerow(['raster_row','raster_column','source_radiance'])
                    for row,col,value in sorted(copied):
                        writer.writerow([row,col,repr(value)])
                        if not math.isfinite(value) or (nodata is not None and value==nodata):invalid+=1
                        else:
                            values.append(value);zero+=int(value==0);negative+=int(value<0)
                summaries.append(dict(year=year,epsg=epsg,width=width,height=height,pixel_width_degrees=dx,pixel_height_degrees=dy,
                                      west=x0,north=y0,pilot_rows=r1-r0,pilot_columns=c1-c0,finite_non_nodata_pixels=len(values),zero_pixels=zero,negative_pixels=negative,invalid_pixels=invalid,
                                      declared_nodata=nodata,minimum=min(values),median=statistics.median(values),maximum=max(values)))
                print(f'{year}: native pilot {r1-r0}x{c1-c0}; EPSG={epsg}; spacing={dx}; invalid={invalid}',flush=True)
        (OUT/'tables/nighttime_raster_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        with (OUT/'tables/nighttime_pilot_summary.csv').open('w',newline='') as dest:
            writer=csv.DictWriter(dest,list(summaries[0]));writer.writeheader();writer.writerows(summaries)


if __name__=='__main__':main()
