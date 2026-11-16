"""Shared, display-only utilities for the two administrative association figures."""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from statistics import NormalDist

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tr01b-matplotlib-formal")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from shapely import make_valid, union_all
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.geometry.polygon import orient

from figure_regional_and_prefecture_road_associations import (
    ROOT, MODELS, REGION_ORDER, sha, plot_panel,
)

SOURCE = ROOT / "data/exp/umd-four-layer"
PANEL = SOURCE / "inputs/model_panel.parquet"

REGION_PREFECTURES = {
    "Hokkaido": [1], "Tohoku": [2, 3, 4, 5, 6, 7],
    "Kanto": [8, 9, 10, 11, 12, 13, 14, 19],
    "Hokuriku-Shinetsu": [15, 16, 17, 20], "Chubu": [18, 21, 22, 23, 24],
    "Kinki": [25, 26, 27, 28, 29, 30], "Chugoku": [31, 32, 33, 34, 35],
    "Shikoku": [36, 37, 38, 39], "Kyushu": [40, 41, 42, 43, 44, 45, 46, 47],
}
MANIFEST = ROOT / "data/exp/data-preprocessing/regional/reference/manifest.json"
CACHE = ROOT / "data/exp/figure-table-generation/administrative-map-reference/display_boundaries.json"
LIMITS = [((128, 146.5), (30, 46), 36),
          ((122.5, 132), (23.7, 30.15), 27),
          ((140.9, 142.65), (24.5, 27.5), 26)]
MAP_RANGE = (-.25, .25)
MAP_COLORS = ["#2166ac", "#1a9850", "#ffffff", "#fee033", "#d73027"]
OCEAN = "#e6f2f8"
UNAVAILABLE = "#aaaeb3"
OVERLAPS = ROOT / "data/exp/data-preprocessing/expanded-analysis-geography/prefecture-overlap/mesh_prefecture_overlaps.csv"


def read_estimates(family, membership):
    """Read the verified UMD fits and verify retained-rank CR1 uncertainty."""
    delivery = json.loads((SOURCE / f"{family}_validation.json").read_text())
    assert delivery["status"] == "passed"
    columns = ["Region"] if family == "regional" else ["Prefecture Code", "Prefecture"]
    expected = membership.groupby(columns).agg(observations=("Mesh Code", "size"), meshes=("Mesh Code", "nunique"))
    csv = pd.read_csv(SOURCE / f"{family}_coefficients.csv")
    csv = csv.loc[csv["variable"].eq("Road Length Density")]
    rows, z = [], NormalDist().inv_cdf(.975)
    assert len(delivery["results"]) == len(expected) == (9 if family == "regional" else 47)
    for entry in delivery["results"]:
        group = entry["group"]
        code, name = (None, group) if family == "regional" else group.split(" / ", 1)
        counts = expected.loc[name if family == "regional" else (code, name)]
        row = {"name": name, "code": code, "meshes": int(counts.meshes),
               "observations": int(counts.observations), "models": {}}
        for model, _, _, _, _ in MODELS:
            fit = entry[model]
            assert fit["meshes"] == row["meshes"] and fit["observations"] == row["observations"] == 5 * row["meshes"]
            assert fit["status"] == "ok" and fit["rank"] == fit["parameters"] == len(fit["retained_terms"])
            term = next(t for t in fit["coefficients"] if t["variable"] == "Road Length Density")
            coef, se, low, high = [term[k] for k in ["coefficient", "clustered_standard_error", "confidence_lower", "confidence_upper"]]
            assert np.isfinite([coef, se, low, high]).all() and se > 0
            np.testing.assert_allclose([low, high], [coef-z*se, coef+z*se], rtol=1e-12, atol=1e-14)
            ix = fit["retained_terms"].index("Road Length Density")
            np.testing.assert_allclose(se**2, fit["covariance_retained"][ix][ix], rtol=1e-12)
            g, n, k = fit["meshes"], fit["observations"], fit["parameters"]
            np.testing.assert_allclose(fit["cr1_factor"], g/(g-1)*(n-1)/(n-k), rtol=1e-12)
            spec = "Baseline" if model == "baseline_same_sample" else "Extended"
            ref = csv.loc[csv.Group.eq(group) & csv.Specification.eq(spec)]
            assert len(ref) == 1
            np.testing.assert_allclose(ref[["coefficient", "clustered_standard_error", "confidence_lower", "confidence_upper"]].iloc[0],
                                       [coef, se, low, high], rtol=1e-12, atol=1e-14)
            row["models"][model] = {"status": "ok", "coefficient": coef, "standard_error": se,
                "lower_95": low, "upper_95": high, "retained_parameters": k,
                "omitted_constant_controls": fit["omitted_constant_controls"],
                "omitted_redundant_controls": fit["omitted_redundant_controls"]}
        rows.append(row)
    assert sum(r["meshes"] for r in rows) == 383386 and sum(r["observations"] for r in rows) == 1916930
    rows.sort(key=lambda r: REGION_ORDER.index(r["name"]) if family == "regional" else r["code"])
    return rows


