# Data Analyzer

A command-line tool that takes any CSV or Excel file and produces:
- A Markdown summary report (`report/summary.md`)
- A set of charts (`report/figures/`): distributions, missing-data map, correlation heatmap, top categories, and optional target relationships
- A 100-row cleaned preview CSV

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Try it with the included sample data
python make_sample_data.py
python analyzer.py sample_sales.csv

# Use your own file
python analyzer.py path/to/your_data.csv

# Excel input, specific sheet
python analyzer.py data.xlsx --sheet "Sheet1"

# Highlight relationships against a specific numeric column (e.g. a target you care about)
python analyzer.py data.csv --target revenue

# Custom output folder
python analyzer.py data.csv --outdir my_report
```

## What it computes

- **Overview**: row/column counts, memory footprint, duplicate rows, missing-cell rate
- **Missing data**: per-column count + percentage, plus a bar chart
- **Numeric columns**: mean/std/quartiles, skew, and IQR-based outlier counts
- **Categorical columns**: cardinality, top values, missing counts
- **Correlations**: full correlation matrix + heatmap + the strongest pairwise correlations called out
- **Target relationships** (optional): scatter plots of every other numeric column against `--target`

## Files

| File | Purpose |
|---|---|
| `analyzer.py` | Main CLI tool — all analysis and plotting logic |
| `make_sample_data.py` | Generates a synthetic sales dataset for testing |
| `requirements.txt` | Python dependencies |

## Notes

- Column types (numeric / categorical / datetime) are inferred automatically.
- Works with messy real-world data: handles missing values, mixed types, and datetime strings without extra config.
- Output is self-contained — the Markdown report references the PNGs by relative path, so the whole `report/` folder can be shared as-is.
