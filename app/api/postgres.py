from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.postgres import (
    PostgresConnectionRequest,
    PostgresConnectionResponse,
    PostgresSyncRequest,
    PostgresSyncResponse,
    PostgresTableInfo,
    PostgresTableSyncResult,
    PostgresTablesResponse,
)
from app.services.postgres_service import (
    list_tables,
    sync_tables,
    test_connection,
)


router = APIRouter()


def _ensure_postgres_enabled() -> None:
    if not settings.POSTGRES_ENABLED:
        raise HTTPException(
            status_code=503,
            detail=(
                "Integrasi PostgreSQL belum aktif. "
                "Set POSTGRES_ENABLED=true di .env terlebih dahulu."
            ),
        )


@router.post("/postgres/test-connection", response_model=PostgresConnectionResponse)
async def postgres_test_connection(payload: PostgresConnectionRequest):
    _ensure_postgres_enabled()

    try:
        result = await test_connection(payload.connection)
        return PostgresConnectionResponse(**result)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal terhubung ke PostgreSQL: {str(exc)}",
        )


@router.post("/postgres/tables", response_model=PostgresTablesResponse)
async def postgres_list_tables(payload: PostgresConnectionRequest):
    _ensure_postgres_enabled()

    try:
        result = await list_tables(payload.connection)
        return PostgresTablesResponse(
            database=result["database"],
            schema_name=result["schema_name"],
            tables=[PostgresTableInfo(**table) for table in result["tables"]],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil daftar tabel: {str(exc)}",
        )


@router.post("/postgres/sync", response_model=PostgresSyncResponse)
async def postgres_sync_tables(payload: PostgresSyncRequest):
    _ensure_postgres_enabled()

    try:
        result = await sync_tables(
            tables=payload.tables,
            override=payload.connection,
            limit_per_table=payload.limit_per_table,
        )

        return PostgresSyncResponse(
            database=result["database"],
            schema_name=result["schema_name"],
            results=[
                PostgresTableSyncResult(**item) for item in result["results"]
            ],
            total_indexed_chunks=result["total_indexed_chunks"],
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal sync PostgreSQL ke knowledge base: {str(exc)}",
        )
