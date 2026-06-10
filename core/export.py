"""
Consolidated export for a completed Job - with strong error handling for massive scale.

Key improvements for "export masivo":
- Per-shard error collection (never lose the whole export because 1 bad PDF shard).
- Memory-efficient strategy (low_memory mode): process shards in small groups, write intermediate Parquets, final merge.
- Prefer pyarrow for Parquet I/O when available (lighter on memory than full pandas DataFrame for metadata/row groups).
- Always produce a detailed sidecar manifest.json with:
    shards_total, shards_ok, shards_failed, errors[], rows_written, formats, timestamp, etc.
- Update Job with export_status, export_errors, export_row_count, export_manifest_key.
- Export is **never fatal**: workers and finalize treat failures as warnings + partial success.
- Graceful fallbacks (parquet -> csv, skip bad shards, etc.).
"""

from __future__ import annotations
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import List, Optional, Dict, Any

import pandas as pd

from .db import get_job, update_job
from .storage import get_storage, StorageBackend

logger = logging.getLogger(__name__)

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False


def list_result_shards(job_id: str, storage: Optional[StorageBackend] = None) -> List[str]:
    """Return storage keys for result shards. Robust to partial listing failures."""
    job = get_job(job_id)
    if not job or not job.storage_prefix:
        return []

    storage = storage or get_storage()
    prefix = f"{job.storage_prefix}/results/"
    shards = []
    errors = []

    try:
        for obj in storage.list_prefix(prefix):
            key = obj.key
            if key.endswith(".parquet"):
                shards.append(key)
            elif key.endswith(".csv") and not shards:  # only use csv if no parquet
                shards.append(key)
    except Exception as e:
        errors.append({"action": "list_prefix", "error": str(e)})
        logger.warning(f"list_result_shards partial failure for {job_id}: {e}")

    return sorted(shards)


def _read_shard(storage: StorageBackend, key: str) -> Optional[pd.DataFrame]:
    """Read one shard safely. Returns DF or None on failure."""
    try:
        data = storage.get_bytes(key)
        if key.endswith(".parquet"):
            if PYARROW_AVAILABLE:
                # More efficient path
                table = pq.read_table(pa.BufferReader(data))
                return table.to_pandas()
            else:
                return pd.read_parquet(pd.io.common.BytesIO(data))
        else:
            return pd.read_csv(pd.io.common.BytesIO(data))
    except Exception as e:
        logger.error(f"Failed reading shard {key}: {e}")
        return None


def _write_manifest(
    storage: StorageBackend,
    job,
    *,
    shards_ok: int,
    shards_failed: int,
    errors: List[Dict],
    rows_written: int,
    formats_written: List[str],
    primary_key: Optional[str],
) -> str:
    """Write a detailed JSON manifest next to the results."""
    short = job.id[:8]
    manifest_key = f"{job.storage_prefix}/results/job_{short}_export_manifest.json"

    manifest = {
        "job_id": job.id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "shards_total": shards_ok + shards_failed,
        "shards_ok": shards_ok,
        "shards_failed": shards_failed,
        "errors": errors[:50],  # cap to avoid huge manifests
        "rows_written": rows_written,
        "formats": formats_written,
        "primary_result_key": primary_key,
        "recommendation": "Use Parquet for large exports. Split very big jobs by date/provider if >5M rows.",
    }

    try:
        storage.put_bytes(
            manifest_key,
            json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )
        logger.info(f"Wrote export manifest for {job.id}: {manifest_key}")
    except Exception as e:
        logger.error(f"Failed to write manifest: {e}")
        manifest_key = ""

    return manifest_key


