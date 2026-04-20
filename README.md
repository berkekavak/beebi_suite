# Data Profiler

Upload a dataset, pick a target column, and get a complete statistical profile — distributions, missing values, target-conditioned stats, feature importance, and correlations.

## Install

```bash
pip install -r requirements.txt
```

## Run the web UI

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`), upload a CSV/Excel/Parquet file, select your target column, and click **Run profile**.

## Run from the command line

```bash
python cli.py data.csv --target churn
python cli.py data.csv --target price --task regression --output my_report.xlsx
```

## Use as a library

```python
import pandas as pd
from profiler import profile

df = pd.read_csv("data.csv")
result = profile(df, target="churn")

print(result.overview)
print(result.numeric_stats)
print(result.feature_importance)
```

## What it computes

**Overview:** rows, columns, memory, duplicates, missing %, dtypes.

**Target analysis:**
- Classification → class distribution + imbalance ratio
- Regression → mean / std / quantiles / skew / kurtosis

**Per-feature stats:**
- Numeric: count, mean, std, min/q25/median/q75/max, skew, kurtosis, IQR outliers, zeros
- Categorical: unique, top value, top frequency %, mode dominance

**Target-conditioned analysis:**
- Classification → per-class means & stds for numeric features, P(target | category) for categoricals
- Regression → Pearson + Spearman correlations with target, per-category target means

**Feature importance:**
- Mutual information (non-linear dependence)
- Pearson r (numeric → numeric)
- ANOVA F-test (numeric → categorical target, or categorical → numeric target)
- Chi-square (categorical → categorical)

**Missing values:** per-column missing counts, percentages, and visualizations.

**Correlations:** Pearson correlation matrix across all numeric columns.

## Output

The web UI shows everything interactively with Plotly charts. Click **Download full report (Excel)** to export a multi-sheet `.xlsx` with all tables. The CLI writes the same Excel report directly.

## File structure

```
data_profiler/
├── profiler.py      # Core analysis logic (pure functions, no UI deps)
├── app.py           # Streamlit web UI
├── cli.py           # Command-line interface
├── requirements.txt
└── README.md
```
