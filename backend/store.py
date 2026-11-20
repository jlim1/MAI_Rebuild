"""SQLite storage. Each request works in a single connection and transaction."""

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
APP_ID = int.from_bytes(b"PWK1", "big")
FIXTURES = (
    ("ARC-01", "Arc lamp", 2),
    ("BOOM-02", "Telescoping boom", 4),
    ("CASE-03", "Field recorder case", 7),
    ("LEVEL-04", "Pocket level", 5),
    ("REEL-05", "Signal cable reel", 3),
    ("STAND-06", "Folding lens stand", 6),
)


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.db_path = root.resolve() / ".demo" / "parcel.sqlite3"

    @contextmanager
    def transaction(self, *, write=False, is_new=False):
        # mode=rw ensures a request never silently recreates a missing database.
        db_uri = self.db_path.absolute().as_uri() + "?mode=rw"
        with closing(sqlite3.connect(db_uri, uri=True, isolation_level=None)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            with conn:
                if not is_new:
                    self._check_owner(conn)
                yield conn

    def initialize(self, *, reset=False):
        if self.db_path.resolve() != self.db_path or (self.db_path.exists() and self.db_path.stat().st_nlink != 1):
            raise ValueError("Refusing a linked demo database or directory.")
        self.db_path.parent.mkdir(exist_ok=True)
        try:
            self.db_path.touch(exist_ok=False)
        except FileExistsError:
            # Probe without creating journals or recovering an unrelated database.
            db_uri = self.db_path.as_uri() + "?mode=ro&immutable=1"
            with closing(sqlite3.connect(db_uri, uri=True)) as conn:
                self._check_owner(conn)
            if reset:
                with self.transaction(write=True) as conn:
                    conn.execute("DELETE FROM events")
                    conn.execute("DELETE FROM orders")
                    conn.execute("DELETE FROM inventory")
                    self._seed_inventory(conn)
            return
        with self.transaction(write=True, is_new=True) as conn:
            conn.execute(f"PRAGMA application_id = {APP_ID}")
            conn.execute("""CREATE TABLE inventory (
                sku TEXT PRIMARY KEY, name TEXT NOT NULL, on_hand INTEGER NOT NULL,
                reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved BETWEEN 0 AND on_hand)
            )""")
            conn.execute("""CREATE TABLE orders (
                id TEXT PRIMARY KEY, sku TEXT NOT NULL REFERENCES inventory(sku),
                quantity INTEGER NOT NULL CHECK (quantity > 0)
            )""")
            conn.execute("""CREATE TABLE events (
                seq INTEGER PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
                status TEXT NOT NULL, at TEXT NOT NULL, UNIQUE(order_id, status)
            )""")
            self._seed_inventory(conn)

    @staticmethod
    def _check_owner(conn):
        if conn.execute("PRAGMA application_id").fetchone()[0] != APP_ID:
            raise ValueError("Not a Parcel Workbench demo database; refusing to modify it.")

    @staticmethod
    def _seed_inventory(conn):
        conn.executemany("INSERT INTO inventory(sku, name, on_hand) VALUES(?, ?, ?)", FIXTURES)

    def get_inventory(self, query):
        with self.transaction() as conn:
            rows = conn.execute("""SELECT sku, name, on_hand, reserved, on_hand - reserved AS available
                FROM inventory WHERE instr(lower(sku), lower(:q)) OR instr(lower(name), lower(:q))
                ORDER BY sku""", {"q": query.strip()})
            return [dict(row) for row in rows]

    @staticmethod
    def _get_order(conn, order_id):
        line = conn.execute("""SELECT sku, name, quantity FROM orders JOIN inventory USING (sku)
            WHERE id = ?""", (order_id,)).fetchone()
        if line is None:
            raise NotFound("Order not found.")
        events = [dict(row) for row in conn.execute(
            "SELECT status, at FROM events WHERE order_id = ? ORDER BY seq", (order_id,)
        )]
        return {"id": order_id, "status": events[-1]["status"], "lines": [dict(line)], "events": events}

    @staticmethod
    def _add_event(conn, order_id, status):
        at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        conn.execute("INSERT INTO events(order_id, status, at) VALUES (?, ?, ?)", (order_id, status, at))

    def get_ask_snapshot(self, order_id):
        """Read only the six fixture stock counts and, if requested, one exact order."""
        with self.transaction() as conn:
            catalog = []
            for sku, name, _initial in FIXTURES:
                item = conn.execute("SELECT on_hand, reserved FROM inventory WHERE sku = ?", (sku,)).fetchone()
                if item is not None:
                    catalog.append({"sku": sku, "name": name, **dict(item),
                                    "available": item["on_hand"] - item["reserved"]})
            order = self._get_order(conn, order_id) if order_id is not None else None
            if order:
                line = order["lines"][0]
                name_by_sku = {item["sku"]: item["name"] for item in catalog}
                if line["sku"] not in name_by_sku:
                    raise NotFound("Not a demo catalog order.")
                line["name"] = name_by_sku[line["sku"]]
            return {"inventory": catalog, "order": order}

    def lookup_order(self, order_id):
        with self.transaction() as conn:
            return self._get_order(conn, order_id)

    def advance_order(self, order_id, expected_status):
        with self.transaction(write=True) as conn:
            order = self._get_order(conn, order_id)
            if order["status"] != expected_status:
                raise Conflict(f"Order is {order['status']}; refresh before advancing.")
            next_status = {"reserved": "packed", "packed": "shipped", "shipped": "delivered"}.get(expected_status)
            if next_status is None:
                raise Conflict("Delivered orders cannot advance.")
            if next_status == "shipped":
                line = order["lines"][0]
                conn.execute("""UPDATE inventory SET on_hand = on_hand - :quantity,
                    reserved = reserved - :quantity WHERE sku = :sku""", line)
            self._add_event(conn, order_id, next_status)
            return self._get_order(conn, order_id)

    def reserve_stock(self, sku, quantity):
        with self.transaction(write=True) as conn:
            item = conn.execute("SELECT on_hand - reserved FROM inventory WHERE sku = ?", (sku,)).fetchone()
            if item is None:
                raise NotFound("SKU not found.")
            if quantity > item[0]:
                raise Conflict("Not enough available stock.")
            conn.execute("UPDATE inventory SET reserved = reserved + ? WHERE sku = ?", (quantity, sku))
            order_id = "PW-" + uuid4().hex
            conn.execute("INSERT INTO orders(id, sku, quantity) VALUES (?, ?, ?)", (order_id, sku, quantity))
            self._add_event(conn, order_id, "reserved")
            return self._get_order(conn, order_id)
