from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, unquote


@dataclass(frozen=True)
class DatabaseArticle:
    article_id: int
    title: str
    abstract: str


def _connection_kwargs_from_database_url(database_url: str) -> dict[str, Any]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"mysql", "mysql+pymysql", "mariadb", "mariadb+pymysql"}:
        raise ValueError("DATABASE_URL must use mysql/mariadb scheme")

    if not parsed.hostname or not parsed.path:
        raise ValueError("DATABASE_URL is missing host or database name")

    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/"),
        "charset": "utf8mb4",
        "autocommit": True,
    }


def fetch_articles_from_mysql(
    *,
    database_url: str,
    table: str,
    id_column: str,
    title_column: str,
    abstract_column: str,
    limit: int | None,
    require_non_empty_abstract: bool = True,
) -> list[dict]:
    import pymysql

    for identifier in (table, id_column, title_column, abstract_column):
        if not identifier.replace("_", "").replace(".", "").isalnum():
            raise ValueError(f"Unsafe SQL identifier: {identifier}")

    kwargs = _connection_kwargs_from_database_url(database_url)
    kwargs["cursorclass"] = pymysql.cursors.DictCursor
    query = (
        f"SELECT {id_column} AS article_id, {title_column} AS title, "
        f"{abstract_column} AS abstract FROM {table}"
    )
    if require_non_empty_abstract:
        query += f" WHERE {abstract_column} IS NOT NULL AND {abstract_column} != ''"
    params: tuple = ()
    if limit is not None:
        query += " LIMIT %s"
        params = (limit,)

    with pymysql.connect(**kwargs) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [DatabaseArticle(**row).__dict__ for row in rows]
