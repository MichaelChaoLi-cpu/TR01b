#!/usr/bin/env python3
"""Regional and Prefecture Road Associations.

Plan: two forest panels comparing baseline and extended road coefficients.
Framework: AnaSOP Sections 5-7, same-sample original-scale pooled OLS,
mesh-clustered CR1 and individual normal 95% confidence intervals.
Run locally: uv run python src/analyses/figure_regional_and_prefecture_road_associations.py
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from statistics import NormalDist

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tr01b-matplotlib-formal")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet"
SOURCE = ROOT / "data/exp/land-cover-poi-extension"
OUT = ROOT / "data/results/figures/Figure_regional_and_prefecture_road_associations.png"
AUDIT = ROOT / "data/exp/figure-table-generation/regional-and-prefecture-road-associations"
REGION_ORDER = ["Hokkaido", "Tohoku", "Kanto", "Hokuriku-Shinetsu", "Chubu",
                "Kinki", "Chugoku", "Shikoku", "Kyushu"]
MODELS = [("baseline_same_sample", "Baseline: roads + population", "#0072B2", "o", -.16),
          ("extended", "Extended: + land cover and facilities", "#D55E00", "D", .16)]
DPI = 600


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_estimates(family: str, membership: pd.DataFrame) -> list[dict]:
    """Verify membership and saved uncertainty without rerunning the estimators."""
    source = json.loads((SOURCE / f"{family}_validation.json").read_text())
    assert source["status"] == "passed" and source["family"] == family
    entries = source["results"]
    assert len(entries) == {"regional": 9, "prefecture": 47}[family]
    columns = ["Region"] if family == "regional" else ["Prefecture Code", "Prefecture"]
    expected = membership.groupby(columns, sort=True).agg(
        observations=("Mesh Code", "size"), meshes=("Mesh Code", "nunique"))
    assert len(expected) == len(entries)
    csv = pd.read_csv(SOURCE / f"{family}_coefficients.csv")
    road_csv = csv.loc[csv["variable"].eq("Road Length Density")]
    rows = []
    z = NormalDist().inv_cdf(.975)
    for item in entries:
        base, extended = item["baseline_same_sample"], item["extended"]
        group = base["group"]
        assert group == extended["group"]
        key = group[0] if family == "regional" else tuple(group)
        counts = expected.loc[key]
        label = group[-1]
        row = {"name": label, "code": group[0] if family == "prefecture" else None,
               "meshes": int(counts["meshes"]), "observations": int(counts["observations"]),
               "models": {}}
        for model, _, _, _, _ in MODELS:
            fit = item[model]
            assert fit["meshes"] == row["meshes"] and fit["observations"] == row["observations"]
            assert fit["observations"] == 5 * fit["meshes"]
            assert fit["parameters"] == (3 if model == "baseline_same_sample" else 14)
            if fit["status"] != "ok":
                assert model == "extended" and family == "prefecture"
                assert fit["reason"] == "constant_predictors" and fit["coefficients"] == []
                row["models"][model] = {"status": "unavailable", "reason": fit["reason"],
                                         "constant_predictors": fit["constant_predictors"]}
                continue
            assert fit["rank"] == fit["parameters"]
            terms = fit["coefficients"]
            road_index = next(i for i, c in enumerate(terms) if c["variable"] == "Road Length Density")
            road = terms[road_index]
            coef, se = road["coefficient"], road["clustered_standard_error"]
            low, high = road["confidence_lower"], road["confidence_upper"]
            assert np.isfinite([coef, se, low, high]).all() and se > 0
            np.testing.assert_allclose([low, high], [coef - z * se, coef + z * se], rtol=1e-12, atol=1e-14)
            np.testing.assert_allclose(se**2, fit["covariance"][road_index][road_index], rtol=1e-12)
            g, n, k = fit["meshes"], fit["observations"], fit["parameters"]
            np.testing.assert_allclose(fit["cr1_factor"], g / (g - 1) * (n - 1) / (n - k), rtol=1e-12)
            spec = "Baseline same sample" if model == "baseline_same_sample" else "Extended"
            reference = road_csv.loc[road_csv["Group"].eq(" / ".join(group)) & road_csv["Specification"].eq(spec)]
            assert len(reference) == 1
            np.testing.assert_allclose(reference[["coefficient", "clustered_standard_error", "confidence_lower", "confidence_upper"]].iloc[0],
                                       [coef, se, low, high], rtol=1e-12, atol=1e-14)
            row["models"][model] = {"status": "ok", "coefficient": coef, "standard_error": se,
                                     "lower_95": low, "upper_95": high}
        assert row["models"]["baseline_same_sample"]["status"] == "ok"
        rows.append(row)
    assert sum(row["meshes"] for row in rows) == 383386
    assert sum(row["observations"] for row in rows) == 1916930
    if family == "regional":
        assert set(row["name"] for row in rows) == set(REGION_ORDER)
        rows.sort(key=lambda row: REGION_ORDER.index(row["name"]))
    else:
        rows.sort(key=lambda row: row["code"])
        assert [row["code"] for row in rows] == [f"{i:02}" for i in range(1, 48)]
        unavailable = {row["name"]: row["models"]["extended"].get("constant_predictors")
                       for row in rows if row["models"]["extended"]["status"] != "ok"}
        assert unavailable == {"Tokyo": ["Cropland Mosaic Land Cover Share"], "Nara": ["Water Land Cover Share"]}
    return rows


def plot_panel(ax: plt.Axes, rows: list[dict], letter: str, level: str) -> int:
    for i in range(len(rows)):
        if i % 2 == 0:
            ax.axhspan(i - .5, i + .5, color="#f2f5f7", zorder=0)
    ax.axvline(0, color="#53616b", linestyle=(0, (4, 3)), linewidth=1, zorder=1)
    plotted = 0
    for model, _, color, marker, offset in MODELS:
        for i, row in enumerate(rows):
            estimate = row["models"][model]
            y = i + offset
            if estimate["status"] != "ok":
                # Place a text-only status in axes coordinates, never a false zero coefficient.
                ax.text(.67, y, "Extended unavailable", transform=ax.get_yaxis_transform(),
                        color=color, fontsize=8, va="center")
                continue
            beta = estimate["coefficient"]
            ax.errorbar(beta, y, xerr=np.array([[beta - estimate["lower_95"]],
                                              [estimate["upper_95"] - beta]]),
                        fmt=marker, color=color, markersize=4, capsize=2.2,
                        elinewidth=1.05, markeredgewidth=.8, zorder=3)
            plotted += 1
    ax.set_yticks(np.arange(len(rows)), labels=[row["name"] for row in rows], fontsize=9)
    ax.set_ylim(len(rows) - .45, -.55)
    ax.set_xlim(-.15, .82)
    ax.xaxis.set_major_locator(MultipleLocator(.1))
    ax.tick_params(axis="x", labelsize=9)
    ax.tick_params(axis="y", length=0, pad=7)
    ax.grid(axis="x", color="#d9dfe4", linewidth=.65, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylabel(level, fontsize=10, labelpad=12)
    ax.set_xlabel("Road density coefficient (NTL radiance per km/km²)", fontsize=10, labelpad=8)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#9ba6af")
    ax.text(-.17, 1.025, letter, transform=ax.transAxes, fontsize=15, fontweight="bold", va="bottom")
    return plotted


def main() -> None:
    protected = [PANEL, SOURCE / "execution_contract.json", SOURCE / "pooled_validation.json"]
    protected += [SOURCE / f"{family}_{suffix}" for family in ["regional", "prefecture"]
                  for suffix in ["validation.json", "coefficients.csv"]]
    before = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    contract = json.loads((SOURCE / "execution_contract.json").read_text())
    validation = json.loads((SOURCE / "pooled_validation.json").read_text())
    assert contract["confirmed"] and contract["panel_sha256"] == sha(PANEL)
    assert not contract["effects"] and contract["original_units"] and contract["intercept"]
    assert contract["uncertainty"] == "Mesh-clustered CR1; normal 95 percent confidence intervals"
    assert validation["status"] == "passed" and validation["same_sample_baseline_comparisons"]
    assert validation["cluster_scores_verified"] and validation["exact_geographic_partitions_verified"]
    membership = pd.read_parquet(PANEL, columns=["Mesh Code", "Road Year", "Region", "Prefecture Code", "Prefecture"])
    assert len(membership) == 1916930
    assert sorted(membership["Road Year"].unique()) == [2002, 2003, 2004, 2010, 2024]
    for column in ["Mesh Code", "Prefecture Code"]:
        membership[column] = membership[column].astype(str)
    assert membership.groupby("Mesh Code").size().eq(5).all()
    assert membership.groupby("Mesh Code")[["Road Year", "Region", "Prefecture Code", "Prefecture"]].nunique().eq(
        pd.Series({"Road Year": 5, "Region": 1, "Prefecture Code": 1, "Prefecture": 1})).all().all()
    regions = read_estimates("regional", membership)
    prefectures = read_estimates("prefecture", membership)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 17), gridspec_kw={"height_ratios": [9, 47]}, facecolor="white")
    fig.subplots_adjust(left=.20, right=.97, bottom=.055, top=.96, hspace=.19)
    handles = [Line2D([], [], marker=marker, color=color, markersize=5, linewidth=1,
                      label=label) for _, label, color, marker, _ in MODELS]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.58, .997), frameon=False,
               ncol=2, fontsize=10, columnspacing=1.6)
    counts = [plot_panel(axes[0], regions, "a", "Region"),
              plot_panel(axes[1], prefectures, "b", "Prefecture")]
    assert counts == [18, 92]
    for ax in axes:
        for row in regions if ax is axes[0] else prefectures:
            for estimate in row["models"].values():
                if estimate["status"] == "ok":
                    assert ax.get_xlim()[0] < estimate["lower_95"] <= estimate["upper_95"] < ax.get_xlim()[1]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    assert before == {str(path.relative_to(ROOT)): sha(path) for path in protected}
    caption = (
        "Regional and prefecture road associations. Panel a reports nine transportation-statistics "
        "Regions in geographic order; panel b reports all forty-seven Prefectures in official code "
        "order. Circles denote the baseline original-scale pooled regression of Nighttime Radiance "
        "on Road Length Density and Population. Diamonds denote the extended model adding five "
        "annual land-cover shares, distances to railway stations and passenger airports, and four "
        "selected facility counts. Both specifications include an intercept and no fixed effects, "
        "and use identical area-specific samples from 383,386 meshes and 1,916,930 observations. "
        "Road/light periods are 2002, 2003, 2004, 2010 and 2024; matched population years are "
        "2000, 2005, 2005, 2010 and 2020. Bars are individual normal 95 percent intervals from "
        "mesh-clustered CR1 covariance estimates. Both panels use the same linear coefficient "
        "scale; no interval is truncated. The dashed vertical line marks zero. Tokyo and Nara "
        "retain their baseline estimates, but the extended vectors are unavailable under the "
        "complete-model rank rule: Cropland Mosaic Land Cover Share is constant zero in Tokyo, "
        "and Water Land Cover Share is constant zero in Nara. No zero coefficient is substituted. "
        "Intervals are unadjusted for multiple comparisons and are not formal tests of coefficient "
        "differences between areas. Estimates describe conditional associations, not causal road "
        "effects or excessive provision. Original road-source comparability, population timing "
        "and static facility limitations remain. PNG export is 600 dpi.\n"
    )
    OUT.with_suffix(".caption.md").write_text(caption)
    AUDIT.mkdir(parents=True, exist_ok=True)
    report = {"status": "generated_pending_visual_and_human_review",
              "title": "Regional and Prefecture Road Associations", "dpi": DPI,
              "framework": "AnaSOP Sections 5-7: same-sample pooled OLS, mesh-clustered CR1, normal 95% intervals",
              "region_rows": 9, "prefecture_rows": 47, "plotted_estimates": sum(counts),
              "extended_region_estimates": 9, "extended_prefecture_estimates": 45,
              "same_sample_membership_verified": True, "mesh_count": 383386, "observations": 1916930,
              "confidence_intervals_verified": True, "csv_json_agreement_verified": True,
              "source_panel_hash_matches_estimation_contract": True,
              "axis_limits": [-.15, .82], "same_linear_scale": True, "intervals_truncated": False,
              "has_figure_or_panel_titles": False, "panel_labels": ["a", "b"],
              "source_hashes": before, "source_files_unchanged": True, "figure_sha256": sha(OUT),
              "regions": regions, "prefectures": prefectures}
    (AUDIT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved: {OUT.relative_to(ROOT)}", flush=True)
    print("Verified: 9 regions; 47 prefectures; 110 coefficients and complete intervals; 2 unavailable extensions.", flush=True)


if __name__ == "__main__":
    main()