def verify_boundary_allocation(membership):
    """Verify the known boundary difference using each level's own area rule."""
    lookup = {f"{code:02}": region for region, codes in REGION_PREFECTURES.items() for code in codes}
    meshes = membership.drop_duplicates("Mesh Code").copy()
    implied = meshes["Prefecture Code"].map(lookup)
    assert implied.notna().all()
    differing = meshes.loc[implied.ne(meshes["Region"])]
    assert differing["Mesh Code"].tolist() == ["55392391"]
    overlaps = pd.read_csv(OVERLAPS, dtype={"mesh_code": str, "prefecture_code": str})
    details = []
    for row in differing.itertuples(index=False, name=None):
        mesh, _, region, prefecture_code, prefecture = row
        areas = overlaps.loc[overlaps["mesh_code"].eq(mesh)].copy()
        assert len(areas) > 1 and areas["land_overlap_m2"].gt(0).all()
        largest_prefecture = areas.loc[areas["land_overlap_m2"].idxmax(), "prefecture_code"]
        areas["region"] = areas["prefecture_code"].map(lookup)
        regional_areas = areas.groupby("region")["land_overlap_m2"].sum()
        assert largest_prefecture == prefecture_code and regional_areas.idxmax() == region
        details.append({"mesh_code": mesh, "region": region, "prefecture": prefecture,
                        "prefecture_code": prefecture_code, "prefecture_implied_region": lookup[prefecture_code],
                        "region_overlap_m2": regional_areas.to_dict(),
                        "verified": "Independent largest-prefecture and largest-region area rules"})
    return details


def polygons(geometry):
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, (MultiPolygon, GeometryCollection)):
        for part in geometry.geoms:
            yield from polygons(part)


