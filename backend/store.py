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
        self.path = root.resolve() / ".demo" / "parcel.sqlite3"

    @contextmanager
    def transaction(self, *, write=False, new=False):
        # mode=rw ensures a request never silently recreates a missing database.
        uri = self.path.absolute().as_uri() + "?mode=rw"
        with closing(sqlite3.connect(uri, uri=True, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            with db:
                if not new:
                    self._check_owner(db)
                yield db

    def initialize(self, *, reset=False):
        if self.path.resolve() != self.path or (self.path.exists() and self.path.stat().st_nlink != 1):
            raise ValueError("Refusing a linked demo database or directory.")
        self.path.parent.mkdir(exist_ok=True)
        try:
            self.path.touch(exist_ok=False)
        except FileExistsError:
            # Probe without creating journals or recovering an unrelated database.
            uri = self.path.as_uri() + "?mode=ro&immutable=1"
            with closing(sqlite3.connect(uri, uri=True)) as db:
                self._check_owner(db)
            if reset:
                with self.transaction(write=True) as db:
                    db.execute("DELETE FROM events")
                    db.execute("DELETE FROM orders")
                    db.execute("DELETE FROM inventory")
                    self._seed(db)
            return
        with self.transaction(write=True, new=True) as db:
            db.execute(f"PRAGMA application_id = {APP_ID}")
            db.execute("""CREATE TABLE inventory (
                sku TEXT PRIMARY KEY, name TEXT NOT NULL, on_hand INTEGER NOT NULL,
                reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved BETWEEN 0 AND on_hand)
            )""")
            db.execute("""CREATE TABLE orders (
                id TEXT PRIMARY KEY, sku TEXT NOT NULL REFERENCES inventory(sku),
                quantity INTEGER NOT NULL CHECK (quantity > 0)
            )""")
            db.execute("""CREATE TABLE events (
                seq INTEGER PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
                status TEXT NOT NULL, at TEXT NOT NULL, UNIQUE(order_id, status)
            )""")
            self._seed(db)

    @staticmethod
    def _check_owner(db):
        if db.execute("PRAGMA application_id").fetchone()[0] != APP_ID:
            raise ValueError("Not a Parcel Workbench demo database; refusing to modify it.")

    @staticmethod
    def _seed(db):
        db.executemany("INSERT INTO inventory(sku, name, on_hand) VALUES(?, ?, ?)", FIXTURES)

    def inventory(self, query):
        with self.transaction() as db:
            rows = db.execute("""SELECT sku, name, on_hand, reserved, on_hand - reserved AS available
                FROM inventory WHERE instr(lower(sku), lower(:q)) OR instr(lower(name), lower(:q))
                ORDER BY sku""", {"q": query.strip()})
            return [dict(row) for row in rows]

    @staticmethod
    def _order(db, order_id):
        line = db.execute("""SELECT sku, name, quantity FROM orders JOIN inventory USING (sku)
            WHERE id = ?""", (order_id,)).fetchone()
        if line is None:
            raise NotFound("Order not found.")
        events = [dict(row) for row in db.execute(
            "SELECT status, at FROM events WHERE order_id = ? ORDER BY seq", (order_id,)
        )]
        return {"id": order_id, "status": events[-1]["status"], "lines": [dict(line)], "events": events}

    @staticmethod
    def _event(db, order_id, status):
        at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        db.execute("INSERT INTO events(order_id, status, at) VALUES (?, ?, ?)", (order_id, status, at))

    def ask_snapshot(self, order_id):
        """Read only the six fixture stock counts and, if requested, one exact order."""
        with self.transaction() as db:
            catalog = []
            for sku, name, _initial in FIXTURES:
                item = db.execute("SELECT on_hand, reserved FROM inventory WHERE sku = ?", (sku,)).fetchone()
                if item is not None:
                    catalog.append({"sku": sku, "name": name, **dict(item),
                                    "available": item["on_hand"] - item["reserved"]})
            order = self._order(db, order_id) if order_id is not None else None
            if order:
                line = order["lines"][0]
                names = {item["sku"]: item["name"] for item in catalog}
                if line["sku"] not in names:
                    raise NotFound("Not a demo catalog order.")
                line["name"] = names[line["sku"]]
            return {"inventory": catalog, "order": order}

    def lookup(self, order_id):
        with self.transaction() as db:
            return self._order(db, order_id)

    def advance(self, order_id, expected_status):
        with self.transaction(write=True) as db:
            order = self._order(db, order_id)
            if order["status"] != expected_status:
                raise Conflict(f"Order is {order['status']}; refresh before advancing.")
            next_status = {"reserved": "packed", "packed": "shipped", "shipped": "delivered"}.get(expected_status)
            if next_status is None:
                raise Conflict("Delivered orders cannot advance.")
            if next_status == "shipped":
                line = order["lines"][0]
                db.execute("""UPDATE inventory SET on_hand = on_hand - :quantity,
                    reserved = reserved - :quantity WHERE sku = :sku""", line)
            self._event(db, order_id, next_status)
            return self._order(db, order_id)

    def reserve(self, sku, quantity):
        with self.transaction(write=True) as db:
            item = db.execute("SELECT on_hand - reserved FROM inventory WHERE sku = ?", (sku,)).fetchone()
            if item is None:
                raise NotFound("SKU not found.")
            if quantity > item[0]:
                raise Conflict("Not enough available stock.")
            db.execute("UPDATE inventory SET reserved = reserved + ? WHERE sku = ?", (quantity, sku))
            order_id = "PW-" + uuid4().hex
            db.execute("INSERT INTO orders(id, sku, quantity) VALUES (?, ?, ?)", (order_id, sku, quantity))
            self._event(db, order_id, "reserved")
            return self._order(db, order_id)
