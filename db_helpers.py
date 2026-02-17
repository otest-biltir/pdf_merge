from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, Tuple

try:  # pragma: no cover - optional dependency
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover - optional dependency
    psycopg2 = None  # type: ignore
    RealDictCursor = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import psycopg  # type: ignore
    from psycopg.rows import dict_row  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore


@dataclass(frozen=True)
class TableConfig:
    name: str
    table: str


@dataclass(frozen=True)
class DataSourceConfig:
    name: str
    host: str
    port: int
    username: str
    password: str
    database: str
    tables: Tuple[TableConfig, ...]


_PREDEFINED_DATA_SOURCES: Tuple[DataSourceConfig, ...] = (
    DataSourceConfig(
        name="docker_psql_container",
        host="144.122.233.88",
        port=32786,
        username="postgres",
        password="B12345+-",
        database="otest_all_tests",
        tables=(
            TableConfig(name="Dynamic Tests", table="dynamic_tests"),
            TableConfig(name="Linear Tests", table="linear_tests"),
            TableConfig(name="Static Tests", table="static_tests"),
        ),
    ),
)

_DATA_SOURCES: Sequence[DataSourceConfig] | None = None


class DatabaseLookupError(RuntimeError):
    """Raised when test information cannot be fetched from DB."""


def _load_data_sources() -> Sequence[DataSourceConfig]:
    global _DATA_SOURCES
    if _DATA_SOURCES is not None:
        return _DATA_SOURCES
    _DATA_SOURCES = _PREDEFINED_DATA_SOURCES
    return _DATA_SOURCES


def iter_test_sources() -> Iterable[TableConfig]:
    for source in _load_data_sources():
        yield from source.tables


def _find_source_and_table(source_name: str) -> tuple[DataSourceConfig, TableConfig]:
    for source in _load_data_sources():
        for table in source.tables:
            if table.name == source_name:
                return source, table
    raise DatabaseLookupError(f"Test kaynağı bulunamadı: {source_name}")


def _create_connection(*, host: str, port: int, user: str, password: str, database: str):
    if psycopg2 is not None and RealDictCursor is not None:
        return psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=database,
            cursor_factory=RealDictCursor,
        )

    if psycopg is not None and dict_row is not None:  # pragma: no cover - optional driver
        return psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=database,
            row_factory=dict_row,
        )

    raise DatabaseLookupError(
        "Veritabanına bağlanmak için psycopg2 veya psycopg paketlerinden en az biri gerekli. "
        "Uygulama açılışta requirements.txt kurulumunu dener; başarısız olduysa manuel kurulum yapın."
    )


@contextmanager
def get_connection(source: DataSourceConfig):
    conn = _create_connection(
        host=source.host,
        port=source.port,
        user=source.username,
        password=source.password,
        database=source.database,
    )
    try:
        yield conn
    finally:
        conn.close()


def fetch_test_numbers(source_name: str) -> list[str]:
    source, table = _find_source_and_table(source_name)

    query = f"SELECT test_no FROM {table.table} ORDER BY test_no"
    with get_connection(source) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall() or []

    test_numbers: list[str] = []
    for row in rows:
        value = row["test_no"] if isinstance(row, dict) else row[0]
        if value is not None:
            test_numbers.append(str(value))
    return test_numbers


def get_main_path_for_test(test_no: str, source_name: str) -> str:
    """Return `main_path` for a given `test_no` and table display name."""

    source, table = _find_source_and_table(source_name)

    query = f"SELECT main_path FROM {table.table} WHERE test_no = %s LIMIT 1"
    with get_connection(source) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (test_no,))
            row = cur.fetchone()

    if not row:
        raise DatabaseLookupError(
            f"'{source_name}' kaynağında '{test_no}' test numarası bulunamadı."
        )

    main_path = row["main_path"] if isinstance(row, dict) else row[0]
    if not main_path:
        raise DatabaseLookupError(f"'{test_no}' testi için main_path boş.")

    return str(main_path)