def boundaries():
    """Read official cached polygons; dissolve and simplify only their display copy."""
    manifest = json.loads(MANIFEST.read_text())
    assert len(manifest) == 47
    hashes = {entry["path"]: sha(ROOT / entry["path"]) for entry in manifest}
    assert all(hashes[entry["path"]] == entry["sha256"] for entry in manifest)
    assert sorted(entry["prefecture_code"] for entry in manifest) == [f"{i:02}" for i in range(1, 48)]
    if CACHE.exists():
        cache = json.loads(CACHE.read_text())
        assert cache["source_hashes"] == hashes
        return cache, hashes
    prefectures, metadata = {}, []
    for entry in manifest:
        with zipfile.ZipFile(ROOT / entry["path"]) as archive:
            member = next(name for name in archive.namelist() if name.endswith(".geojson") and "subprefecture" not in name)
            data = json.loads(archive.read(member))
            prj = next(name for name in archive.namelist() if name.endswith(".prj") and "subprefecture" not in name)
            wkt = archive.read(prj).decode()
            assert "JGD_2011" in wkt and 'UNIT["Degree"' in wkt
        assert data["type"] == "FeatureCollection"
        parts, repaired = [], 0
        for feature in data["features"]:
            if feature["geometry"] is None:
                continue
            geom = shape(feature["geometry"])
            if not geom.is_valid:
                geom = make_valid(geom)
                repaired += 1
            parts.extend(polygons(geom))
        merged = union_all(parts)
        assert not merged.is_empty and merged.is_valid
        xmin, ymin, xmax, ymax = merged.bounds
        assert 120 < xmin < xmax < 155 and 20 < ymin < ymax < 47
        prefectures[entry["prefecture_code"]] = merged
        metadata.append({"prefecture_code": entry["prefecture_code"], "source_features": len(data["features"]),
                         "invalid_features_repaired_for_display": repaired, "source_projection": wkt})
        print(f"Display boundary: {entry['prefecture_code']}; {len(parts):,} source polygon parts", flush=True)
    regions = {region: union_all([prefectures[f"{code:02}"] for code in codes])
               for region, codes in REGION_PREFECTURES.items()}
    tolerance = .005
    cache = {"source_hashes": hashes, "source_manifest_sha256": sha(MANIFEST),
             "boundary_date": "2024-01-01", "role": "Display-only administrative geometry; not an analytical mask",
             "simplification_degrees": tolerance, "source_crs": "JGD2011 geographic degrees",
             "metadata": metadata,
             "prefectures": {code: mapping(geom.simplify(tolerance, preserve_topology=True)) for code, geom in prefectures.items()},
             "regions": {region: mapping(geom.simplify(tolerance, preserve_topology=True)) for region, geom in regions.items()}}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, separators=(",", ":")) + "\n")
    assert all(sha(ROOT / name) == value for name, value in hashes.items())
    return cache, hashes


def polygon_patch(parts, color):
    # Opposite ring orientation preserves holes when the compound path is filled.
    vertices, codes = [], []
    for poly in parts:
        poly = orient(poly, sign=1)
        for ring in [poly.exterior, *poly.interiors]:
            coords = np.asarray(ring.coords)[:, :2]
            vertices.extend(coords)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(coords) - 2) + [MplPath.CLOSEPOLY])
    return PathPatch(MplPath(np.asarray(vertices), codes), facecolor=color,
                     edgecolor="#636d74", linewidth=.45, zorder=2)


def map_panel(ax, rows, family, cache):
    cmap = LinearSegmentedColormap.from_list("blue_green_white_yellow_red", MAP_COLORS, N=1025)
    norm = Normalize(*MAP_RANGE)
    np.testing.assert_allclose(cmap(norm(0)), [1, 1, 1, 1])
    area_key = "regions" if family == "regional" else "prefectures"
    map_axes = [ax, ax.inset_axes([.015, .66, .31, .23]), ax.inset_axes([.76, .02, .22, .24])]
    plotted = set()
    for map_ax, (xlim, ylim, reference_lat) in zip(map_axes, LIMITS):
        map_ax.set_xlim(xlim); map_ax.set_ylim(ylim)
        map_ax.set_aspect(1 / np.cos(np.deg2rad(reference_lat)))
        map_ax.set_facecolor(OCEAN)
        map_ax.set_axisbelow(False)
        map_ax.grid(True, color="#687987", linewidth=.45, alpha=.45, linestyle=(0, (2, 3)))
        map_ax.tick_params(labelsize=7, length=2)
        for spine in map_ax.spines.values():
            spine.set_color("#b8bec5"); spine.set_linewidth(.6)
        for row in rows:
            key = row["name"] if family == "regional" else row["code"]
            estimate = row["models"]["extended"]
            color = UNAVAILABLE if estimate["status"] != "ok" else cmap(norm(estimate["coefficient"]))
            if estimate["status"] == "ok":
                assert MAP_RANGE[0] <= estimate["coefficient"] <= MAP_RANGE[1]
            visible = []
            for poly in polygons(shape(cache[area_key][key])):
                xmin, ymin, xmax, ymax = poly.bounds
                if xmax < xlim[0] or xmin > xlim[1] or ymax < ylim[0] or ymin > ylim[1]:
                    continue
                visible.append(poly)
            if visible:
                map_ax.add_patch(polygon_patch(visible, color)); plotted.add(key)
    assert len(plotted) == len(rows)
    ax.set_xticks([130, 135, 140, 145]); ax.set_yticks([30, 35, 40, 45])
    ax.set_xlabel("Longitude (°E)", fontsize=9); ax.set_ylabel("Latitude (°N)", fontsize=9)
    for inset in map_axes[1:]:
        inset.xaxis.set_major_locator(MaxNLocator(2)); inset.yaxis.set_major_locator(MaxNLocator(2))
        inset.tick_params(labelsize=6, pad=1)
    ax.text(.015, 1.015, "b", transform=ax.transAxes, fontsize=15, fontweight="bold", va="bottom")
    cax = ax.inset_axes([.05, -.13, .90, .027])
    bar = ax.figure.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    bar.set_ticks([-.25, -.125, 0, .125, .25])
    bar.ax.tick_params(labelsize=8)
    bar.set_label("Extended road density coefficient", fontsize=9, labelpad=5)
    bar.outline.set_linewidth(.5)
    if any(row["models"]["extended"]["status"] != "ok" for row in rows):
        ax.legend(handles=[Patch(facecolor=UNAVAILABLE, edgecolor="#636d74", label="Extended unavailable")],
                  loc="upper left", bbox_to_anchor=(.03, -.045), frameon=False, fontsize=8)
    return len(plotted)


