"""Administracion sin imprimir credenciales: python -m bootstrap.manage check."""

import argparse
import json
import os

import psycopg

from bootstrap.database import Database, SchemaError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "migrate", "summary"])
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL sin configurar")
        return 1
    database = Database(url)
    try:
        if args.action == "migrate":
            database.migrate()
        database.check()
        print(json.dumps(database.summary() if args.action == "summary" else {"database": "ok"}))
    except (psycopg.Error, SchemaError, ValueError, OSError):
        print("No se pudo verificar PostgreSQL. Revisar configuracion; detalles privados omitidos.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
