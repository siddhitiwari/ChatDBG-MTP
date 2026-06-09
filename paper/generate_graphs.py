"""
Generate evaluation graphs for the ChatDBG-MTP research paper.

Usage:
    pip install matplotlib numpy pandas seaborn
    python paper/generate_graphs.py                        # uses sample_results.json
    python paper/generate_graphs.py --results eval_results.json  # uses real eval output
"""
import argparse
import json
import os

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

VARIANTS = ["baseline", "with_repo", "with_git", "with_all"]
VARIANT_LABELS = {
    "baseline": "Baseline",
    "with_repo": "+Repo",
    "with_git": "+Git",
    "with_all": "+Repo+Git",
}
COLORS = {
    "baseline":  "#6baed6",
    "with_repo": "#3182bd",
    "with_git":  "#fd8d3c",
    "with_all":  "#e6550d",
}

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def load(path: str) -> pd.DataFrame:
    with open(path) as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df["exception_match"] = df["exception_match"].astype(float)
    df["fix_proposed"]    = df["fix_proposed"].astype(float)
    df["test_generated"]  = df["test_generated"].astype(float)
    df["fix_correct"]     = pd.to_numeric(df["fix_correct"], errors="coerce")
    return df


def fig1_accuracy_comparison(df: pd.DataFrame) -> None:
    """Grouped bar: root-cause keyword accuracy per variant."""
    means = (
        df.groupby("variant")["keyword_score"].mean().reindex(VARIANTS)
    )
    stds = (
        df.groupby("variant")["keyword_score"].std().reindex(VARIANTS)
    )

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(VARIANTS))
    bars = ax.bar(
        x,
        means.values * 100,
        yerr=stds.values * 100,
        color=[COLORS[v] for v in VARIANTS],
        width=0.55,
        capsize=5,
        edgecolor="white",
        linewidth=0.8,
        error_kw={"elinewidth": 1.5, "ecolor": "#444"},
    )
    ax.set_xticks(x)
    ax.set_xticklabels([VARIANT_LABELS[v] for v in VARIANTS], fontsize=11)
    ax.set_ylabel("Root Cause Keyword Coverage (%)", fontsize=11)
    ax.set_title("Figure 1 — Root Cause Accuracy by Configuration", fontsize=12, pad=10)
    ax.set_ylim(0, 110)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    for bar, val in zip(bars, means.values * 100):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 2.5,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig1_accuracy.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  saved {out}")


def fig2_fix_correctness(df: pd.DataFrame) -> None:
    """Grouped bar: fix correctness rate and test generation rate per variant."""
    fix_rate  = df.groupby("variant")["fix_correct"].mean().reindex(VARIANTS) * 100
    test_rate = df.groupby("variant")["test_generated"].mean().reindex(VARIANTS) * 100

    x = np.arange(len(VARIANTS))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4.5))

    b1 = ax.bar(x - width/2, fix_rate.values, width, label="Fix Correct",
                color=[COLORS[v] for v in VARIANTS], edgecolor="white")
    b2 = ax.bar(x + width/2, test_rate.values, width, label="Test Generated",
                color=[COLORS[v] for v in VARIANTS], edgecolor="white", alpha=0.55, hatch="//")

    ax.set_xticks(x)
    ax.set_xticklabels([VARIANT_LABELS[v] for v in VARIANTS], fontsize=11)
    ax.set_ylabel("Rate (%)", fontsize=11)
    ax.set_title("Figure 2 — Fix Correctness & Test Generation Rate", fontsize=12, pad=10)
    ax.set_ylim(0, 115)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    solid = mpatches.Patch(color="#6baed6", label="Fix Correct")
    hatch = mpatches.Patch(facecolor="#6baed6", alpha=0.55, hatch="//", label="Test Generated")
    ax.legend(handles=[solid, hatch], fontsize=10)

    for bar in list(b1) + list(b2):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 1.5,
                f"{h:.0f}%", ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig2_fix_test.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  saved {out}")


