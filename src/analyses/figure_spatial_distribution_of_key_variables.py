#!/usr/bin/env python3
"""Spatial Distribution of Key Variables.

Plan: three five-period mesh means and selected source-location facility points.
Framework: AnaSOP Sections 5-7 descriptive foundation, approved extension cohort.
Run locally: uv run python src/analyses/figure_spatial_distribution_of_key_variables.py
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tr01b-matplotlib-formal")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import FuncNorm, LinearSegmentedColormap
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet"
LEDGERS = ROOT / "data/exp/data-preprocessing/static-facilities/facility-ledgers"
BOUNDARY = ROOT / "data/exp/gwpr-twoways/map_reference_lines.json"
OUT = ROOT / "data/results/figures/Figure_spatial_distribution_of_key_variables.png"
AUDIT = ROOT / "data/exp/figure-table-generation/spatial-distribution-of-key-variables"
DPI = 600  # Human-requested higher resolution overrides the skill's 150-dpi default.
CORE = ["Road Length Density", "Population", "Nighttime Radiance"]
FACILITIES = [
    ("medical", "Medical Facility Count", "Medical (2020)", "#0072B2"),
    ("schools", "School Facility Count", "Schools (2023)", "#D55E00"),
    ("visitor_facilities", "Visitor and Event Facility Count", "Visitor/event (2014)", "#CC0079"),
    ("logistics", "Logistics Facility Count", "Logistics (2013)", "#009E73"),
]
CONTINUOUS_COLORS = ["#2474B5", "#20A34A", "#FDE725", "#D73027"]
ZERO_COLOR = "#d8dee5"
OCEAN_COLOR = "#e6f2f8"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def mesh_geometry(codes: pd.Index) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Actual standard third-order mesh corners, not centroid interpolation."""
    c = codes.astype(str).astype("int64").to_numpy()
    lat = (c // 1000000) * 2 / 3 + (c // 1000 % 10) / 12 + (c // 10 % 10) / 120 + 1 / 240
    lon = 100 + (c // 10000 % 100) + (c // 100 % 10) / 8 + (c % 10) / 80 + 1 / 160
    vertices = np.empty((len(c), 4, 2))
    vertices[:, :, 0] = lon[:, None] + np.array([-1, 1, 1, -1]) / 160
    vertices[:, :, 1] = lat[:, None] + np.array([-1, -1, 1, 1]) / 240
    return lat, lon, vertices


def group_masks(lat: np.ndarray, lon: np.ndarray) -> list[np.ndarray]:
    return [lat >= 30, (lat < 30) & (lon < 135), (lat < 30) & (lon >= 135)]


def continuous_scale(values: np.ndarray, anchors: list[float]):
    """Continuous, monotonic display mapping; the underlying means stay unchanged.

    Unequal numerical intervals receive equal colorbar space to retain spatial
    detail in these strongly skewed variables. All ticks remain in original units.
    """
    assert np.isfinite(values).all() and (values >= 0).all()
    nodes = np.asarray(anchors, dtype=float)
    assert nodes[0] == 0 and np.all(np.diff(nodes) > 0) and values.max() <= nodes[-1]
    positions = np.linspace(0, 1, len(nodes))
    norm = FuncNorm((lambda x: np.interp(x, nodes, positions),
                     lambda y: np.interp(y, positions, nodes)),
                    vmin=0, vmax=nodes[-1])
    cmap = LinearSegmentedColormap.from_list("blue_green_yellow_red", CONTINUOUS_COLORS, N=1024)
    faces = cmap(norm(values))
    faces[values == 0] = matplotlib.colors.to_rgba(ZERO_COLOR)
    np.testing.assert_allclose(norm.inverse(norm(nodes)), nodes)
    labels = [f"{int(v):,}" if float(v).is_integer() else f"{v:g}" for v in anchors]
    labels[0] = "0+"
    return faces, cmap, norm, labels


def background(ax: plt.Axes, rings: list[np.ndarray], limits: tuple) -> None:
    xlim, ylim, reference_lat = limits
    visible = [v for v in rings if v[:, 0].max() >= xlim[0] and v[:, 0].min() <= xlim[1]
               and v[:, 1].max() >= ylim[0] and v[:, 1].min() <= ylim[1]]
    if visible:
        ax.add_collection(PolyCollection(visible, facecolors="#f2f0eb", edgecolors="#b9b9b5",
                                         linewidths=.20, zorder=0))
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect(1 / np.cos(np.deg2rad(reference_lat)))
    ax.set_facecolor(OCEAN_COLOR)
    ax.set_axisbelow(False)  # Keep graticules visible above mesh faces and POI points.
    ax.grid(True, color="#687987", linewidth=.45, alpha=.45, linestyle=(0, (2, 3)))
    ax.tick_params(labelsize=7, length=2.5, color="#999999")
    for spine in ax.spines.values():
        spine.set_color("#b8bec5")
        spine.set_linewidth(.6)


def main() -> None:
    protected = [PANEL, BOUNDARY] + [LEDGERS / f"{kind}_allocated_facilities.parquet" for kind, *_ in FACILITIES]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    columns = ["Mesh Code", "Road Year", "Population Year", *CORE] + [p[1] for p in FACILITIES]
    panel = pd.read_parquet(PANEL, columns=columns)
    panel["Mesh Code"] = panel["Mesh Code"].astype(str)
    assert len(panel) == 1916930
    assert panel.groupby("Mesh Code").size().eq(5).all()
    assert sorted(panel["Road Year"].unique()) == [2002, 2003, 2004, 2010, 2024]
    pairs = panel[["Road Year", "Population Year"]].drop_duplicates().sort_values("Road Year")
    assert pairs["Population Year"].tolist() == [2000, 2005, 2005, 2010, 2020]
    means = panel.groupby("Mesh Code", sort=True)[CORE].mean()
    latest = panel.loc[panel["Road Year"].eq(2024)].set_index("Mesh Code").reindex(means.index)
    assert len(means) == 383386 and means.notna().all().all()
    lat, lon, vertices = mesh_geometry(means.index)
    masks = group_masks(lat, lon)
    assert np.stack(masks).sum(axis=0).min() == np.stack(masks).sum(axis=0).max() == 1
    assert np.allclose(vertices[:, :, 0].max(1) - vertices[:, :, 0].min(1), 1 / 80)
    assert np.allclose(vertices[:, :, 1].max(1) - vertices[:, :, 1].min(1), 1 / 120)

    points = []
    counts = {}
    for kind, count_column, label, color in FACILITIES:
        frame = pd.read_parquet(LEDGERS / f"{kind}_allocated_facilities.parquet",
                                columns=["Mesh Code", "Longitude", "Latitude", "source_edition"])
        frame["Mesh Code"] = frame["Mesh Code"].astype(str)
        source_records = len(frame)
        frame = frame.loc[frame["Mesh Code"].isin(means.index)].copy()
        observed = frame["Mesh Code"].value_counts().reindex(means.index, fill_value=0)
        np.testing.assert_array_equal(observed.to_numpy(), latest[count_column].to_numpy())
        assert np.isfinite(frame[["Longitude", "Latitude"]].to_numpy()).all()
        points.append((frame, label, color))
        counts[kind] = {"source_records": source_records, "plotted_records": len(frame),
                        "outside_analytical_meshes": source_records - len(frame),
                        "source_years": sorted(int(x) for x in frame["source_edition"].unique()),
                        "mesh_count_agreement": True}

    boundary = json.loads(BOUNDARY.read_text())
    rings = [np.asarray(ring, dtype=float) for ring in boundary["lines"]]
    rings = [v for v in rings if len(v) >= 3 and np.isfinite(v).all()]
    # Identical extents and inset geometry in all four panels; retained islands are not dropped.
    limits = [((128.0, 146.5), (30.0, 46.0), 36),
              ((122.5, 132.0), (23.7, 30.15), 27),
              ((140.9, 142.65), (24.5, 27.5), 26)]
    positions = [[.018, .61, .30, .25], [.70, .018, .23, .24]]
    for mask, (xlim, ylim, _) in zip(masks, limits):
        assert np.all(vertices[mask, :, 0] >= xlim[0]) and np.all(vertices[mask, :, 0] <= xlim[1])
        assert np.all(vertices[mask, :, 1] >= ylim[0]) and np.all(vertices[mask, :, 1] <= ylim[1])

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(16, 16), facecolor="white")
    fig.subplots_adjust(left=.045, right=.985, top=.97, bottom=.065, hspace=.23, wspace=.16)
    schemes = [("Road Length Density", "Mean road density (km/km²)", [0, 1, 2, 3, 5, 40]),
               ("Population", "Mean population (persons/mesh)", [0, 10, 50, 150, 500, 32000]),
               ("Nighttime Radiance", "Mean NTL radiance (nW/cm²/sr)", [0, .01, .1, 1, 5, 170])]
    display_scales = {}
    for j, (letter, ax) in enumerate(zip("abcd", axes.flat)):
        map_axes = [ax] + [ax.inset_axes(pos) for pos in positions]
        for k, (map_ax, lim) in enumerate(zip(map_axes, limits)):
            background(map_ax, rings, lim)
            if k == 0:
                map_ax.set_xticks([130, 135, 140, 145])
                map_ax.set_yticks([30, 35, 40, 45])
                map_ax.set_xlabel("Longitude (°E)", fontsize=8)
                map_ax.set_ylabel("Latitude (°N)", fontsize=8)
            else:
                map_ax.xaxis.set_major_locator(MaxNLocator(2))
                map_ax.yaxis.set_major_locator(MaxNLocator(2))
                map_ax.tick_params(labelsize=6, pad=1)
        ax.text(-.065, 1.045, letter, transform=ax.transAxes, fontsize=15,
                fontweight="bold", va="top")
        if j < 3:
            name, unit_label, anchors = schemes[j]
            values = means[name].to_numpy()
            faces, cmap, norm, labels = continuous_scale(values, anchors)
            for map_ax, mask in zip(map_axes, masks):
                map_ax.add_collection(PolyCollection(vertices[mask], facecolors=faces[mask],
                                                     edgecolors="none", linewidths=0, zorder=2))
            cax = ax.inset_axes([.02, -.105, .96, .023])
            cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
            cb.set_ticks(anchors, labels=labels)
            cb.ax.tick_params(labelsize=7, length=0, pad=3)
            cb.set_label(unit_label, fontsize=9, labelpad=5)
            cb.outline.set_linewidth(.5)
            ax.legend(handles=[Patch(facecolor=ZERO_COLOR, label="Zero")],
                      loc="upper left", bbox_to_anchor=(.02, -.04), frameon=False,
                      fontsize=8, borderaxespad=0)
            display_scales[name] = {"continuous_mapping": "Piecewise linear between equally spaced color anchors",
                                   "value_anchors": anchors,
                                   "normalized_color_positions": np.linspace(0, 1, len(anchors)).tolist(),
                                   "zero_meshes": int((values == 0).sum()),
                                   "minimum": float(values.min()), "maximum": float(values.max())}
        else:
            for frame, label, color in points:
                point_masks = group_masks(frame["Latitude"].to_numpy(), frame["Longitude"].to_numpy())
                for map_ax, mask in zip(map_axes, point_masks):
                    here = frame.loc[mask]
                    map_ax.scatter(here["Longitude"], here["Latitude"], s=.65, color=color,
                                   alpha=.85, linewidths=0, rasterized=True, zorder=2)
            handles = [Line2D([], [], linestyle="none", marker="o", markersize=4,
                              color=color, label=label) for _, label, color in points]
            ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, -.045),
                      frameon=False, ncol=2, fontsize=9, columnspacing=1.8, handletextpad=.5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    caption = (
        "Spatial distribution of key variables. Panels a-c show equal-weight means over the "
        "2002, 2003, 2004, 2010 and 2024 road/light observations: road length density, matched "
        "population and NTL radiance. Population snapshots are 2000, 2005, 2005, 2010 and 2020. "
        "These are observation means, not continuous annual averages. Actual standard mesh "
        "footprints are drawn without interpolation. Gray cells denote valid zero means; "
        "positive values use the same continuous blue-green-yellow-red palette, with a "
        "separate numerical scale and units for each variable. To show detail in the skewed "
        "distributions, color positions are piecewise-linear functions of the original values; "
        "successive labeled ticks occupy equal colorbar space. The scales are nonlinear overall, "
        "and no analytical values are transformed or clipped. The blue endpoint marked 0+ "
        "denotes the limit of positive values; exact zeros are gray. Road density and population "
        "ticks are integers; NTL retains fractional ticks for low radiance. Geographic gridlines are "
        "drawn in all main maps and insets; the PNG is exported at 600 dpi. "
        "Panel d draws the retained source-location records for medical "
        "facilities (2020), schools (2023), visitor/event facilities (2014) and logistics "
        "facilities (2013), using the accepted within-category selection and duplicate rules. "
        "Points are restricted to the same 383,386 analytical meshes, are not relocated or "
        "jittered, and can overlap. The facility display is not a comprehensive POI inventory "
        "or a cross-category count of unique institutions. Pale blue map backgrounds represent "
        "the ocean. Light land shading is geographic "
        "context outside the analytical footprints. Main-island, southwest and Ogasawara "
        "views have identical extents across panels; the island insets use separate scales. "
        "Four Minamitorishima meshes remain outside the approved extension because land cover "
        "is unavailable. Source road definitions and population timing remain as documented.\n"
    )
    OUT.with_suffix(".caption.md").write_text(caption)
    AUDIT.mkdir(parents=True, exist_ok=True)
    report = {"status": "generated_pending_visual_and_human_review", "title": "Spatial Distribution of Key Variables",
              "mesh_count": len(means), "source_observations": len(panel), "dpi": DPI,
              "longitude_latitude_gridlines": True,
              "display_mapping": "Continuous piecewise-linear color normalization; valid zero separate",
              "continuous_palette": CONTINUOUS_COLORS, "zero_color": ZERO_COLOR,
              "ocean_background_color": OCEAN_COLOR,
              "has_figure_or_panel_titles": False, "panel_labels": list("abcd"),
              "mesh_geometry": "Actual third-order rectangles, 1/80 degree longitude by 1/120 degree latitude",
              "map_mesh_counts": {key: int(mask.sum()) for key, mask in zip(["main", "southwest", "ogasawara"], masks)},
              "mean_missing_values": int(means.isna().sum().sum()), "display_scales": display_scales,
              "facility_colors": {kind: color for kind, _, _, color in FACILITIES}, "facility_point_alpha": .85,
              "facility_points": counts, "source_hashes": before, "source_files_unchanged": True,
              "analytical_values_unchanged": True, "source_points_not_jittered_or_relocated": True,
              "figure_sha256": sha(OUT), "source_population_matches": pairs.to_dict("records")}
    (AUDIT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved: {OUT.relative_to(ROOT)}", flush=True)
    print("Verified: 383,386 actual meshes; four point categories agree with their mesh counts.", flush=True)


if __name__ == "__main__":
    main()
