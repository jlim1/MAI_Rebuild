"""Exercise the built UI on loopback, without touching the presenter's data."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
import os
import re
import shutil
import subprocess
import sys
import time

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def server(project):
    log = project / 'server.log'
    with log.open('w', encoding='utf-8') as output:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '0'],
            cwd=project, stdout=output, stderr=subprocess.STDOUT,
            env={**os.environ, 'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': ''},
        )
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and proc.poll() is None:
                text = log.read_text(encoding='utf-8', errors='replace')
                ready = re.search(r'Uvicorn running on (http://127\.0\.0\.1:\d+)', text)
                if ready:
                    yield ready.group(1)
                    return
                time.sleep(0.1)
            raise RuntimeError('Local server did not start:\n' + log.read_text(errors='replace'))
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def run(check):
    with TemporaryDirectory(prefix='parcel-check-') as scratch, sync_playwright() as p:
        project = Path(scratch)
        shutil.copytree(ROOT / 'backend', project / 'backend', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'frontend' / 'dist', project / 'frontend' / 'dist')
        browser = p.chromium.launch(
            channel=os.getenv('PARCEL_TEST_BROWSER') or None, chromium_sandbox=True
        )
        try:
            context = browser.new_context(service_workers='block', viewport={'width': 1360, 'height': 960})
            page = context.new_page()
            forbidden, errors = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            with server(project) as origin:
                def local_only(route):
                    if urlsplit(route.request.url).netloc != urlsplit(origin).netloc:
                        forbidden.append(route.request.url)
                        route.abort()
                    else:
                        route.continue_()
                context.route('**/*', local_only)
                page.goto(origin)
                check(page)
            subprocess.run([sys.executable, '-m', 'backend.reset'], cwd=project, check=True)
            with server(project) as origin:
                stock = context.request.get(origin + '/api/inventory?q=ARC-01').json()
                assert stock[0]['available'] == 2 and stock[0]['reserved'] == 0, stock
            assert not forbidden, f'Unexpected external browser requests: {forbidden}'
            assert not errors, f'Browser errors: {errors}'
        finally:
            browser.close()
    print('PASS: isolated browser walkthrough and reset; no external browser requests.')


def walkthrough(page):
    search = page.get_by_role('searchbox', name='Search inventory')
    search.fill('nothing-matches-this')
    expect(page.get_by_role('heading', name='No matching equipment')).to_be_visible()
    search.fill('ARC-01')
    reserve = page.get_by_role('button', name='Reserve Arc lamp')
    reserve.click()
    page.get_by_role('button', name='Confirm reservation').click()
    lookup = page.get_by_label('Order ID', exact=True)
    expect(lookup).not_to_have_value('')
    order_id = lookup.input_value()
    expect(page.get_by_label(f'Order {order_id}', exact=True)).to_be_visible()
    reserve.click()
    page.get_by_role('spinbutton', name='Quantity').fill('2')
    page.get_by_role('button', name='Confirm reservation').click()
    expect(page.get_by_role('alert')).to_contain_text(re.compile('stock|available|shortage|insufficient', re.I))
    page.get_by_role('button', name='Cancel').click()
    page.reload()
    expect(page.get_by_label(f'Order {order_id}', exact=True)).to_be_visible()
    lookup.fill(order_id)
    page.get_by_role('button', name='Look up order').click()
    for state in ['packed', 'shipped', 'delivered']:
        page.get_by_role('button', name=f'Mark as {state}').click()
        expect(page.locator('[aria-current="step"]')).to_contain_text(state.title())
    expect(page.get_by_text('Simulated fulfillment complete')).to_be_visible()
    stock = page.request.get(page.url.split('#')[0].rstrip('/') + '/api/inventory?q=ARC-01').json()
    assert [(s['on_hand'], s['reserved'], s['available']) for s in stock] == [(1, 0, 1)]
    expect(page.get_by_role('heading', name='Ask Mai', exact=True)).to_be_visible()
    with page.expect_response(lambda response: response.url.endswith('/api/ask/providers')) as configuration:
        page.get_by_role('button', name='Check provider configuration').click()
    assert configuration.value.json() == {'openai': False, 'anthropic': False}


if __name__ == '__main__':
    run(walkthrough)
