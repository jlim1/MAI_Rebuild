import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app


class AskTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        root = Path(stack.enter_context(TemporaryDirectory(dir=Path(__file__).parent)))
        self.env = {"OPENAI_API_KEY": "fake-openai", "ANTHROPIC_API_KEY": "fake-anthropic"}
        self.connect = stack.enter_context(patch("http.client.HTTPSConnection", autospec=True))
        self.app = create_app(root, ask_env=self.env)
        self.client = stack.enter_context(TestClient(
            self.app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 55000)
        ))

    def test_discovery_is_configuration_only(self):
        for flag in (True, False):
            if not flag:
                self.env["OPENAI_API_KEY"] = "   "
            self.assertEqual(self.client.get("/api/ask/providers").json(), {"openai": flag, "anthropic": True})
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.connect.assert_not_called()

    def set_reply(self, payload, status=200):
        response = self.connect.return_value.getresponse.return_value
        response.status = status
        response.read.return_value = json.dumps(payload).encode()

    def post_ask(self, **fields):
        return self.client.post("/api/ask", json={"provider": "openai", "question": "  What is available?  ", **fields},
                                headers={"Origin": "http://127.0.0.1:8000"})

    def get_request(self, host, path):
        self.connect.assert_called_once_with(host, timeout=10)
        send = self.connect.return_value.request
        send.assert_called_once()
        args, kwargs = send.call_args
        self.assertEqual(args, ("POST", path))
        return kwargs["headers"], json.loads(kwargs["body"])

    def test_openai_receives_only_selected_order_and_its_own_key(self):
        def post_reserve():
            return self.client.post("/api/orders", json={"sku": "ARC-01", "quantity": 1}).json()
        selected, other = post_reserve(), post_reserve()
        self.set_reply({"choices": [{"message": {"content": " Both lamps are reserved. "}}]})
        result = self.post_ask(order_id=selected["id"])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"provider": "openai", "answer": "Both lamps are reserved."})
        headers, data = self.get_request("api.openai.com", "/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer fake-openai")
        self.assertNotIn("fake-anthropic", str(headers) + str(data))
        self.assertEqual(data["model"], "gpt-4o-mini")
        self.assertEqual(data["max_completion_tokens"], 400)
        context = json.loads(data["messages"][1]["content"])
        self.assertEqual(context["question"], "What is available?")
        self.assertEqual(context["order"], selected)
        self.assertEqual(context["inventory"][0]["available"], 0)
        self.assertNotIn(other["id"], str(data))
        self.assertEqual(self.client.get("/api/orders/" + selected["id"]).json(), selected)

    def test_anthropic_receives_only_its_key_and_model_and_no_unselected_order(self):
        order = self.client.post("/api/orders", json={"sku": "ARC-01", "quantity": 1}).json()
        self.env["ANTHROPIC_MODEL"] = "demo-model-override"
        self.set_reply({"content": [{"type": "text", "text": "One lamp"}, {"type": "text", "text": "remains."}]})
        result = self.post_ask(provider="anthropic")
        self.assertEqual(result.json(), {"provider": "anthropic", "answer": "One lamp\nremains."})
        headers, data = self.get_request("api.anthropic.com", "/v1/messages")
        self.assertEqual(headers["x-api-key"], "fake-anthropic")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("fake-openai", str(headers) + str(data))
        self.assertEqual(data["model"], "demo-model-override")
        self.assertEqual(data["max_tokens"], 400)
        self.assertIsInstance(data["system"], str)
        self.assertIsNone(json.loads(data["messages"][0]["content"])["order"])
        self.assertNotIn(order["id"], str(data))

    def test_nonlocal_or_cross_origin_requests_never_connect(self):
        body = {"provider": "openai", "question": "How many lamps?"}
        for headers in (
            {"Host": "not-the-demo.example", "Origin": "http://not-the-demo.example"},
            {"Origin": "https://not-the-demo.example"}, {"Origin": "null"},
            {"Origin": "http://127.0.0.1:9000"}, {"Sec-Fetch-Site": "cross-site"},
            {"X-Forwarded-For": "127.0.0.1"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.post("/api/ask", json=body, headers=headers).status_code, 403)
        # Even with a local Host and no Origin, a non-loopback peer is not a local CLI.
        with TestClient(self.app, base_url="http://localhost", client=("192.0.2.1", 54000)) as remote:
            self.assertEqual(remote.post("/api/ask", json=body).status_code, 403)
        self.connect.assert_not_called()

    def test_bad_input_unknown_order_and_missing_key_never_connect(self):
        for fields in ({"provider": "other"}, {"question": "  "}, {"question": "x" * 801},
                       {"order_id": 42}, {"context": "unsolicited"}):
            with self.subTest(fields=fields):
                self.assertEqual(self.post_ask(**fields).status_code, 422)
        for mime, message, code in (("text/plain", "{}", 415), ("application/json", "bad", 422),
                                    ("application/json", "x" * 17000, 413)):
            r = self.client.post("/api/ask", content=message, headers={"Content-Type": mime})
            self.assertEqual(r.status_code, code)
        self.assertEqual(self.post_ask(order_id="unknown").status_code, 404)
        del self.env["OPENAI_API_KEY"]
        self.assertEqual(self.post_ask().status_code, 503)  # No fallback to the configured vendor.
        self.connect.assert_not_called()

    def test_upstream_errors_are_generic_and_never_retried(self):
        expected = {"detail": "Selected provider could not complete the request."}
        for provider, status, body in (
            ("openai", 302, b"private redirect"), ("anthropic", 429, b"private details"),
            ("openai", 200, b"not json"), ("anthropic", 200, b'{"content":null}'),
            ("openai", 200, b"x" * 32769),
        ):
            with self.subTest(provider=provider, status=status):
                self.connect.reset_mock()
                upstream = self.connect.return_value.getresponse.return_value
                upstream.status = status
                upstream.read.return_value = body
                r = self.post_ask(provider=provider)
                self.assertEqual((r.status_code, r.json()), (502, expected))
                self.connect.assert_called_once()
                self.connect.return_value.request.assert_called_once()
                if status == 200:
                    upstream.read.assert_called_once_with(32769)
                else:
                    upstream.read.assert_not_called()
        self.connect.reset_mock()
        self.connect.return_value.getresponse.side_effect = TimeoutError("private timeout details")
        r = self.post_ask()
        self.assertEqual((r.status_code, r.json()), (502, expected))
        self.connect.return_value.request.assert_called_once()

    def test_boundary_question_and_output_limits(self):
        self.set_reply({"content": [{"type": "text", "text": "a" * 3000}]})
        r = self.post_ask(provider="anthropic", question=" " + "x" * 800 + " ", order_id=None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["answer"]), 2400)
        _, data = self.get_request("api.anthropic.com", "/v1/messages")
        self.assertEqual(data["model"], "claude-haiku-4-5")
