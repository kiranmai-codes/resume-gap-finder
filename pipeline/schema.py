import pandas as pd


CANONICAL_COLUMNS = [
    "source_portal",
    "source_job_id",
    "job_title",
    "company_name",
    "location",
    "description",
    "discovery_family",
]


def standardize_schema(df: pd.DataFrame, portal_name: str) -> pd.DataFrame:
    """Map a raw portal DataFrame to canonical schema.

    Uses dict-of-lists construction — positional, no index alignment,
    NaN impossible.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    n = len(df)

    def positional_col(name, *fallbacks):
        for candidate in (name,) + fallbacks:
            if candidate in df.columns:
                values = df[candidate].tolist()  # positional, no index
                return [
                    "" if v is None or (isinstance(v, float) and pd.isna(v))
                    else str(v).strip()
                    for v in values
                ]
        return [""] * n

    return pd.DataFrame({
        "source_portal":    [portal_name] * n,
        "source_job_id":    positional_col("source_job_id", "job_id"),
        "job_title":        positional_col("job_title"),
        "company_name":     positional_col("company_name"),
        "location":         positional_col("location"),
        "description":      positional_col("description"),
        "discovery_family": positional_col("discovery_family"),
    })[CANONICAL_COLUMNS]
