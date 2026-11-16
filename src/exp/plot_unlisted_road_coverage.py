#!/usr/bin/env python3
"""Diagnostic map of omitted source blocks; not a manuscript result figure."""
from pathlib import Path
import math
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle
from osgeo import ogr, osr
import pandas as pd

from construct_road_pilot_trial import initialize_gdal, spatial_reference, WEST, SOUTH, DX, DY

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/pilot/coverage-investigation'


def parts(geometry):
    kind = ogr.GT_Flatten(geometry.GetGeometryType())
    if kind == ogr.wkbPolygon:
        yield geometry
    elif kind in [ogr.wkbMultiPolygon, ogr.wkbGeometryCollection]:
        for i in range(geometry.GetGeometryCount()):
            yield from parts(geometry.GetGeometryRef(i))


def shape_path(poly):
    vertices, codes = [], []
    for i in range(poly.GetGeometryCount()):
        points = [(x,y) for x,y,*_ in poly.GetGeometryRef(i).GetPoints()]
        if len(points) < 4:
            continue
        vertices.extend(points)
        codes.extend([MplPath.MOVETO] + [MplPath.LINETO]*(len(points)-2) + [MplPath.CLOSEPOLY])
    return MplPath(vertices, codes)


def main():
    initialize_gdal()
    frame = pd.read_csv(OUT / 'unlisted_mesh_diagnostics.csv', dtype={'mesh_code':'string', 'second_mesh_code':'string'})
    land_paths = []
    for archive_path in sorted((OUT / 'reference').glob('*.zip')):
        with zipfile.ZipFile(archive_path) as archive:
            name = next(n for n in archive.namelist() if n.endswith('.shp'))
        dataset = ogr.Open('/vsizip/' + str(archive_path) + '/' + name)
        layer = dataset.GetLayer()
        layer.SetSpatialFilterRect(129.99, 33.32, 131.01, 34.01)
        ref = layer.GetSpatialRef()
        ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(ref, spatial_reference(4612))
        for feature in layer:
            geometry = feature.GetGeometryRef().Clone()
            geometry.Transform(transform)
            for poly in parts(geometry):
                land_paths.append(shape_path(poly))
    fig, axes = plt.subplots(1,3,figsize=(13.8,5.4), sharex=True, sharey=True)
    for ax, year, label in zip(axes, [2002,2003,2010], ['2002', '2003 / 2004', '2010']):
        ax.set_facecolor('#f8fbfd')
        for path in land_paths:
            ax.add_patch(PathPatch(path, facecolor='#c9d4c9', edgecolor='none', rasterized=True))
        missing = frame[~frame[f'source_listed_{year}']]
        for block, group in missing.groupby('second_mesh_code'):
            row, col = int(group.grid_row.min()), int(group.grid_column.min())
            ax.add_patch(Rectangle((WEST+col*DX,SOUTH+row*DY), 10*DX,10*DY,
                                   facecolor='#76a9d3', edgecolor='#3e6f96', linewidth=.7, alpha=.5))
        land = missing[missing.aux_land_footprint_present_2024]
        ax.scatter(land.longitude, land.latitude, s=14, facecolor='#bd332d', edgecolor='white', linewidth=.3,zorder=4)
        ax.set_title(f'{label}\n{len(missing):,} unlisted cells; {len(land)} intersect current land',fontsize=10)
        ax.set_xlim(130,131);ax.set_ylim(SOUTH,34)
        ax.set_aspect(1/math.cos(math.radians(33.67)))
        ax.set_xlabel('Longitude')
        ax.tick_params(labelsize=8)
        ax.grid(alpha=.18,linewidth=.5)
    axes[0].set_ylabel('Latitude')
    axes[0].annotate('503041\nadded in 2003',xy=(130.23125,33.6875),xytext=(130.40,33.74),
                     fontsize=8,arrowprops=dict(arrowstyle='-',color='#343434'))
    axes[0].annotate('503060\nadded in 2010',xy=(130.03125,33.8625),xytext=(130.16,33.84),
                     fontsize=8,arrowprops=dict(arrowstyle='-',color='#343434'))
    axes[2].annotate('Two small land intersections\nin persistent omitted blocks',xy=(130.48125,33.92083),xytext=(130.58,33.83),
                     fontsize=8,arrowprops=dict(arrowstyle='-',color='#343434'))
    legend = [Rectangle((0,0),1,1,facecolor='#c9d4c9',label='2024 administrative / coastline footprint'),
              Rectangle((0,0),1,1,facecolor='#76a9d3',alpha=.5,label='Entire second-order block absent from source'),
              plt.Line2D([0],[0],marker='o',color='none',markerfacecolor='#bd332d',markersize=5,label='Unlisted cell intersects current land')]
    fig.legend(handles=legend,loc='lower center',bbox_to_anchor=(.5,.075),ncol=3,fontsize=8,frameon=False)
    fig.suptitle('Original road-file coverage: complete blocks omitted, not isolated parser losses',fontsize=13,y=.98)
    fig.text(.5,.035,'Primary mesh 5030. Current land is a diagnostic reference, not a historical coastline. Unknown rows are outside this audit.',
             ha='center',fontsize=8,color='#505050')
    fig.subplots_adjust(left=.06,right=.985,top=.84,bottom=.20,wspace=.12)
    fig.savefig(OUT / 'unlisted_road_coverage.png',dpi=180)
    plt.close(fig)
    print(OUT / 'unlisted_road_coverage.png')


if __name__ == '__main__':
    main()