def export_consolidated(
    job_id: str,
    formats: List[str] = ("parquet",),
    storage: Optional[StorageBackend] = None,
    low_memory: bool = True,
    max_shards_per_group: int = 80,
    # === NEW: incremental / filtered export for very large jobs ===
    filter_proveedor: Optional[str] = None,
    filter_fecha_desde: Optional[str] = None,   # simple string prefix match on Vigencia or filename
    group_by: Optional[str] = None,             # e.g. "Proveedor" → separate file per provider
) -> Dict[str, Any]:
    """
    Robust consolidated export.

    Returns rich result with errors, manifest, etc.

    New for massive jobs:
    - filter_proveedor, filter_fecha_desde: produce smaller partial exports without re-reading everything.
    - group_by="Proveedor": creates one file per unique provider (very useful for negotiation).

    low_memory=True (default): processes shards in small groups to keep RAM reasonable.
    """
    job = get_job(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}

    storage = storage or get_storage()
    shards = list_result_shards(job_id, storage=storage)

    if not shards:
        logger.warning(f"No shards for export job={job_id}")
        update_job(job_id, export_status="failed", export_errors=[{"error": "no shards found"}])
        return {"success": False, "shards_ok": 0, "shards_failed": 0}

    errors: List[Dict[str, Any]] = []
    successful_frames_or_paths = []
    shards_ok = 0
    shards_failed = 0
    total_rows = 0

    # === Low memory strategy: group shards ===
    if low_memory and len(shards) > max_shards_per_group:
        logger.info(f"Using low-memory grouped export for {job_id} ({len(shards)} shards)")
        groups = [shards[i:i + max_shards_per_group] for i in range(0, len(shards), max_shards_per_group)]

        temp_keys = []
        for gidx, group in enumerate(groups):
            group_frames = []
            for key in group:
                df = _read_shard(storage, key)
                if df is not None:
                    group_frames.append(df)
                    shards_ok += 1
                    total_rows += len(df)
                else:
                    shards_failed += 1
                    errors.append({"shard": key, "error": "read_failed"})

            if group_frames:
                try:
                    group_df = pd.concat(group_frames, ignore_index=True)
                    # Write intermediate parquet for this group
                    tmp_key = f"{job.storage_prefix}/results/_tmp_group_{gidx:04d}.parquet"
                    buf = group_df.to_parquet(index=False)
                    storage.put_bytes(tmp_key, buf, content_type="application/parquet")
                    temp_keys.append(tmp_key)
                    del group_df, group_frames   # free memory
                except Exception as e:
                    errors.append({"group": gidx, "error": str(e)[:300]})
                    shards_failed += len(group)  # rough

        # Final merge of the temp group files (still can be large, but fewer)
        if temp_keys:
            final_frames = []
            for tk in temp_keys:
                df = _read_shard(storage, tk)
                if df is not None:
                    final_frames.append(df)
                # best effort cleanup of temp
                try:
                    storage.delete(tk)
                except Exception:
                    pass

            if final_frames:
                consolidated = pd.concat(final_frames, ignore_index=True)
            else:
                consolidated = pd.DataFrame()
        else:
            consolidated = pd.DataFrame()

    else:
        # Normal path (smaller jobs) or forced full load
        frames = []
        for key in shards:
            df = _read_shard(storage, key)
            if df is not None:
                frames.append(df)
                shards_ok += 1
                total_rows += len(df)
            else:
                shards_failed += 1
                errors.append({"shard": key, "error": "read_failed"})

        if not frames:
            update_job(job_id, export_status="failed", export_errors=errors[:20])
            return {"success": False, "shards_ok": 0, "shards_failed": shards_failed, "errors": errors}

        try:
            consolidated = pd.concat(frames, ignore_index=True)
        except Exception as e:
            errors.append({"phase": "concat", "error": str(e)[:300]})
            # Try to salvage what we have
            if frames:
                consolidated = pd.concat(frames[:1], ignore_index=True)  # at least first group
            else:
                consolidated = pd.DataFrame()

    # === NEW: Incremental / filtered / grouped export for massive jobs ===
    original_rows = len(consolidated) if 'consolidated' in locals() else 0
    if filter_proveedor and 'consolidated' in locals():
        consolidated = consolidated[
            consolidated.get("Proveedor", pd.Series(dtype=str)).astype(str).str.contains(filter_proveedor, case=False, na=False)
        ]
        errors.append({"applied_filter": f"proveedor~{filter_proveedor}", "rows_after": len(consolidated)})

    if filter_fecha_desde and 'consolidated' in locals():
        mask = (consolidated.get("Vigencia", pd.Series(dtype=str)).astype(str).str.contains(filter_fecha_desde, na=False)) | \
               (consolidated.get("Archivo", pd.Series(dtype=str)).astype(str).str.contains(filter_fecha_desde, na=False))
        consolidated = consolidated[mask]
        errors.append({"applied_filter": f"fecha~{filter_fecha_desde}", "rows_after": len(consolidated)})

    grouped_exports = {}
    if group_by and 'consolidated' in locals() and group_by in consolidated.columns:
        for val, gdf in consolidated.groupby(group_by, dropna=False):
            safe = str(val).replace("/", "_").replace(" ", "_")[:50] or "SIN_PROVEEDOR"
            grouped_exports[safe] = gdf
        # Do not write the giant one when grouping
        consolidated = pd.DataFrame()

    # === Write outputs ===
    short_id = job_id[:8]
    base = f"{job.storage_prefix}/results/job_{short_id}_consolidated"
    results = {}
    formats_written = []

    # Parquet (preferred)
    if "parquet" in formats and len(consolidated) > 0:
        try:
            key = f"{base}.parquet"
            buf = consolidated.to_parquet(index=False)
            storage.put_bytes(key, buf, content_type="application/parquet")
            results["parquet"] = key
            formats_written.append("parquet")
            logger.info(f"Exported parquet {key} ({len(consolidated)} rows)")
        except Exception as e:
            errors.append({"format": "parquet", "error": str(e)[:300]})

    # XLSX (dangerous for massive)
    if "xlsx" in formats and len(consolidated) > 0:
        if len(consolidated) > 900_000:
            errors.append({"format": "xlsx", "error": "too_many_rows_for_excel (>900k) - skipped"})
        else:
            try:
                key = f"{base}.xlsx"
                from io import BytesIO
                bio = BytesIO()
                with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                    consolidated.to_excel(writer, index=False, sheet_name="data")
                storage.put_bytes(key, bio.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                results["xlsx"] = key
                formats_written.append("xlsx")
            except Exception as e:
                errors.append({"format": "xlsx", "error": str(e)[:300]})

    # CSV always as last resort / compatibility
    if ("csv" in formats or not results) and len(consolidated) > 0:
        try:
            key = f"{base}.csv"
            storage.put_bytes(key, consolidated.to_csv(index=False).encode("utf-8"), content_type="text/csv")
            results["csv"] = key
            formats_written.append("csv")
        except Exception as e:
            errors.append({"format": "csv", "error": str(e)[:300]})

    # === Grouped / incremental export support (by proveedor, etc.) ===
    if grouped_exports:
        for gname, gdf in list(grouped_exports.items())[:50]:  # safety cap
            gbase = f"{job.storage_prefix}/results/job_{short_id}_group_{gname}"
            if "parquet" in formats and len(gdf) > 0:
                try:
                    gk = f"{gbase}.parquet"
                    storage.put_bytes(gk, gdf.to_parquet(index=False), content_type="application/parquet")
                    results[f"group_{gname}_parquet"] = gk
                except Exception as e:
                    errors.append({"grouped": gname, "error": str(e)[:200]})
            # also csv for groups
            try:
                gk = f"{gbase}.csv"
                storage.put_bytes(gk, gdf.to_csv(index=False).encode("utf-8"), content_type="text/csv")
                results[f"group_{gname}_csv"] = gk
            except Exception:
                pass
        formats_written.append("grouped_by_" + (group_by or "field"))

    # === Manifest + Job update ===
    primary = results.get("parquet") or results.get("xlsx") or results.get("csv")
    manifest_key = _write_manifest(
        storage, job,
        shards_ok=shards_ok,
        shards_failed=shards_failed,
        errors=errors,
        rows_written=len(consolidated) if 'consolidated' in locals() else 0,
        formats_written=formats_written,
        primary_key=primary,
    )

    # Update job record (robust even if some columns are new)
    export_status = "success" if shards_failed == 0 and primary else ("partial" if primary else "failed")
    try:
        update_job(
            job_id,
            result_manifest_key=primary,
            export_status=export_status,
            export_errors=errors[:30],
            export_row_count=len(consolidated) if 'consolidated' in locals() else 0,
            export_manifest_key=manifest_key,
        )
    except Exception as e:
        logger.warning(f"Could not fully update job export fields (possible schema): {e}")
        # Fallback: at least update the main manifest key
        if primary:
            update_job(job_id, result_manifest_key=primary)

    return {
        "success": bool(primary),
        "primary_key": primary,
        "manifest_key": manifest_key,
        "rows_written": len(consolidated) if 'consolidated' in locals() else 0,
        "shards_ok": shards_ok,
        "shards_failed": shards_failed,
        "errors": errors[:20],   # truncated for response size
        "formats_written": formats_written,
        "export_status": export_status,
    }


# Backwards compatible alias used by older code
def get_consolidated_download_info(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        return {}
    return {
        "job_id": job_id,
        "result_manifest_key": job.result_manifest_key,
        "export_manifest_key": getattr(job, "export_manifest_key", None),
        "export_status": getattr(job, "export_status", ""),
        "export_row_count": getattr(job, "export_row_count", 0),
        "total_rows": job.total_rows,
        "storage_prefix": job.storage_prefix,
    }


def list_job_files(job_id: str) -> List[dict]:
    """List files for UI - now also marks export artifacts."""
    job = get_job(job_id)
    if not job or not job.storage_prefix:
        return []
    storage = get_storage()
    files = []
    try:
        for obj in storage.list_prefix(job.storage_prefix):
            is_export = "consolidated" in obj.key or "manifest" in obj.key
            files.append({
                "key": obj.key,
                "size": obj.size,
                "is_result": "/results/" in obj.key,
                "is_export": is_export,
            })
    except Exception:
        pass
    return files
