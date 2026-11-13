"""Integration #1: customer lookup (read-only). Used ONLY by the deterministic rules, never sent to the LLM.

SqliteCRM is the default: a real database file (data/integrations/crm.sqlite) built from the synthetic customer
export on first run, queried with SQL per lookup. A production CRM (HubSpot, Salesforce...) would implement the
same two methods.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Protocol

COLUMNS = {  # name -> SQL type
    "customer_id": "TEXT PRIMARY KEY", "company_name": "TEXT NOT NULL", "trade": "TEXT", "plan_tier": "TEXT NOT NULL",
    "seat_count": "INTEGER", "contract_renewal_date": "TEXT", "open_incidents": "INTEGER NOT NULL DEFAULT 0",
    "account_health": "TEXT NOT NULL", "onboarding_in_progress": "INTEGER NOT NULL DEFAULT 0",
    "primary_contact_domain": "TEXT",
}
_BOOL = {"onboarding_in_progress"}
_seed_lock = threading.Lock()


class CRMError(RuntimeError):
    """Customer data could not be read. The message says what to do."""


class CRM(Protocol):
    name: str

    def get(self, customer_id: str) -> Optional[dict]: ...

    def all(self) -> dict[str, dict]: ...


def _load_json(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))["records"]
    except FileNotFoundError as e:
        raise CRMError(f"Customer file not found: {path}. Restore it from the repo (git checkout -- {path.name}).") from e
    except (json.JSONDecodeError, KeyError) as e:
        raise CRMError(f"Customer file {path} is not valid ({e}). Restore it from the repo.") from e


class JsonCRM:
    name = "json"

    def __init__(self, path: Path):
        self._records = {c["customer_id"]: c for c in _load_json(path)}

    def get(self, customer_id: str) -> Optional[dict]:
        return self._records.get(customer_id)

    def all(self) -> dict[str, dict]:
        return dict(self._records)


class SqliteCRM:
    name = "sqlite"

    def __init__(self, db_path: Path, seed_json: Optional[Path] = None):
        self.db_path = Path(db_path)
        with _seed_lock:
            if not self.db_path.exists():
                if seed_json is None:
                    raise CRMError(f"Customer database {self.db_path} does not exist.")
                self._create(_load_json(seed_json))

    def _connect(self) -> sqlite3.Connection:
        try:
            con = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error as e:
            raise CRMError(f"Could not open the customer database {self.db_path} ({e}). Delete it; it is rebuilt "
                           "automatically on the next run.") from e
        con.row_factory = sqlite3.Row
        return con

    def _create(self, records: list[dict]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.db_path.with_suffix(".building")
        tmp.unlink(missing_ok=True)
        con = sqlite3.connect(tmp)
        try:
            con.execute(f"CREATE TABLE customers ({', '.join(f'{k} {t}' for k, t in COLUMNS.items())})")
            con.executemany(f"INSERT INTO customers VALUES ({', '.join('?' * len(COLUMNS))})",
                            [tuple(int(r[k]) if k in _BOOL else r.get(k) for k in COLUMNS) for r in records])
            con.commit()
        finally:
            con.close()
        tmp.replace(self.db_path)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for k in _BOOL:
            d[k] = bool(d[k])
        return d

    def _query(self, sql: str, args: tuple = ()) -> list[dict]:
        con = self._connect()
        try:
            return [self._row(r) for r in con.execute(sql, args)]
        except sqlite3.Error as e:
            raise CRMError(f"Customer database query failed ({e}). Delete {self.db_path.name}; it is rebuilt "
                           "automatically on the next run.") from e
        finally:
            con.close()

    def get(self, customer_id: str) -> Optional[dict]:
        rows = self._query("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        return rows[0] if rows else None

    def all(self) -> dict[str, dict]:
        return {r["customer_id"]: r for r in self._query("SELECT * FROM customers ORDER BY customer_id")}
