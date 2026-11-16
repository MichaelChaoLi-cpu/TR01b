#!/usr/bin/env python3
"""Local Road Associations across Japan.

Plan: independent main-text coefficient map, with island insets. The companion
appendix support figure calls the same renderer with mode="support".
Framework: AnaSOP Sections 5-7, extended UMD geographically weighted pooled
regression, water reference, fixed-distance bisquare, selected 5 km bandwidth.
This script reads verified results; it neither estimates nor changes source data.
Run locally: uv run python src/analyses/figure_local_road_associations_across_japan.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tr01b-matplotlib-formal")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from shapely.geometry import shape

from administrative_association_map_helpers import (
    ROOT, SOURCE, PANEL, OCEAN, UNAVAILABLE, MAP_COLORS,
    boundaries, polygon_patch, polygons, sha,
)
from gwpr_twoways import mesh_centroids

OUT = ROOT / "data/results/figures/Figure_local_road_associations_across_japan.png"
AUDIT = ROOT / "data/exp/figure-table-generation/local-road-associations-across-japan"
SUPPORT_COLORS = ["#216b65", "#e69f00", UNAVAILABLE]


def mesh_vertices(latitude, longitude):
    vertices = np.empty((len(latitude), 4, 2))
    vertices[:, :, 0] = longitude[:, None] + np.array([-1, 1, 1, -1])[None, :] / 160
    vertices[:, :, 1] = latitude[:, None] + np.array([-1, -1, 1, 1])[None, :] / 240
    return vertices


def draw_map(ax, mode, vertices, good, low, beta, groups, context, cmap, norm):
    axes = [ax, ax.inset_axes([.015, .66, .31, .23]), ax.inset_axes([.76, .02, .22, .24])]
    counts = {}
    for view, group in zip(axes, groups):
        xlim, ylim, ref, mask, name = group
        view.set_xlim(xlim); view.set_ylim(ylim)
        view.set_aspect(1 / np.cos(np.deg2rad(ref)))
        view.set_facecolor(OCEAN)
        for parts in context:
            visible = []
            for poly in parts:
                xmin, ymin, xmax, ymax = poly.bounds
                if xmax >= xlim[0] and xmin <= xlim[1] and ymax >= ylim[0] and ymin <= ylim[1]:
                    visible.append(poly)
            if visible:
                # Combine unchanged display polygons into one compound path per
                # prefecture rather than thousands of separate tiny patches.
                view.add_patch(polygon_patch(visible, "#f0f0f0"))
        if mode == "coefficient":
            view.add_collection(PolyCollection(vertices[mask & good], facecolors=cmap(norm(beta[mask & good])),
                                               edgecolors="none", antialiased=False, zorder=3))
            view.add_collection(PolyCollection(vertices[mask & ~good], facecolors=UNAVAILABLE,
                                               edgecolors="none", antialiased=False, zorder=3))
        else:
            for selected, color in zip([good & ~low, good & low, ~good], SUPPORT_COLORS):
                view.add_collection(PolyCollection(vertices[mask & selected], facecolors=color,
                                                   edgecolors="none", antialiased=False, zorder=3))
        view.set_axisbelow(False)
        view.grid(True, color="#687987", linewidth=.45, alpha=.45, linestyle=(0, (2, 3)))
        view.tick_params(labelsize=8, length=2)
        for spine in view.spines.values():
            spine.set_color("#b8bec5"); spine.set_linewidth(.6)
        if view is not ax:
            view.xaxis.set_major_locator(MaxNLocator(2)); view.yaxis.set_major_locator(MaxNLocator(2))
            view.tick_params(labelsize=6, pad=1)
        assert np.all(vertices[mask, :, 0] >= xlim[0]) and np.all(vertices[mask, :, 0] <= xlim[1])
        assert np.all(vertices[mask, :, 1] >= ylim[0]) and np.all(vertices[mask, :, 1] <= ylim[1])
        counts[name] = int(mask.sum())
    ax.set_xticks([130, 135, 140, 145]); ax.set_yticks([30, 35, 40, 45])
    ax.set_xlabel("Longitude (°E)", fontsize=10); ax.set_ylabel("Latitude (°N)", fontsize=10)
    return counts


def main(mode="coefficient"):
    assert mode in ["coefficient", "support"]
    title = "Local Road Associations across Japan" if mode == "coefficient" else "Local Road Association Estimation Support"
    placement = "main_text" if mode == "coefficient" else "appendix"
    slug = "local_road_associations_across_japan" if mode == "coefficient" else "local_road_association_estimation_support"
    output = ROOT / f"data/results/figures/Figure_{slug}.png"
    audit = ROOT / f"data/exp/figure-table-generation/{slug.replace('_', '-')}"
    active_path = SOURCE / "active_local_result.json"
    active = json.loads(active_path.read_text())
    source, validation_path = ROOT / active["output"], ROOT / active["validation"]
    contract_path = SOURCE / "execution_contract.json"
    protected = [source, validation_path, active_path, contract_path, PANEL]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    fit = json.loads(validation_path.read_text())
    contract = json.loads(contract_path.read_text())
    assert fit["status"] == "passed" and fit["classification"] == contract["classification"] == "UMD"
    assert active["bandwidth_km"] == fit["bandwidth_km"] == 5
    assert fit["output_sha256"] == sha(source) and fit["input_sha256"] == sha(PANEL)
    assert not contract["effects"] and contract["land_cover_reference"] == "Water Land Cover Share"
    data = pd.read_parquet(source)
    assert len(data) == fit["meshes"] == 383386 and data["Mesh Code"].is_unique
    codes = data["Mesh Code"].astype(str).to_numpy()
    cohort = pd.read_parquet(PANEL, columns=["Mesh Code"])["Mesh Code"].astype(str).unique()
    assert set(codes) == set(cohort)
    lat, lon = data["Latitude"].to_numpy(), data["Longitude"].to_numpy()
    np.testing.assert_allclose(mesh_centroids(codes), np.column_stack([lat, lon]), atol=1e-12)
    good = data["Fit Status"].eq("ok").to_numpy()
    low = data["Below 30 Observations"].to_numpy()
    beta = data["Road Density Coefficient"].to_numpy()
    assert np.isfinite(beta[good]).all() and np.isnan(beta[~good]).all()
    assert int(good.sum()) == fit["estimable_meshes"] == 357316
    assert int((~good).sum()) == fit["failed_meshes"] == 26070
    assert int((good & low).sum()) == fit["estimable_below_30_meshes"] == 24
    assert np.array_equal(low, data["Local Observations"].to_numpy() < 30)
    assert int((beta[good] == 0).sum()) == fit["road_zero_meshes"] == 9936
    vertices = mesh_vertices(lat, lon)
    np.testing.assert_allclose(vertices[:, :, 0].max(1)-vertices[:, :, 0].min(1), 1/80, atol=1e-12)
    np.testing.assert_allclose(vertices[:, :, 1].max(1)-vertices[:, :, 1].min(1), 1/120, atol=1e-12)
    absolute_p98 = float(np.quantile(abs(beta[good]), .98))
    # Round the existing percentile display rule upwards to readable 0.05 increments.
    limit = float(np.ceil(absolute_p98 / .05) * .05)
    cmap = LinearSegmentedColormap.from_list("blue_green_white_yellow_red", MAP_COLORS, N=1025)
    norm = Normalize(-limit, limit, clip=True)
    np.testing.assert_allclose(cmap(norm(0)), [1, 1, 1, 1])
    groups = [((128., 146.5), (29.95, 46.), 36, lat >= 30, "Main islands"),
              ((122.5, 132.), (23.7, 30.15), 27, (lat < 30) & (lon < 135), "Southwest islands"),
              ((140.9, 142.65), (24.5, 27.5), 26, (lat < 30) & (lon >= 135), "Ogasawara islands")]
    assert np.all(np.stack([g[3] for g in groups]).sum(0) == 1)
    cache, boundary_hashes = boundaries()
    context = [list(polygons(shape(geo))) for geo in cache["prefectures"].values()]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig = plt.figure(figsize=(10, 12), facecolor="white")
    height = .86 * 10 / 12 * (46-29.95) / (146.5-128) / np.cos(np.deg2rad(36))
    ax = fig.add_axes([.10, .96-height, .86, height])
    counts = [draw_map(ax, mode, vertices, good, low, beta, groups, context, cmap, norm)]
    assert sum(counts[0].values()) == len(data)
    if mode == "coefficient":
        cax = ax.inset_axes([.05, -.13, .90, .027])
        bar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal", extend="both")
        bar.set_ticks([-limit, -limit/2, 0, limit/2, limit])
        bar.set_label("Extended local road density coefficient", fontsize=10, labelpad=5)
        bar.ax.tick_params(labelsize=9)
        handles = [Patch(facecolor=UNAVAILABLE, label="Not estimable (26,070 meshes)")]
    else:
        handles = [Patch(facecolor=c, label=label) for c, label in zip(SUPPORT_COLORS, [
            "Estimable: ≥30 records (357,292 meshes)", "Estimable: <30 records (24 meshes)",
            "Not estimable (26,070 meshes)"])]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(.50, -.065),
              frameon=False, fontsize=10, ncol=1)
    output.parent.mkdir(parents=True, exist_ok=True); audit.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=600, facecolor="white")
    fig.savefig(audit / "preview.png", dpi=100, facecolor="white")
    plt.close(fig)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert all(sha(ROOT / name) == digest for name, digest in boundary_hashes.items())
    clipped = int((abs(beta[good]) > limit).sum())
    description = ("This independent main-text figure shows the extended geographically weighted pooled road-density coefficient surface. "
                   if mode == "coefficient" else
                   "This independent appendix figure documents estimation support for the extended geographically weighted pooled road-density coefficient surface shown in Local Road Associations across Japan. ")
    note = (f"{title}. " + description + "The coefficient is conditional on Population, five annual UMD land-cover shares and six selected static facility/accessibility "
        "controls. Water is the omitted land-cover reference. UMD classes 6-10 form Shrublands and Grasslands and class 15 is "
        "Barren. Constant or redundant nuisance controls are omitted while retaining their column space; road and population "
        "must remain identifiable. An intercept is included; no fixed effects are included. Nighttime Radiance proxies broader "
        "economic activity. The five road/light periods are 2002, 2003, 2004, 2010 and 2024, with census matches 2000, 2005, "
        "2005, 2010 and 2020. Coefficients have radiance units (nW/cm2/sr) per km/km2 of road density. "
        "The 5 km fixed-distance bisquare kernel uses great-circle centroid distances. Bandwidth selection used whole-mesh "
        "holdout on identical estimable validation support: 985 of 1,282 sampled centers, representing 75.25 percent of tile "
        "expansion weight. This is an approximate optimum conditional on that support, not a verified national optimum. "
        "Final fits include the focal mesh. All 383,386 complete-case focal meshes appear in this figure: 357,316 estimable "
        "and 26,070 non-estimable. Gray marks non-estimable fits, not zero coefficients. Pale blue denotes ocean; "
        "light gray land is display context without a model estimate. Mesh rectangles are "
        "1/120 degree latitude by 1/80 degree longitude, with no interpolation or additional land mask. Southwest and "
        "Ogasawara insets use separate scales. Four original-source Minamitorishima meshes lack land cover and are absent "
        "from this common estimation cohort; their source rows remain retained. "
        "Of the unavailable fits, 23,837 have "
        "constant mandatory road or population terms and 2,233 have an unidentifiable retained design. No local uncertainty "
        "or significance shading is provided. Associations neither identify causality nor prove excessive road provision. "
        "Export is 600 dpi.\n")
    if mode == "coefficient":
        note += (f"The continuous blue-green-white-yellow-red color scale is centered at zero and saturates at ±{limit:.2f}; "
            f"this rounds the 98th percentile of absolute coefficients ({absolute_p98:.6f}) upwards to a 0.05 increment. "
            f"Only colors saturate for {clipped:,} meshes; all numerical coefficients remain unchanged. The original "
            f"coefficient range is {beta[good].min():.6f} to {beta[good].max():.6f}. The 9,936 exact zero slopes appear white. "
            "The companion appendix figure, Local Road Association Estimation Support, documents neighborhood availability "
            "and retains the twenty-four estimable neighborhoods below thirty observation records.\n")
    else:
        note += ("Dark teal marks 357,292 estimable focal meshes with at least thirty observation records; orange marks "
            "the twenty-four estimable focal meshes below thirty records. All estimable neighborhoods, including exact zero "
            "road slopes, receive an estimable support color. The threshold counts pooled observation records, not independent "
            "meshes. With five records per mesh, thirty records correspond to six positive-weight meshes; it is not an "
            "effective-weight sample-size threshold. Gray marks all 26,070 unavailable fits; support colors encode neither "
            "road coefficient signs nor significance. Full numerical estimates are unchanged.\n")
    output.with_suffix(".caption.md").write_text(note)
    report = {"status": "generated_pending_visual_and_human_review", "human_review": "pending",
        "title": title, "placement": placement, "map_mode": mode, "classification": "UMD",
        "decision_id": contract["decision_id"], "bandwidth_km": 5, "effects": [], "dpi": 600,
        "presentation_decision_id": "MILI-D-20261011-025", "panel_labels": [], "has_figure_or_panel_titles": False,
        "figure_size_inches": [10, 12], "single_map": True,
        "geometry": "Standard third-order mesh rectangles", "meshes_per_panel": len(data),
        "all_meshes_inside_plot_limits": True, "one_geographic_view_per_mesh_verified": True,
        "panel_geographic_counts": counts, "estimable_meshes": int(good.sum()),
        "unavailable_meshes": int((~good).sum()), "support_counts": [int((good & ~low).sum()), int((good & low).sum()), int((~good).sum())],
        "zero_coefficient_meshes": int((beta[good] == 0).sum()),
        "zero_color": "#ffffff" if mode == "coefficient" else "Estimable support-category color",
        "below_30_estimates_retained": True, "coefficient_display_limit": limit,
        "absolute_coefficient_p98": absolute_p98, "color_saturated_meshes": clipped if mode == "coefficient" else 0,
        "coefficients_beyond_display_limit": clipped,
        "original_coefficient_range": [float(beta[good].min()), float(beta[good].max())],
        "coefficient_values_unmodified": True, "no_local_significance": True,
        "coefficient_color_scale_shown": mode == "coefficient", "support_legend_shown": mode == "support",
        "source_hashes": hashes, "boundary_source_hashes": boundary_hashes,
        "source_files_unchanged": True, "figure_sha256": sha(output)}
    (audit / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved: {output.relative_to(ROOT)}", flush=True)
    print(f"Verified: {len(data):,} meshes per panel; {int(good.sum()):,} estimable; source hashes unchanged.", flush=True)


if __name__ == "__main__":
    main()
