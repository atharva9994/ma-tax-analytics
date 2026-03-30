"""
data_cleaner.py
---------------
Reads CSV or Excel uploads, standardizes columns, removes duplicates,
fixes missing values, and returns a cleaned DataFrame plus a summary dict.
"""

import io
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Column name normalisation map
# Keys are common raw spellings; values are the canonical names used
# throughout the rest of the application.
# ---------------------------------------------------------------------------
COLUMN_ALIASES = {
    # Taxpayer identifiers
    "business name":        "Business_Name",
    "taxpayer name":        "Business_Name",
    "company name":         "Business_Name",
    "name":                 "Business_Name",
    "taxpayer id":          "Taxpayer_ID",
    "ein":                  "Taxpayer_ID",
    "id":                   "Taxpayer_ID",

    # Geography
    "city":                 "City",
    "municipality":         "City",
    "town":                 "City",
    "zip":                  "Zip_Code",
    "zip code":             "Zip_Code",
    "postal code":          "Zip_Code",

    # Classification
    "industry":             "Industry",
    "sector":               "Industry",
    "business type":        "Industry",
    "naics":                "NAICS_Code",
    "naics code":           "NAICS_Code",

    # Time
    "tax year":             "Tax_Year",
    "year":                 "Tax_Year",
    "fiscal year":          "Tax_Year",

    # Tax type
    "tax type":             "Tax_Type",
    "type of tax":          "Tax_Type",
    "tax category":         "Tax_Type",

    # Revenue & tax figures
    "reported revenue":     "Reported_Revenue",
    "reported_revenue":     "Reported_Revenue",
    "revenue reported":     "Reported_Revenue",
    "gross revenue":        "Reported_Revenue",
    "revenue":              "Reported_Revenue",

    "industry avg revenue": "Industry_Avg_Revenue",
    "industry_avg_revenue": "Industry_Avg_Revenue",
    "expected revenue":     "Industry_Avg_Revenue",
    "average revenue":      "Industry_Avg_Revenue",

    "tax paid":             "Tax_Paid",
    "taxes paid":           "Tax_Paid",
    "amount paid":          "Tax_Paid",

    "expected tax":         "Expected_Tax",
    "tax liability":        "Expected_Tax",
    "tax due":              "Expected_Tax",

    "estimated tax gap":    "Estimated_Tax_Gap",
    "tax gap":              "Estimated_Tax_Gap",
    "gap":                  "Estimated_Tax_Gap",

    "revenue ratio":        "Revenue_Ratio",
    "ratio":                "Revenue_Ratio",

    # Filing / compliance
    "filing status":        "Filing_Status",
    "status":               "Filing_Status",
    "compliance flag":      "Compliance_Flag",
    "compliance":           "Compliance_Flag",
    "compliant":            "Compliance_Flag",

    # Audit history
    "previously audited":   "Previously_Audited",
    "audited before":       "Previously_Audited",
    "prior audit":          "Previously_Audited",
    "prior audit result":   "Prior_Audit_Result",
    "audit result":         "Prior_Audit_Result",
    "audit outcome":        "Prior_Audit_Result",
}

# Numeric columns – will be coerced to float
NUMERIC_COLS = [
    "Reported_Revenue",
    "Industry_Avg_Revenue",
    "Tax_Paid",
    "Expected_Tax",
    "Estimated_Tax_Gap",
    "Revenue_Ratio",
]

# Categorical columns – will be stripped and title-cased
CATEGORICAL_COLS = [
    "Industry",
    "City",
    "Tax_Type",
    "Filing_Status",
    "Compliance_Flag",
    "Previously_Audited",
    "Prior_Audit_Result",
]


def _normalise_column_name(raw: str) -> str:
    """Lower-strip a raw column name and look it up in COLUMN_ALIASES."""
    key = raw.strip().lower().replace("_", " ")
    return COLUMN_ALIASES.get(key, raw.strip())


