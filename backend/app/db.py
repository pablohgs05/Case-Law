from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=settings.database_pool_size,
    kwargs={"row_factory": dict_row},
    open=False,
)


@contextmanager
def connection() -> Iterator[Connection[DictRow]]:
    with pool.connection() as conn:
        yield conn


def get_connection() -> Iterator[Connection[DictRow]]:
    with connection() as conn:
        yield conn