def connect_coefficients(ax, rows):
    """Connect paired estimates without implying inference on their difference."""
    offsets = {name: offset for name, _, _, _, offset in MODELS}
    connectors = []
    for i, row in enumerate(rows):
        baseline = row["models"]["baseline_same_sample"]
        extended = row["models"]["extended"]
        if baseline["status"] != "ok" or extended["status"] != "ok":
            continue
        x = [baseline["coefficient"], extended["coefficient"]]
        y = [i + offsets["baseline_same_sample"], i + offsets["extended"]]
        midpoint = (y[0] + y[1]) / 2
        vertices = [(x[0], y[0]), (x[0], midpoint), (x[1], midpoint), (x[1], y[1])]
        ax.plot(*zip(*vertices), color="#7c8790", linewidth=.9, linestyle=(0, (3, 2)),
                alpha=.8, zorder=2)
        connectors.append({"name": row["name"], "endpoints": list(zip(x, y)),
                           "vertices": vertices,
                           "extended_minus_baseline": x[1] - x[0]})
    return connectors


def generate(family: str, title: str, slug: str):
    protected = [PANEL, MANIFEST, OVERLAPS, SOURCE / "execution_contract.json", SOURCE / "pooled_validation.json"]
    protected += [SOURCE / f"{level}_{suffix}" for level in ["regional", "prefecture"]
                  for suffix in ["validation.json", "coefficients.csv"]]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    contract = json.loads((SOURCE / "execution_contract.json").read_text())
    validation = json.loads((SOURCE / "pooled_validation.json").read_text())
    assert contract["panel_sha256"] == sha(PANEL) and not contract["effects"]
    assert contract["confirmed"] and contract["original_units"] and contract["intercept"]
    assert validation["status"] == "passed" and validation["same_sample_verified"]
    membership = pd.read_parquet(PANEL, columns=["Mesh Code", "Road Year", "Region", "Prefecture Code", "Prefecture"])
    for col in ["Mesh Code", "Prefecture Code"]:
        membership[col] = membership[col].astype(str)
    assert membership.groupby("Mesh Code").size().eq(5).all()
    rows = read_estimates(family, membership)
    boundary_allocation = verify_boundary_allocation(membership)
    cache, boundary_hashes = boundaries()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    # Both figures use identical geometry. Compute height from the map's
    # geographic aspect so equal panel heights do not stretch Japan.
    fig = plt.figure(figsize=(18, 14), facecolor="white")
    map_width = .57
    (xlim, ylim, reference_lat) = LIMITS[0]
    height = map_width * 18 / 14 * (ylim[1]-ylim[0]) / (xlim[1]-xlim[0]) / np.cos(np.deg2rad(reference_lat))
    bottom = .94 - height
    forest = fig.add_axes([.12, bottom, .22, height])
    geographic = fig.add_axes([.41, bottom, map_width, height])
    ncoeff = plot_panel(forest, rows, "a", "Region" if family == "regional" else "Prefecture")
    connectors = connect_coefficients(forest, rows)
    assert len(connectors) == (9 if family == "regional" else 47)
    forest.set_xlim((-.08, .34) if family == "regional" else (-.15, .82))
    for row in rows:
        for estimate in row["models"].values():
            if estimate["status"] == "ok":
                assert forest.get_xlim()[0] < estimate["lower_95"] <= estimate["upper_95"] < forest.get_xlim()[1]
    forest.set_xlabel("Road density coefficient", fontsize=10)
    # Replace the reusable forest helper's label to match the map label height.
    for text in forest.texts:
        if text.get_text() == "a":
            text.set_position((.015, 1.015))
    handles = [Line2D([], [], marker=marker, color=color, markersize=5, linewidth=1, label=label)
               for _, label, color, marker, _ in MODELS]
    handles.append(Line2D([], [], color="#7c8790", linewidth=.9, linestyle=(0, (3, 2)),
                          label="Coefficient change"))
    legend_anchor = (.5, -.08)
    legend = forest.legend(handles=handles, loc="upper center", bbox_to_anchor=legend_anchor,
                           ncol=1, frameon=False, fontsize=10, borderaxespad=0)
    nareas = map_panel(geographic, rows, family, cache)
    fig.canvas.draw()
    forest_bounds = forest.get_position().bounds
    map_bounds = geographic.get_position().bounds
    np.testing.assert_allclose([forest_bounds[1], forest_bounds[3]], [map_bounds[1], map_bounds[3]], atol=1e-12)
    expected = 18 if family == "regional" else 94
    assert ncoeff == expected
    output = ROOT / f"data/results/figures/Figure_{slug}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the same canvas crop for both levels despite different label lengths.
    fig.savefig(output, dpi=600, facecolor="white")
    audit = ROOT / f"data/exp/figure-table-generation/{slug.replace('_', '-')}"
    audit.mkdir(parents=True, exist_ok=True)
    fig.savefig(audit / "preview.png", dpi=100, facecolor="white")
    plt.close(fig)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert all(sha(ROOT / name) == digest for name, digest in boundary_hashes.items())
    note = (f"{title}. Panel a compares baseline (circles) and extended (diamonds) original-scale pooled "
            "road-density coefficients, with Nighttime Radiance as the outcome, and individual normal "
            "95 percent intervals from mesh-clustered CR1 "
            "covariance using the actual retained parameter count. Baseline controls for Population; the extension adds the five selected annual UMD land-cover "
            "shares, railway/airport distances and four selected facility counts. Both include an intercept and "
            "no fixed effects, on identical area-specific samples from 383,386 meshes and 1,916,930 records. "
            "The five road/light periods are 2002, 2003, 2004, 2010 and 2024; census matches are 2000, 2005, "
            "2005, 2010 and 2020. Road coefficients have radiance units (nW/cm2/sr) per km/km2 of road density. "
            "Forest intervals are not truncated; the forest horizontal scale differs between the regional "
            "and prefecture figures to retain readability. Gray dashed stepped connectors have a horizontal "
            "segment centered between the two model point heights and vertical end segments joining their markers, "
            "showing the coefficient change after adding controls; "
            "they are not confidence intervals or significance tests of the change. Areas with unavailable "
            "extended fits have no connector. Panel b colors the extended coefficient "
            "over frozen 2024 official administrative polygons; regional polygons follow the accepted nine-region "
            "transportation-statistics grouping. Both administrative maps use the same continuous linear "
            "blue-green-white-yellow-red scale from -0.25 to 0.25, with white exactly at zero, "
            "without clipping coefficients. The three-item model and connector legend is stacked directly below panel a; the prefecture "
            "and regional figures use the same 18 by 14 inch canvas and panel geometry. Panel a is narrow and tall; "
            "panel b has approximately 2.59 times its plotting width. Both plotting panels have identical vertical "
            "lengths and aligned upper and lower edges. Map geometry retains its geographic aspect ratio. "
            "Fills represent area-level conditional slopes, not mesh-specific estimates or a statement "
            "of complete within-area sample coverage. Maps do not encode significance. Gray represents unavailable "
            "extended fits if any; all nine regional and all forty-seven prefecture extended fits are available in this UMD delivery, including Tokyo and Nara. "
            "Water is the omitted land-cover reference. The included UMD categories are Urban, Forest, Cropland, "
            "Shrublands and Grasslands (classes 6-10), and Barren (class 15). Constant or redundant added controls "
            "are omitted while retaining their nuisance column space; the road and population coefficients must remain identifiable. "
            "Nara omits constant Barren and redundant Shrublands and Grasslands; its road coefficient remains estimable. "
            "Display geometry is dissolved then simplified at 0.005 "
            "degrees; source geometry and analytical assignments are unchanged. Southwest and Ogasawara "
            "insets use separate scales; views follow the analytical map extents, and remote land outside these "
            "views is not shown. Pale blue denotes ocean. Intervals are unadjusted for multiple comparisons and "
            "are not formal between-area difference tests. Conditional associations do not establish causal "
            "effects or excessive provision. Export is 600 dpi.\n")
    output.with_suffix(".caption.md").write_text(note)
    audit = ROOT / f"data/exp/figure-table-generation/{slug.replace('_', '-')}"
    audit.mkdir(parents=True, exist_ok=True)
    report = {"status": "generated_pending_visual_and_human_review", "title": title,
              "decision_id": "MILI-D-20261011-020", "classification": "UMD", "water_reference": True,
              "human_review": "pending", "panel_labels": ["a", "b"], "dpi": 600,
              "presentation_revision_decision_id": "MILI-D-20261011-017",
              "legend_placement_decision_id": "MILI-D-20261011-021",
              "panel_layout_decision_id": "MILI-D-20261011-022",
              "prior_presentation_revision_decision_id": "MILI-D-20261011-016",
              "coefficient_connectors": connectors, "connector_count": len(connectors),
              "connector_style": "gray dashed centered horizontal step", "connectors_encode_difference_significance": False,
              "administrative_level": family, "areas": nareas, "forest_estimates": ncoeff,
              "map_specification": "Extended", "map_range": list(MAP_RANGE), "map_center": 0,
              "map_palette": MAP_COLORS, "zero_color_verified": "#ffffff", "model_legend_position": "below_panel_a",
              "legend_columns": 1, "legend_anchor_in_forest_axes": list(legend_anchor),
              "figure_size_inches": list(fig.get_size_inches()),
              "forest_panel_position": list(forest.get_position().bounds),
              "map_panel_position": list(geographic.get_position().bounds),
              "equal_rendered_panel_heights_verified": True,
              "aligned_panel_top_and_bottom_verified": True,
              "map_to_forest_width_ratio": map_bounds[2] / forest_bounds[2],
              "panel_height_inches": forest_bounds[3] * 14,
              "forest_axis_limits": list(forest.get_xlim()),
              "map_significance_shading": False, "no_coefficient_or_interval_clipping": True,
              "same_sample_membership_verified": True, "csv_json_uncertainty_agreement_verified": True,
              "independent_boundary_allocation_verified": boundary_allocation,
              "map_geometry": str(CACHE.relative_to(ROOT)), "map_geometry_sha256": sha(CACHE),
              "source_hashes": hashes, "boundary_source_hashes": boundary_hashes,
              "source_files_unchanged": True, "figure_sha256": sha(output),
              "rows": rows, "has_figure_or_panel_titles": False}
    (audit / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved: {output.relative_to(ROOT)}", flush=True)
    print(f"Verified: {nareas} mapped administrative areas; {ncoeff} forest estimates; input hashes unchanged.", flush=True)
