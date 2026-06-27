from pydantic import BaseModel, Field


class PostgresConnectionOverride(BaseModel):
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = None
    user: str | None = None
    password: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


class PostgresConnectionRequest(BaseModel):
    connection: PostgresConnectionOverride | None = None


class PostgresConnectionResponse(BaseModel):
    ok: bool
    database: str
    schema_name: str
    host: str
    port: int
    postgres_version: str | None = None
    message: str | None = None


class PostgresTableInfo(BaseModel):
    name: str
    row_estimate: int | None = None


class PostgresTablesResponse(BaseModel):
    database: str
    schema_name: str
    tables: list[PostgresTableInfo]


class PostgresSyncRequest(BaseModel):
    tables: list[str] = Field(..., min_length=1)
    connection: PostgresConnectionOverride | None = None
    limit_per_table: int | None = Field(default=None, ge=1, le=100_000)


class PostgresTableSyncResult(BaseModel):
    table: str
    rows_fetched: int
    indexed_chunks: int


class PostgresSyncResponse(BaseModel):
    database: str
    schema_name: str
    results: list[PostgresTableSyncResult]
    total_indexed_chunks: int
