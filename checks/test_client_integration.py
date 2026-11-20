"""Run the actual JS client against FastAPI, substituting only vendor HTTPS."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import json
import socket
import subprocess
import time
import unittest
from unittest.mock import Mock, patch

import uvicorn
from backend.app import create_app


class ClientIntegration(unittest.TestCase):
    def test_order_and_both_provider_adapters(self):
        destinations = []

        def simulated_vendor(host, **_):
            destinations.append(host)
            reply = {'api.openai.com': {'choices': [{'message': {'content': 'one available'}}]},
                     'api.anthropic.com': {'content': [{'type': 'text', 'text': 'one reserved'}]}}[host]
            connection = Mock()
            response = connection.getresponse.return_value
            response.status = 200
            response.read.return_value = json.dumps(reply).encode()
            return connection

        with TemporaryDirectory() as tmp, socket.socket() as sock, \
                patch('http.client.HTTPSConnection', side_effect=simulated_vendor):
            app = create_app(Path(tmp), ask_env={'OPENAI_API_KEY': 'test-only', 'ANTHROPIC_API_KEY': 'test-only'})
            sock.bind(('127.0.0.1', 0))
            origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
            server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level='error', proxy_headers=False))
            worker = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
            worker.start()
            try:
                deadline = time.monotonic() + 10
                while not server.started and worker.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(server.started, 'Local API failed to start')
                subprocess.run(['node', str(Path(__file__).with_name('client_flow.mjs')), origin],
                               check=True, timeout=30)
            finally:
                server.should_exit = True
                worker.join(10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(destinations, ['api.openai.com', 'api.anthropic.com'])