def fig3_feature_impact(df: pd.DataFrame) -> None:
    """Horizontal bar: improvement of each context feature over baseline."""
    baseline = df[df["variant"] == "baseline"]["keyword_score"].mean()
    improvements = {}
    for v in ["with_repo", "with_git", "with_all"]:
        val = df[df["variant"] == v]["keyword_score"].mean()
        improvements[VARIANT_LABELS[v]] = (val - baseline) * 100

    fig, ax = plt.subplots(figsize=(6, 3.5))
    labels = list(improvements.keys())
    values = list(improvements.values())
    colors = ["#3182bd", "#fd8d3c", "#e6550d"]

    bars = ax.barh(labels, values, color=colors, edgecolor="white", height=0.5)
    ax.set_xlabel("Improvement in Keyword Coverage (pp)", fontsize=11)
    ax.set_title("Figure 3 — Feature Impact vs Baseline", fontsize=12, pad=10)
    ax.xaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    for bar, val in zip(bars, values):
        ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                f"+{val:.1f}pp", va="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig3_feature_impact.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  saved {out}")


def fig4_cost_accuracy(df: pd.DataFrame) -> None:
    """Scatter: cost vs keyword accuracy, coloured by variant."""
    fig, ax = plt.subplots(figsize=(6.5, 4.5))

    for v in VARIANTS:
        sub = df[df["variant"] == v]
        ax.scatter(
            sub["cost"] * 100,
            sub["keyword_score"] * 100,
            color=COLORS[v],
            label=VARIANT_LABELS[v],
            s=70, alpha=0.85, edgecolors="white", linewidths=0.6,
        )

    ax.set_xlabel("Analysis Cost (¢ USD)", fontsize=11)
    ax.set_ylabel("Root Cause Keyword Coverage (%)", fontsize=11)
    ax.set_title("Figure 4 — Cost vs Accuracy Trade-off", fontsize=12, pad=10)
    ax.legend(fontsize=10)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig4_cost_accuracy.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  saved {out}")


def fig5_per_benchmark_heatmap(df: pd.DataFrame) -> None:
    """Heatmap: keyword score per benchmark × variant."""
    pivot = df.pivot_table(
        index="benchmark_id", columns="variant", values="keyword_score"
    ).reindex(columns=VARIANTS)

    short_ids = [bid.replace("_", "\n") for bid in pivot.index]

    fig, ax = plt.subplots(figsize=(7, max(4, len(pivot) * 0.6 + 1)))
    im = ax.imshow(pivot.values, cmap="YlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(VARIANTS)))
    ax.set_xticklabels([VARIANT_LABELS[v] for v in VARIANTS], fontsize=10)
    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(short_ids, fontsize=8)
    ax.set_title("Figure 5 — Keyword Coverage Heatmap (per Benchmark)", fontsize=12, pad=10)

    for i in range(len(pivot)):
        for j in range(len(VARIANTS)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.0%}", ha="center", va="center",
                        fontsize=9, color="black" if val < 0.8 else "white")

    plt.colorbar(im, ax=ax, fraction=0.03, label="Keyword Coverage")
    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig5_heatmap.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  saved {out}")


def fig6_token_usage(df: pd.DataFrame) -> None:
    """Box plot: token distribution per variant."""
    data = [df[df["variant"] == v]["tokens"].values for v in VARIANTS]

    fig, ax = plt.subplots(figsize=(6.5, 4))
    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops={"color": "white", "linewidth": 2})
    for patch, v in zip(bp["boxes"], VARIANTS):
        patch.set_facecolor(COLORS[v])

    ax.set_xticklabels([VARIANT_LABELS[v] for v in VARIANTS], fontsize=11)
    ax.set_ylabel("Tokens per Analysis", fontsize=11)
    ax.set_title("Figure 6 — Token Usage Distribution", fontsize=12, pad=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig6_tokens.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  saved {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        default=os.path.join(os.path.dirname(__file__), "sample_results.json"),
        help="Path to eval_results.json (default: paper/sample_results.json)",
    )
    args = parser.parse_args()

    print(f"Loading results from {args.results} ...")
    df = load(args.results)
    print(f"  {len(df)} rows, {df['benchmark_id'].nunique()} benchmarks, "
          f"{df['variant'].nunique()} variants\n")

    print("Generating figures:")
    fig1_accuracy_comparison(df)
    fig2_fix_correctness(df)
    fig3_feature_impact(df)
    fig4_cost_accuracy(df)
    fig5_per_benchmark_heatmap(df)
    fig6_token_usage(df)

    print("\nAll figures saved to paper/")
    print("Replace sample_results.json with your real eval_results.json to use actual data.")


if __name__ == "__main__":
    main()
