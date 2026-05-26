from __future__ import annotations

from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parent
LOCAL_DATA_DIR = ROOT / "data"


def _local_path(relative_path: str) -> Path:
    return LOCAL_DATA_DIR / relative_path.lstrip("/")


def read_parquet_source(local_path: str, **kwargs) -> pl.DataFrame:
    return pl.read_parquet(_local_path(local_path), **kwargs)


def load_reference_stores() -> pl.DataFrame:
    return read_parquet_source("cstore_stores.parquet")


def load_reference_gtin_master() -> pl.DataFrame:
    return read_parquet_source("cstore_master_ctin.parquet")


def load_reference_store_status() -> pl.DataFrame:
    return read_parquet_source("cstore_store_status.parquet")


def load_daily_agg(store_id: str = "ALL") -> pl.DataFrame:
    frame = read_parquet_source("cstore_transactions_daily_agg.parquet")

    return frame.with_columns(
        pl.col("DATE").cast(pl.Date, strict=False),
        pl.col("STORE_ID").cast(pl.Utf8),
        pl.col("SKUPOS_DESCRIPTION").cast(pl.Utf8).alias("ProductName"),
    )


def load_transaction_sets(store_id: str = "ALL") -> pl.DataFrame:
    frame = read_parquet_source("cstore_transaction_sets.parquet")

    return frame.with_columns(
        pl.col("DATE_TIME").cast(pl.Datetime, strict=False),
        pl.col("STORE_ID").cast(pl.Utf8),
    )


def load_transaction_items(store_id: str = "ALL") -> pl.DataFrame:
    frame = read_parquet_source("transaction_items")

    return frame.with_columns(
        pl.col("DATE_TIME").cast(pl.Datetime, strict=False),
        pl.col("STORE_ID").cast(pl.Utf8),
    )