def _read_file(uploaded_file) -> tuple[list[pd.DataFrame], int]:
    """
    Accept a file-like object (Streamlit UploadedFile, path string, or
    io.BytesIO) and return (list_of_dataframes, sheet_count).
    """
    name = getattr(uploaded_file, "name", str(uploaded_file)).lower()

    if name.endswith((".xlsx", ".xls")):
        xl = pd.ExcelFile(uploaded_file)
        sheets = xl.sheet_names
        frames = [xl.parse(s) for s in sheets]
        return frames, len(sheets)
    else:
        # CSV / TSV
        df = pd.read_csv(uploaded_file)
        return [df], 1


def _coerce_numerics(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Strip currency symbols and commas then coerce to float. Returns (df, blanks_fixed)."""
    blanks_fixed = 0
    for col in NUMERIC_COLS:
        if col not in df.columns:
            continue
        before_nulls = df[col].isna().sum()
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[\$,\s]", "", regex=True)
                .replace("nan", np.nan)
            )
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_nulls = df[col].isna().sum()
        blanks_fixed += int(after_nulls - before_nulls)
    return df, blanks_fixed


def _fix_categoricals(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Standardise categorical columns. Returns (df, blanks_fixed)."""
    blanks_fixed = 0
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": np.nan, "None": np.nan, "": np.nan})
        blanks_fixed += int(df[col].isna().sum())
        # Title-case non-null values for consistent grouping
        mask = df[col].notna()
        df.loc[mask, col] = df.loc[mask, col].str.title()
    return df, blanks_fixed


def _derive_missing_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Derive Revenue_Ratio and Estimated_Tax_Gap if not already present."""
    if "Revenue_Ratio" not in df.columns:
        if {"Reported_Revenue", "Industry_Avg_Revenue"}.issubset(df.columns):
            df["Revenue_Ratio"] = df["Reported_Revenue"] / df["Industry_Avg_Revenue"].replace(0, np.nan)

    if "Estimated_Tax_Gap" not in df.columns:
        if {"Expected_Tax", "Tax_Paid"}.issubset(df.columns):
            df["Estimated_Tax_Gap"] = (df["Expected_Tax"] - df["Tax_Paid"]).clip(lower=0)

    return df


def clean(uploaded_file) -> tuple[pd.DataFrame, dict]:
    """
    Main entry point.

    Parameters
    ----------
    uploaded_file : Streamlit UploadedFile, path string, or io.BytesIO

    Returns
    -------
    df_clean : pd.DataFrame
    summary  : dict with keys:
        sheet_count, rows_before, rows_after,
        duplicates_removed, blanks_fixed, columns_detected
    """
    frames, sheet_count = _read_file(uploaded_file)

    # Combine sheets / single frame
    df = pd.concat(frames, ignore_index=True)
    rows_before = len(df)

    # 1. Normalise column names
    df.columns = [_normalise_column_name(c) for c in df.columns]

    # 2. Remove fully empty rows
    df.dropna(how="all", inplace=True)

    # 3. Remove duplicate rows
    dupes_before = len(df)
    df.drop_duplicates(inplace=True)
    duplicates_removed = dupes_before - len(df)

    # 4. Coerce numeric columns
    df, blanks_num = _coerce_numerics(df)

    # 5. Fix categoricals
    df, blanks_cat = _fix_categoricals(df)
    blanks_fixed = blanks_num + blanks_cat

    # 6. Derive missing computed columns
    df = _derive_missing_columns(df)

    # 7. Reset index
    df.reset_index(drop=True, inplace=True)
    rows_after = len(df)

    summary = {
        "sheet_count":        sheet_count,
        "rows_before":        rows_before,
        "rows_after":         rows_after,
        "duplicates_removed": duplicates_removed,
        "blanks_fixed":       blanks_fixed,
        "columns_detected":   list(df.columns),
    }

    return df, summary
