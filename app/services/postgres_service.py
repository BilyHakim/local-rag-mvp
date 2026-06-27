import re
import uuid
from dataclasses import dataclass

import asyncpg

from app.core.config import settings
from app.schemas.postgres import PostgresConnectionOverride
from app.services.chunking_service import chunk_text
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


POSTGRES_POINT_NAMESPACE = uuid.UUID("8f4b2f1a-6c3d-4e9b-a1f0-2d8e7c6b5a49")

IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class PostgresConnectionParams:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema_name: str


def resolve_connection(
    override: PostgresConnectionOverride | None = None,
) -> PostgresConnectionParams:
    return PostgresConnectionParams(
        host=(override.host if override and override.host else settings.POSTGRES_HOST),
        port=(override.port if override and override.port else settings.POSTGRES_PORT),
        database=(
            override.database
            if override and override.database
            else settings.POSTGRES_DB
        ),
        user=(override.user if override and override.user else settings.POSTGRES_USER),
        password=(
            override.password
            if override and override.password is not None
            else settings.POSTGRES_PASSWORD
        ),
        schema_name=(
            override.schema_name
            if override and override.schema_name
            else settings.POSTGRES_SCHEMA
        ),
    )


def _validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_PATTERN.match(value):
        raise ValueError(f"{label} tidak valid: {value}")

    return value


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


async def _connect(params: PostgresConnectionParams) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=params.host,
        port=params.port,
        database=params.database,
        user=params.user,
        password=params.password,
    )


def _format_cell(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _format_row(
    *,
    database: str,
    schema_name: str,
    table: str,
    row: dict[str, object],
    row_key: str,
) -> str:
    pairs = []

    for column, value in row.items():
        cell = _format_cell(value)

        if cell:
            pairs.append(f"{column}: {cell}")

    if not pairs:
        return ""

    return (
        f"Database: {database}; Schema: {schema_name}; Table: {table}; "
        f"Row ID: {row_key}; "
        + "; ".join(pairs)
    )


def _build_row_key(
    *,
    primary_key_columns: list[str],
    row: dict[str, object],
    row_index: int,
) -> str:
    if primary_key_columns:
        values = [_format_cell(row.get(column)) for column in primary_key_columns]

        if all(values):
            return "|".join(values)

    return str(row_index)


def _postgres_point_id(
    *,
    database: str,
    table: str,
    row_key: str,
    chunk_index: int,
) -> str:
    key = f"{database}:{table}:{row_key}:{chunk_index}"
    return str(uuid.uuid5(POSTGRES_POINT_NAMESPACE, key))


async def test_connection(
    override: PostgresConnectionOverride | None = None,
) -> dict:
    params = resolve_connection(override)
    connection = await _connect(params)

    try:
        postgres_version = await connection.fetchval("SELECT version()")
    finally:
        await connection.close()

    return {
        "ok": True,
        "database": params.database,
        "schema_name": params.schema_name,
        "host": params.host,
        "port": params.port,
        "postgres_version": postgres_version,
    }


async def list_tables(
    override: PostgresConnectionOverride | None = None,
) -> dict:
    params = resolve_connection(override)
    schema_name = _validate_identifier(params.schema_name, "Schema")
    connection = await _connect(params)

    try:
        rows = await connection.fetch(
            """
            SELECT
                t.table_name,
                COALESCE(c.reltuples::bigint, 0) AS row_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_namespace n
                ON n.nspname = t.table_schema
            LEFT JOIN pg_class c
                ON c.relname = t.table_name
                AND c.relnamespace = n.oid
            WHERE t.table_schema = $1
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
            """,
            schema_name,
        )
    finally:
        await connection.close()

    return {
        "database": params.database,
        "schema_name": params.schema_name,
        "tables": [
            {
                "name": row["table_name"],
                "row_estimate": int(row["row_estimate"] or 0),
            }
            for row in rows
        ],
    }


async def _get_primary_key_columns(
    connection: asyncpg.Connection,
    *,
    schema_name: str,
    table: str,
) -> list[str]:
    rows = await connection.fetch(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
            AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = $1
          AND tc.table_name = $2
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        schema_name,
        table,
    )

    return [row["column_name"] for row in rows]


async def _fetch_table_rows(
    connection: asyncpg.Connection,
    *,
    schema_name: str,
    table: str,
    limit: int | None,
) -> list[dict[str, object]]:
    validated_schema = _validate_identifier(schema_name, "Schema")
    validated_table = _validate_identifier(table, "Table")

    query = (
        f"SELECT * FROM {_quote_identifier(validated_schema)}."
        f"{_quote_identifier(validated_table)}"
    )

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    rows = await connection.fetch(query)
    return [dict(row) for row in rows]


async def sync_tables(
    *,
    tables: list[str],
    override: PostgresConnectionOverride | None = None,
    limit_per_table: int | None = None,
) -> dict:
    params = resolve_connection(override)
    schema_name = _validate_identifier(params.schema_name, "Schema")
    connection = await _connect(params)

    results = []
    total_indexed_chunks = 0

    try:
        for table in tables:
            validated_table = _validate_identifier(table, "Table")
            primary_key_columns = await _get_primary_key_columns(
                connection,
                schema_name=schema_name,
                table=validated_table,
            )
            rows = await _fetch_table_rows(
                connection,
                schema_name=schema_name,
                table=validated_table,
                limit=limit_per_table,
            )

            indexed_chunks = 0

            for row_index, row in enumerate(rows, start=1):
                row_key = _build_row_key(
                    primary_key_columns=primary_key_columns,
                    row=row,
                    row_index=row_index,
                )
                row_text = _format_row(
                    database=params.database,
                    schema_name=params.schema_name,
                    table=validated_table,
                    row=row,
                    row_key=row_key,
                )

                if not row_text:
                    continue

                chunks = chunk_text(row_text)

                for chunk_index, chunk in enumerate(chunks):
                    vector = await ollama_service.embed(chunk)
                    point_id = _postgres_point_id(
                        database=params.database,
                        table=validated_table,
                        row_key=row_key,
                        chunk_index=chunk_index,
                    )

                    qdrant_service.upsert_text(
                        vector=vector,
                        text=chunk,
                        source_name=f"{params.database}.{validated_table}",
                        metadata={
                            "source_type": "postgres",
                            "database": params.database,
                            "schema_name": params.schema_name,
                            "table_name": validated_table,
                            "row_key": row_key,
                            "chunk_index": chunk_index,
                            "file_format": "postgres",
                        },
                        point_id=point_id,
                    )
                    indexed_chunks += 1

            results.append({
                "table": validated_table,
                "rows_fetched": len(rows),
                "indexed_chunks": indexed_chunks,
            })
            total_indexed_chunks += indexed_chunks
    finally:
        await connection.close()

    return {
        "database": params.database,
        "schema_name": params.schema_name,
        "results": results,
        "total_indexed_chunks": total_indexed_chunks,
    }
