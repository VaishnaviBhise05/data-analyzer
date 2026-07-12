#!/usr/bin/env python3
"""
Data Analyzer
=============
A general-purpose command-line tool for exploring and summarizing tabular
data (CSV/Excel). It computes descriptive statistics, detects data quality
issues, generates a set of standard visualizations, and writes a Markdown
summary report.

Usage:
    python analyzer.py path/to/data.csv
    python analyzer.py path/to/data.xlsx --outdir results --sheet Sheet1
    python analyzer.py data.csv --target price   # highlight a column of interest

Outputs (written to --outdir, default "./report"):
    summary.md          Human-readable Markdown report
    figures/*.png        Charts (distributions, correlation heatmap, missingness)
    cleaned_preview.csv  First 100 rows after basic type inference
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#222222",
    "text.color": "#222222",
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
})
ACCENT = "#3B6FA0"
ACCENT2 = "#D97742"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_data(path: str, sheet: str = None) -> pd.DataFrame:
    """Load CSV or Excel data into a DataFrame."""
    ext = Path(path).suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        sep = "\t" if ext == ".tsv" else None
        df = pd.read_csv(path, sep=sep, engine="python")
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet or 0)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def infer_column_types(df: pd.DataFrame):
    """Split columns into numeric, categorical, and datetime groups."""
    numeric_cols, categorical_cols, datetime_cols = [], [], []
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(col)
            continue
        # try datetime parse on a sample
        sample = series.dropna().astype(str).head(50)
        if len(sample) > 0:
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
            if parsed.notna().mean() > 0.8:
                datetime_cols.append(col)
                continue
        categorical_cols.append(col)
    return numeric_cols, categorical_cols, datetime_cols


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

def basic_overview(df: pd.DataFrame) -> dict:
    return {
        "n_rows": len(df),
        "n_cols": df.shape[1],
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 3),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_missing": int(df.isna().sum().sum()),
        "pct_missing": round(df.isna().sum().sum() / df.size * 100, 2) if df.size else 0,
    }


def missingness_table(df: pd.DataFrame) -> pd.DataFrame:
    miss = df.isna().sum()
    pct = (miss / len(df) * 100).round(2)
    out = pd.DataFrame({"missing_count": miss, "missing_pct": pct})
    return out[out["missing_count"] > 0].sort_values("missing_pct", ascending=False)


def numeric_summary(df: pd.DataFrame, numeric_cols: list) -> pd.DataFrame:
    if not numeric_cols:
        return pd.DataFrame()
    desc = df[numeric_cols].describe().T
    desc["skew"] = df[numeric_cols].skew()
    desc["missing"] = df[numeric_cols].isna().sum()
    # simple IQR-based outlier count
    outlier_counts = []
    for col in numeric_cols:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_counts.append(int(((df[col] < lo) | (df[col] > hi)).sum()))
    desc["outliers_iqr"] = outlier_counts
    return desc.round(3)


def categorical_summary(df: pd.DataFrame, categorical_cols: list, top_n=5) -> dict:
    out = {}
    for col in categorical_cols:
        vc = df[col].value_counts(dropna=True).head(top_n)
        out[col] = {
            "n_unique": int(df[col].nunique(dropna=True)),
            "top_values": vc.to_dict(),
            "missing": int(df[col].isna().sum()),
        }
    return out


def correlation_matrix(df: pd.DataFrame, numeric_cols: list) -> pd.DataFrame:
    if len(numeric_cols) < 2:
        return pd.DataFrame()
    return df[numeric_cols].corr(numeric_only=True).round(3)


def top_correlations(corr: pd.DataFrame, n=8) -> list:
    if corr.empty:
        return []
    pairs = []
    cols = corr.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            val = corr.iloc[i, j]
            if pd.notna(val):
                pairs.append((cols[i], cols[j], val))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs[:n]


# --------------------------------------------------------------------------
# Visualization
# --------------------------------------------------------------------------

def plot_missingness(df: pd.DataFrame, outdir: Path):
    miss = df.isna().mean().sort_values(ascending=False)
    miss = miss[miss > 0]
    if miss.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(miss))))
    ax.barh(miss.index[::-1], (miss[::-1] * 100), color=ACCENT2)
    ax.set_xlabel("Missing (%)")
    ax.set_title("Missing Data by Column")
    fig.tight_layout()
    path = outdir / "figures" / "missingness.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_distributions(df: pd.DataFrame, numeric_cols: list, outdir: Path):
    if not numeric_cols:
        return None
    cols = numeric_cols[:12]
    n = len(cols)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
    axes = np.array(axes).reshape(-1)
    for ax, col in zip(axes, cols):
        data = df[col].dropna()
        ax.hist(data, bins=30, color=ACCENT, edgecolor="white")
        ax.set_title(col, fontsize=10)
    for ax in axes[len(cols):]:
        ax.axis("off")
    fig.suptitle("Numeric Distributions", fontweight="bold")
    fig.tight_layout()
    path = outdir / "figures" / "distributions.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_correlation_heatmap(corr: pd.DataFrame, outdir: Path):
    if corr.empty:
        return None
    fig, ax = plt.subplots(figsize=(max(5, 0.6 * len(corr)), max(4, 0.6 * len(corr))))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(corr.columns, fontsize=8)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Correlation Matrix")
    fig.tight_layout()
    path = outdir / "figures" / "correlation_heatmap.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_top_categories(df: pd.DataFrame, categorical_cols: list, outdir: Path, top_n=10):
    paths = []
    for col in categorical_cols[:6]:
        vc = df[col].value_counts(dropna=True).head(top_n)
        if vc.empty:
            continue
        fig, ax = plt.subplots(figsize=(6, max(2.5, 0.35 * len(vc))))
        ax.barh(vc.index[::-1].astype(str), vc.values[::-1], color=ACCENT)
        ax.set_title(f"Top values: {col}")
        fig.tight_layout()
        safe = "".join(ch if ch.isalnum() else "_" for ch in col)[:40]
        path = outdir / "figures" / f"top_{safe}.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        paths.append(path)
    return paths


def plot_target_relationships(df: pd.DataFrame, target: str, numeric_cols: list, outdir: Path):
    """If a target column is specified, plot its relationship to other numeric columns."""
    if target not in df.columns:
        return None
    others = [c for c in numeric_cols if c != target][:8]
    if not others or target not in numeric_cols:
        return None
    ncols = 3
    nrows = int(np.ceil(len(others) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
    axes = np.array(axes).reshape(-1)
    for ax, col in zip(axes, others):
        ax.scatter(df[col], df[target], alpha=0.4, s=12, color=ACCENT)
        ax.set_xlabel(col)
        ax.set_ylabel(target)
    for ax in axes[len(others):]:
        ax.axis("off")
    fig.suptitle(f"Relationships with '{target}'", fontweight="bold")
    fig.tight_layout()
    path = outdir / "figures" / "target_relationships.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# Report generation
# --------------------------------------------------------------------------

def write_report(outdir: Path, source_name: str, overview: dict, miss_table: pd.DataFrame,
                  num_summary: pd.DataFrame, cat_summary: dict, corr: pd.DataFrame,
                  top_corr: list, figure_paths: dict, target: str = None):
    lines = []
    lines.append(f"# Data Analysis Report: {source_name}\n")

    lines.append("## Overview\n")
    lines.append(f"- Rows: **{overview['n_rows']:,}**")
    lines.append(f"- Columns: **{overview['n_cols']}**")
    lines.append(f"- Memory usage: **{overview['memory_mb']} MB**")
    lines.append(f"- Duplicate rows: **{overview['duplicate_rows']:,}**")
    lines.append(f"- Missing cells: **{overview['total_missing']:,}** ({overview['pct_missing']}% of all cells)\n")

    if figure_paths.get("missingness"):
        lines.append("## Missing Data\n")
        if not miss_table.empty:
            lines.append(miss_table.to_markdown())
        lines.append(f"\n![Missingness](figures/{figure_paths['missingness'].name})\n")

    if not num_summary.empty:
        lines.append("## Numeric Columns\n")
        lines.append(num_summary.to_markdown())
        if figure_paths.get("distributions"):
            lines.append(f"\n![Distributions](figures/{figure_paths['distributions'].name})\n")

    if cat_summary:
        lines.append("\n## Categorical Columns\n")
        for col, info in cat_summary.items():
            lines.append(f"**{col}** — {info['n_unique']} unique values, {info['missing']} missing")
            top_vals = ", ".join(f"{k} ({v})" for k, v in info["top_values"].items())
            lines.append(f"  Top values: {top_vals}\n")
        for p in figure_paths.get("top_categories", []):
            lines.append(f"![{p.stem}](figures/{p.name})\n")

    if not corr.empty:
        lines.append("## Correlations\n")
        if top_corr:
            lines.append("Strongest pairwise correlations:\n")
            for a, b, v in top_corr:
                lines.append(f"- {a} ↔ {b}: **{v:+.3f}**")
        if figure_paths.get("correlation_heatmap"):
            lines.append(f"\n![Correlation heatmap](figures/{figure_paths['correlation_heatmap'].name})\n")

    if target and figure_paths.get("target_relationships"):
        lines.append(f"## Relationships with target: `{target}`\n")
        lines.append(f"![Target relationships](figures/{figure_paths['target_relationships'].name})\n")

    report_path = outdir / "summary.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run(input_path: str, outdir: str = "report", sheet: str = None, target: str = None):
    outdir = Path(outdir)
    (outdir / "figures").mkdir(parents=True, exist_ok=True)

    df = load_data(input_path, sheet=sheet)
    numeric_cols, categorical_cols, datetime_cols = infer_column_types(df)

    overview = basic_overview(df)
    miss_table = missingness_table(df)
    num_summary = numeric_summary(df, numeric_cols)
    cat_summary = categorical_summary(df, categorical_cols)
    corr = correlation_matrix(df, numeric_cols)
    top_corr = top_correlations(corr)

    figure_paths = {}
    figure_paths["missingness"] = plot_missingness(df, outdir)
    figure_paths["distributions"] = plot_distributions(df, numeric_cols, outdir)
    figure_paths["correlation_heatmap"] = plot_correlation_heatmap(corr, outdir)
    figure_paths["top_categories"] = plot_top_categories(df, categorical_cols, outdir)
    if target:
        figure_paths["target_relationships"] = plot_target_relationships(df, target, numeric_cols, outdir)

    df.head(100).to_csv(outdir / "cleaned_preview.csv", index=False)

    report_path = write_report(
        outdir, Path(input_path).name, overview, miss_table, num_summary,
        cat_summary, corr, top_corr, figure_paths, target=target
    )

    print(f"Rows x Cols: {overview['n_rows']} x {overview['n_cols']}")
    print(f"Numeric columns: {len(numeric_cols)} | Categorical: {len(categorical_cols)} | Datetime: {len(datetime_cols)}")
    print(f"Missing cells: {overview['total_missing']} ({overview['pct_missing']}%)")
    print(f"\nReport written to: {report_path}")
    print(f"Figures written to: {outdir / 'figures'}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Analyze a CSV/Excel dataset and generate a report.")
    parser.add_argument("input", help="Path to a CSV or Excel file")
    parser.add_argument("--outdir", default="report", help="Directory to write report/figures (default: ./report)")
    parser.add_argument("--sheet", default=None, help="Sheet name, for Excel files")
    parser.add_argument("--target", default=None, help="Optional numeric column to highlight relationships for")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    run(args.input, outdir=args.outdir, sheet=args.sheet, target=args.target)


if __name__ == "__main__":
    main()
