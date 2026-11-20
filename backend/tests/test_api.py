import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier

from fastapi.testclient import TestClient

from backend.app import create_app


class ParcelApiTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.runtime = ExitStack()
        self.addCleanup(self.runtime.close)
        self.client = self.runtime.enter_context(TestClient(create_app(self.root)))

    def test_inventory_can_be_found_by_sku_or_name(self):
        lamp = {"sku": "ARC-01", "name": "Arc lamp", "on_hand": 2,
                "reserved": 0, "available": 2}
        for term in ("arc-0", "C LaM"):
            response = self.client.get("/api/inventory", params={"q": term})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [lamp])
        self.assertEqual(self.client.get("/api/inventory?q=no-such-item").json(), [])

    def post_reserve(self, quantity=1):
        return self.client.post("/api/orders", json={"sku": "ARC-01", "quantity": quantity})

    def get_stock(self, client=None):
        row = (client or self.client).get("/api/inventory?q=ARC-01").json()[0]
        return row["on_hand"], row["reserved"], row["available"]

    def test_reservation_is_retrievable_by_exact_id_after_restart(self):
        response = self.post_reserve(2)
        self.assertEqual(response.status_code, 201)
        order = response.json()
        self.assertEqual(set(order), {"id", "status", "lines", "events"})
        self.assertTrue(order["id"])
        self.assertEqual(order["status"], "reserved")
        self.assertEqual(order["lines"], [{"sku": "ARC-01", "name": "Arc lamp", "quantity": 2}])
        self.assertEqual([event["status"] for event in order["events"]], ["reserved"])
        self.assertEqual(datetime.fromisoformat(order["events"][0]["at"]).utcoffset(), timedelta(0))
        path = "/api/orders/" + order["id"]
        self.runtime.close()
        with TestClient(create_app(self.root)) as restarted:
            self.assertEqual(restarted.get(path).json(), order)
            self.assertEqual(restarted.get(path[:-1]).status_code, 404)
            self.assertEqual(self.get_stock(restarted), (2, 2, 0))

    def post_advance(self, order_id, expected):
        return self.client.post(f"/api/orders/{order_id}/advance", json={"expected_status": expected})

    def assertConflict(self, response):
        self.assertEqual(response.status_code, 409)
        self.assertIsInstance(response.json()["detail"], str)

    def test_lifecycle_consumes_stock_only_at_shipment(self):
        order = self.post_reserve().json()
        history = ["reserved"]
        for status, stock in [("packed", (2, 1, 1)), ("shipped", (1, 0, 1)), ("delivered", (1, 0, 1))]:
            previous = order
            response = self.post_advance(previous["id"], previous["status"])
            self.assertEqual(response.status_code, 200)
            order = response.json()
            history.append(status)
            self.assertEqual(order["status"], status)
            self.assertEqual(order["events"][:-1], previous["events"])
            self.assertEqual([e["status"] for e in order["events"]], history)
            times = [datetime.fromisoformat(e["at"]) for e in order["events"]]
            self.assertEqual(times, sorted(times))
            self.assertTrue(all(t.utcoffset() == timedelta(0) for t in times))
            self.assertConflict(self.post_advance(order["id"], previous["status"]))
            self.assertEqual(self.get_stock(), stock)
            self.assertEqual(self.client.get("/api/orders/" + order["id"]).json(), order)
        self.assertConflict(self.post_advance(order["id"], "delivered"))
        self.assertEqual(self.client.get("/api/orders/" + order["id"]).json(), order)
        self.assertEqual(self.get_stock(), (1, 0, 1))

    @staticmethod
    def run_race(fn):
        start = Barrier(2)

        def contender():
            start.wait(timeout=5)
            return fn()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            return sorted((job.result() for job in futures), key=lambda r: r.status_code)

    def test_competing_reservations_and_shipments_have_one_winner(self):
        winner, loser = self.run_race(lambda: self.post_reserve(2))
        self.assertEqual(winner.status_code, 201)
        self.assertConflict(loser)
        self.assertEqual(self.get_stock(), (2, 2, 0))
        order_id = winner.json()["id"]
        self.assertEqual(self.post_advance(order_id, "reserved").status_code, 200)
        shipped, stale = self.run_race(lambda: self.post_advance(order_id, "packed"))
        self.assertEqual(shipped.status_code, 200)
        self.assertConflict(stale)
        self.assertEqual(self.get_stock(), (0, 0, 0))
        persisted = self.client.get("/api/orders/" + order_id).json()
        self.assertEqual(persisted, shipped.json())
        self.assertEqual([e["status"] for e in persisted["events"]], ["reserved", "packed", "shipped"])

    def test_invalid_reservations_do_not_change_stock(self):
        for quantity in (0, -1, True, 1.5, "1", 2**63):
            with self.subTest(quantity=quantity):
                self.assertEqual(self.post_reserve(quantity).status_code, 422)
        unknown = self.client.post("/api/orders", json={"sku": "absent", "quantity": 1})
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(self.get_stock(), (2, 0, 2))

    def test_built_ui_does_not_shadow_api(self):
        dist = self.root / "frontend" / "dist"
        (dist / "api").mkdir(parents=True)
        (dist / "index.html").write_text("Parcel local UI", encoding="utf-8")
        (dist / "api" / "health").write_text("Not API health", encoding="utf-8")
        with TestClient(create_app(self.root)) as client:
            self.assertEqual(client.get("/").text, "Parcel local UI")
            self.assertEqual(client.get("/api/health").json(), {"status": "ok"})
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/redoc").status_code, 404)
