"""Real local HTTP + PostgreSQL smoke test; run after run-dev.sh. Synthetic data only."""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, Request
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core.management import call_command
from dashboard.models import Share
from monitoring.models import Watchlist, Notification
from portfolio.models import Portfolio, Trade
from portfolio.services import portfolio_summary
from strategies.models import StrategyExecution

BASE = 'http://127.0.0.1:8000'
jar = http.cookiejar.CookieJar()
client = build_opener(HTTPCookieProcessor(jar))


def request(path, data=None):
    if data is not None:
        token = next(c.value for c in jar if c.name == 'csrftoken')
        data = urlencode({**data, 'csrfmiddlewaretoken': token}).encode()
    response = client.open(Request(BASE + path, data=data), timeout=30)
    assert response.status == 200, (path, response.status)
    return response.geturl(), response.read().decode()


call_command('seed_demo')
call_command('demo_price', 'DEMO1', '100.50')
request('/')
request('/user/registration/')
email = f'smoke-{uuid4().hex}@example.com'
password = secrets.token_urlsafe(32)
url, body = request('/user/registration/', {'email': email, 'password1': password, 'password2': password})
assert urlparse(url).path == '/', 'Registration must log the new user in'
owner = get_user_model().objects.get(username=email)
request('/portfolio/', {'name': 'HTTP smoke portfolio', 'currency': 'rub', 'initial_cash': '1000'})
p = Portfolio.objects.get(owner=owner)
request('/monitoring/lists/add/', {'name': 'HTTP smoke watchlist'})
wl = Watchlist.objects.get(owner=owner)
share = Share.objects.get(ticker='DEMO1')
request(f'/monitoring/lists/{wl.pk}/rules/add/', {'share': share.pk, 'direction': 'below', 'target_price': '95'})
request('/strategies/create/', {'name': 'HTTP smoke buy low', 'portfolio': p.pk, 'share': share.pk, 'side': 'buy', 'quantity': '2', 'price_threshold': '95'})
call_command('demo_price', 'DEMO1', '90')
call_command('demo_price', 'DEMO1', '90')
assert Notification.objects.filter(owner=owner).count() == 1
assert Trade.objects.filter(portfolio=p).count() == 1
assert StrategyExecution.objects.filter(strategy__owner=owner).count() == 1
_, inbox = request('/monitoring/notifications/')
assert 'DEMO1' in inbox
call_command('demo_price', 'DEMO1', '110')
p.refresh_from_db()
summary = portfolio_summary(p)
assert p.cash == 820 and summary['total_pnl'] == 40
request(f'/portfolio/{p.pk}/')
_, detail = request(f'/{share.pk}')
assert '110' in detail and 'История рыночных цен' in detail
_, catalogue = request('/api/v1/shares/')
assert json.loads(catalogue)['count'] >= 2
request('/user/logout/', {})
try:
    request('/api/v1/shares/', {'name': 'Forbidden anonymous write'})
except HTTPError as exc:
    assert exc.code == 403
else:
    raise AssertionError('Anonymous API writes must be forbidden')
print(json.dumps({'http_smoke': 'passed', 'notifications': 1, 'strategy_trades': 1, 'cash': str(p.cash), 'total_pnl': str(summary['total_pnl']), 'anonymous_write': 403}))
