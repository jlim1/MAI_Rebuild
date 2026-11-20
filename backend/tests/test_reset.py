import sqlite3
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend import reset
from backend.app import create_app


class ResetTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.db_path = self.root / ".demo" / "parcel.sqlite3"

    def run_reset(self, *args):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return reset.main(args, root=self.root)

    def test_reset_only_restores_demo_data(self):
        self.assertEqual(self.run_reset(), 0)
        note = self.db_path.with_name("keep.txt")
        note.write_text("keep me", encoding="utf-8")
        with TestClient(create_app(self.root)) as client:
            original = client.get("/api/inventory").json()
            order = client.post("/api/orders", json={"sku": "ARC-01", "quantity": 2}).json()
            self.assertEqual(self.run_reset(), 0)
            self.assertEqual(client.get("/api/orders/" + order["id"]).status_code, 404)
            self.assertEqual(client.get("/api/inventory").json(), original)
        self.assertEqual(note.read_text(encoding="utf-8"), "keep me")

    def test_unmarked_database_is_not_changed(self):
        self.db_path.parent.mkdir()
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("CREATE TABLE inventory (note TEXT)")
            conn.execute("INSERT INTO inventory VALUES ('unrelated stock notes')")
        before = self.db_path.read_bytes()
        self.assertNotEqual(self.run_reset(), 0)
        self.assertEqual(self.db_path.read_bytes(), before)
        self.db_path.write_bytes(b"")
        self.assertNotEqual(self.run_reset(), 0)
        self.assertEqual(self.db_path.read_bytes(), b"")

    def test_reset_does_not_accept_paths(self):
        self.assertNotEqual(self.run_reset(str(self.root / "other.sqlite3")), 0)
        self.assertFalse(self.db_path.exists())
        self.assertFalse((self.root / "other.sqlite3").exists())

    def test_reset_refuses_a_link_to_another_demo(self):
        other = self.root / "other-demo"
        other.mkdir()
        with TestClient(create_app(other)) as client:
            order = client.post("/api/orders", json={"sku": "ARC-01", "quantity": 1}).json()
            self.db_path.parent.mkdir()
            try:
                self.db_path.hardlink_to(other / ".demo" / "parcel.sqlite3")
            except OSError as exc:
                self.skipTest(f"Hard links unavailable: {exc}")
            self.assertNotEqual(self.run_reset(), 0)
            self.assertEqual(client.get("/api/orders/" + order["id"]).json(), order)
