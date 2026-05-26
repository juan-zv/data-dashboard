from __future__ import annotations

import os
from pathlib import Path

import polars as pl

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit may be unavailable in non-app contexts
    st = None


ROOT = Path(__file__).resolve().parent
LOCAL_DATA_DIR = ROOT / "data"


def _get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return str(value).strip()

    if st is not None:
        try:
            secret_value = st.secrets.get(name, default)
            return str(secret_value).strip() if secret_value is not None else default
        except Exception:
            return default

    return default


def _remote_bucket_config() -> dict[str, str]:
    bucket = _get_setting("SUPABASE_S3_BUCKET", "")
    endpoint = _get_setting("SUPABASE_S3_ENDPOINT", "")
    access_key = _get_setting("SUPABASE_S3_ACCESS_KEY_ID", "")
    secret_key = _get_setting("SUPABASE_S3_SECRET_ACCESS_KEY", "")
    region = _get_setting("SUPABASE_S3_REGION", "us-east-2") or "us-east-2"

    if not all([bucket, endpoint, access_key, secret_key]):
        return {}

    return {
        "bucket": bucket,
        "endpoint": endpoint,
        "access_key": access_key,
        "secret_key": secret_key,
        "region": region,
    }


def using_remote_bucket() -> bool:
    return bool(_remote_bucket_config())


def _storage_options() -> dict[str, str]:
    config = _remote_bucket_config()
    if not config:
        return {}

    return {
        "aws_access_key_id": config["access_key"],
        "aws_secret_access_key": config["secret_key"],
        "aws_region": config["region"],
        "aws_endpoint_url": config["endpoint"],
    }


def _remote_uri(relative_path: str) -> str:
    config = _remote_bucket_config()
    if not config:
        raise RuntimeError("Remote bucket is not configured")
    return f"s3://{config['bucket']}/{relative_path.lstrip('/')}"


def _local_path(relative_path: str) -> Path:
    return LOCAL_DATA_DIR / relative_path.lstrip("/")


def read_parquet_source(remote_path: str, local_path: str, **kwargs) -> pl.DataFrame:
    if using_remote_bucket():
        return pl.read_parquet(_remote_uri(remote_path), storage_options=_storage_options(), **kwargs)
    return pl.read_parquet(_local_path(local_path), **kwargs)


def scan_parquet_source(remote_path: str, local_path: str, **kwargs) -> pl.LazyFrame:
    if using_remote_bucket():
        return pl.scan_parquet(_remote_uri(remote_path), storage_options=_storage_options(), **kwargs)
    return pl.scan_parquet(_local_path(local_path), **kwargs)


def _store_glob(store_id: str) -> str:
    store_part = "*" if store_id == "ALL" else str(store_id)
    return f"store_id={store_part}/year=*/month=*/part.parquet"


def load_reference_stores() -> pl.DataFrame:
    return read_parquet_source(
        "parquet/reference/stores.parquet",
        "cstore_stores.parquet",
    )


def load_reference_gtin_master() -> pl.DataFrame:
    return read_parquet_source(
        "parquet/reference/gtin_master.parquet",
        "cstore_master_ctin.parquet",
    )


def load_reference_store_status() -> pl.DataFrame:
    return read_parquet_source(
        "parquet/reference/store_status.parquet",
        "cstore_store_status.parquet",
    )


def load_daily_agg(store_id: str = "ALL") -> pl.DataFrame:
    if using_remote_bucket():
        frame = scan_parquet_source(
            f"parquet/facts/daily_agg/{_store_glob(store_id)}",
            "cstore_transactions_daily_agg.parquet",
        ).collect()
    else:
        frame = read_parquet_source(
            "parquet/facts/daily_agg/store_id=*/year=*/month=*/part.parquet",
            "cstore_transactions_daily_agg.parquet",
        )

    return frame.with_columns(
        pl.col("DATE").cast(pl.Date, strict=False),
        pl.col("STORE_ID").cast(pl.Utf8),
        pl.col("SKUPOS_DESCRIPTION").cast(pl.Utf8).alias("ProductName"),
    )


def load_transaction_sets(store_id: str = "ALL") -> pl.DataFrame:
    if using_remote_bucket():
        frame = scan_parquet_source(
            f"parquet/facts/transaction_sets/{_store_glob(store_id)}",
            "cstore_transaction_sets.parquet",
        ).collect()
    else:
        frame = read_parquet_source(
            "parquet/facts/transaction_sets/store_id=*/year=*/month=*/part.parquet",
            "cstore_transaction_sets.parquet",
        )

    return frame.with_columns(
        pl.col("DATE_TIME").cast(pl.Datetime, strict=False),
        pl.col("STORE_ID").cast(pl.Utf8),
    )


def load_transaction_items(store_id: str = "ALL") -> pl.DataFrame:
    if using_remote_bucket():
        frame = scan_parquet_source(
            f"parquet/facts/transaction_items/{_store_glob(store_id)}",
            "transaction_items",
        ).collect()
    else:
        frame = read_parquet_source(
            "parquet/facts/transaction_items/store_id=*/year=*/month=*/part.parquet",
            "transaction_items",
        )

    return frame.with_columns(
        pl.col("DATE_TIME").cast(pl.Datetime, strict=False),
        pl.col("STORE_ID").cast(pl.Utf8),
    )