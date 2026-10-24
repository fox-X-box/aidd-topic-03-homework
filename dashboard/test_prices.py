"""Regression + end-to-end quote pipeline checks; external API is mocked explicitly."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from dashboard.models import Share, PricePoint
from dashboard.services.market_data import quotation, get_last_data, api_request, MarketDataError
from dashboard.services.prices import record_price
from dashboard.tasks import update_last_price
from monitoring.models import Watchlist, WatchRule, Notification
from portfolio.models import Portfolio, Trade
from strategies.models import Strategy, StrategyExecution


class QuotePipelineTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('investor@example.com')
        self.share = Share.objects.create(figi='TEST1', uid='test1', isin='TEST1', ticker='TEST1', name='Test', currency='rub')
        self.now = timezone.now()

    def test_quote_fractional_nanos_are_preserved(self):
        self.assertEqual(quotation({'units': '10', 'nano': 123456789}), Decimal('10.123456789'))
        self.assertEqual(quotation({'units': '0', 'nano': -100}), Decimal('-0.000000100'))

    @patch('dashboard.services.market_data.api_request')
    def test_provider_maps_real_api_shape_and_time(self, request):
        request.return_value = {'lastPrices': [{'price': {'units': '1', 'nano': 50}, 'time': '2026-10-24T08:00:00Z'}]}
        price, observed = get_last_data(self.share)
        self.assertEqual(price, Decimal('1.000000050'))
        self.assertEqual(observed.hour, 8)
        self.assertTrue(timezone.is_aware(observed))

    @override_settings(TINKOFF_TOKEN='mock-token-never-live')
    @patch('dashboard.services.market_data.urlopen')
    def test_rest_adapter_payload_and_safe_errors(self, open_url):
        open_url.return_value.__enter__.return_value.read.return_value = b'{"instruments": []}'
        self.assertEqual(api_request('InstrumentsService', 'Shares', {}), {'instruments': []})
        req = open_url.call_args.args[0]
        self.assertTrue(req.full_url.startswith('https://'))
        self.assertEqual(json.loads(req.data), {})
        self.assertEqual(open_url.call_args.kwargs['timeout'], 15)
        open_url.side_effect = URLError('private backend detail')
        with self.assertRaises(MarketDataError) as error:
            api_request('InstrumentsService', 'Shares', {})
        self.assertNotIn('private', str(error.exception))
        self.assertNotIn('mock-token', str(error.exception))

    @override_settings(TINKOFF_TOKEN='')
    def test_missing_live_token_is_explicit(self):
        with self.assertRaises(MarketDataError):
            get_last_data(self.share)
        self.assertEqual(update_last_price()['skipped'], 'TINKOFF_TOKEN is not configured')
        with self.assertRaises(CommandError):
            call_command('add_shares')

    def test_record_quote_is_idempotent_and_updates_market_timestamp(self):
        first, created = record_price(self.share, '100.123456789', self.now)
        second, duplicate = record_price(self.share, '100.123456789', self.now)
        self.assertTrue(created)
        self.assertFalse(duplicate)
        self.assertEqual(first.pk, second.pk)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal('100.123456789'))
        self.assertEqual(self.share.updated_at, self.now)
        with self.assertRaises(ValidationError):
            record_price(self.share, '101', self.now)
        self.assertEqual(PricePoint.objects.count(), 1)

    def test_stale_quote_retained_without_regressing_price_or_firing_rule(self):
        record_price(self.share, 100, self.now)
        watchlist = Watchlist.objects.create(owner=self.owner, name='Local')
        WatchRule.objects.create(watchlist=watchlist, share=self.share, direction='below', target_price=80)
        record_price(self.share, 75, self.now - timedelta(days=1))
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal(100))
        self.assertEqual(PricePoint.objects.count(), 2)
        self.assertFalse(Notification.objects.exists())

    def test_invalid_quote_cannot_create_history(self):
        for price in ('NaN', 'Infinity', '-1', '0', '0.0000000001', '1e40', 'bad'):
            with self.subTest(price=price), self.assertRaises(ValidationError):
                record_price(self.share, price)
        with self.assertRaises(ValidationError):
            record_price(self.share, 1, self.now.replace(tzinfo=None))
        self.assertFalse(PricePoint.objects.exists())

    def test_quote_triggers_one_notification_and_one_virtual_trade(self):
        p = Portfolio.objects.create(owner=self.owner, name='Virtual', currency='rub', initial_cash=1000, cash=1000)
        wl = Watchlist.objects.create(owner=self.owner, name='Rules')
        WatchRule.objects.create(watchlist=wl, share=self.share, direction='below', target_price=100)
        strategy = Strategy.objects.create(owner=self.owner, portfolio=p, share=self.share, name='Buy low', side='buy', quantity=2, price_threshold=100)
        record_price(self.share, '99.123456789', self.now)
        record_price(self.share, '99.123456789', self.now)
        record_price(self.share, '98.123456789', self.now + timedelta(seconds=1))
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(StrategyExecution.objects.count(), 1)
        self.assertEqual(Trade.objects.get().price, Decimal('99.123456789'))
        p.refresh_from_db()
        self.assertEqual(p.cash, Decimal('801.753086422'))
        strategy.refresh_from_db()
        self.assertFalse(strategy.enabled)

    @patch('strategies.services.evaluate_strategies', side_effect=RuntimeError('database unavailable'))
    def test_pipeline_infrastructure_failure_rolls_back_history_and_alert(self, _):
        wl = Watchlist.objects.create(owner=self.owner, name='Rollback')
        WatchRule.objects.create(watchlist=wl, share=self.share, direction='below', target_price=100)
        with self.assertRaises(RuntimeError):
            record_price(self.share, 90, self.now)
        self.assertFalse(PricePoint.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.share.refresh_from_db()
        self.assertIsNone(self.share.last_price)

    @patch('dashboard.management.commands.add_shares.get_instruments')
    def test_catalog_import_updates_by_stable_figi(self, instruments):
        instruments.return_value = [{'figi': self.share.figi, 'uid': self.share.uid, 'isin': self.share.isin, 'ticker': self.share.ticker, 'name': 'Updated name', 'currency': 'rub'}]
        for _ in range(2):
            call_command('add_shares', stdout=StringIO())
        self.assertEqual(Share.objects.count(), 1)
        self.share.refresh_from_db()
        self.assertEqual(self.share.name, 'Updated name')

    def test_demo_seed_is_repeatable_and_labelled(self):
        for _ in range(2):
            call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Share.objects.filter(ticker__startswith='DEMO').count(), 2)
        self.assertEqual(PricePoint.objects.filter(share__ticker__startswith='DEMO').count(), 16)

    def test_html_missing_detail_returns_404_and_local_history_works(self):
        self.assertEqual(self.client.get('/999999').status_code, 404)
        record_price(self.share, 100, self.now - timedelta(hours=1))
        record_price(self.share, 110, self.now)
        response = self.client.get(reverse('dashboard:detail', args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['absolute_change'], Decimal(10))
        self.assertEqual(response.context['percent_change'], Decimal(10))
        self.assertContains(response, 'История рыночных цен')

    def test_date_range_restricts_results_and_validates(self):
        record_price(self.share, 100, self.now - timedelta(days=2))
        record_price(self.share, 110, self.now)
        url = reverse('dashboard:detail', args=[self.share.pk])
        response = self.client.get(url, {'start': self.now.date().isoformat(), 'end': self.now.date().isoformat()})
        self.assertEqual(len(response.context['history']), 1)
        self.assertIsNone(response.context['absolute_change'])
        for params in ({'start': 'bad'}, {'start': '2026-02-01', 'end': '2026-01-01'}):
            self.assertEqual(self.client.get(url, params).status_code, 400)

    def test_api_anonymous_reads_only_and_uid_required_for_authenticated_writes(self):
        client = APIClient()
        self.assertEqual(client.get('/api/v1/shares/').status_code, 200)
        self.assertEqual(client.post('/api/v1/shares/', {}).status_code, 403)
        self.assertEqual(client.patch(f'/api/v1/shares/{self.share.pk}/', {'name': 'Attack'}).status_code, 403)
        client.force_authenticate(self.owner)
        payload = {'figi': 'NEW', 'isin': 'NEW', 'name': 'New', 'ticker': 'NEW', 'currency': 'rub'}
        self.assertEqual(client.post('/api/v1/shares/', payload).status_code, 400)
        payload['uid'] = 'new-uid'
        response = client.post('/api/v1/shares/', payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Share.objects.get(ticker='NEW').uid, 'new-uid')

    def test_api_cannot_change_market_values_or_delete_portfolio_instrument(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.patch(f'/api/v1/shares/{self.share.pk}/', {'last_price': '999', 'is_trend_high': True})
        self.assertEqual(response.status_code, 200)
        self.share.refresh_from_db()
        self.assertIsNone(self.share.last_price)
        p = Portfolio.objects.create(owner=self.owner, name='Protected', cash=1000, initial_cash=1000)
        from portfolio.services import execute_trade
        execute_trade(p, self.share, 'buy', 1, 100)
        self.assertEqual(client.delete(f'/api/v1/shares/{self.share.pk}/').status_code, 409)
        self.client.force_login(self.owner)
        response = self.client.post(reverse('dashboard:delete', args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'не может быть удалена')
        self.assertTrue(Share.objects.filter(pk=self.share.pk).exists())

    def test_currency_change_cannot_corrupt_existing_price_history(self):
        record_price(self.share, 100, self.now)
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.patch(f'/api/v1/shares/{self.share.pk}/', {'currency': 'usd'})
        self.assertEqual(response.status_code, 400)
        self.share.currency = 'usd'
        with self.assertRaises(ValidationError):
            self.share.save()


    def test_metadata_edit_does_not_make_current_quote_stale(self):
        record_price(self.share, 100, self.now - timedelta(minutes=2))
        self.share.refresh_from_db()
        self.share.name = "Edited metadata"
        self.share.save()
        record_price(self.share, 110, self.now - timedelta(minutes=1))
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal(110))
        self.assertEqual(self.share.updated_at, self.now - timedelta(minutes=1))

    @patch('dashboard.services.graph.get_candles')
    def test_external_chart_remains_available_after_local_quotes(self, candles):
        candles.return_value = [{'time': '2026-10-23T00:00:00Z', 'close': {'units': '80', 'nano': 500000000}}]
        record_price(self.share, 100, self.now)
        response = self.client.get(reverse('dashboard:detail', args=[self.share.pk]), {'source': 'market'})
        self.assertEqual(response.status_code, 200)
        candles.assert_called_once()
        self.assertIn('80.5', response.context['plot_div'])


    def test_malformed_provider_quote_is_reported_as_market_error(self):
        for value in ({}, {'units': 'nan'}, {'units': '1.1'}, {'units': '1', 'nano': 1000000000}):
            with self.subTest(value=value), self.assertRaises(MarketDataError):
                quotation(value)

    @override_settings(TINKOFF_TOKEN='mock-only')
    @patch('dashboard.tasks.get_last_data')
    def test_worker_continues_after_individual_quote_failure(self, quotes):
        second = Share.objects.create(ticker='SECOND', figi='SECOND', uid='SECOND', isin='SECOND', name='Second', currency='rub')
        quotes.side_effect = [MarketDataError('offline'), (Decimal(120), self.now)]
        self.assertEqual(update_last_price(), {'updated': 1, 'failed': 1})
        self.assertEqual(PricePoint.objects.count(), 1)

    def test_demo_command_rejects_real_instrument_and_accepts_synthetic(self):
        with self.assertRaises(CommandError):
            call_command('demo_price', self.share.ticker, '90')
        call_command('seed_demo', stdout=StringIO())
        call_command('demo_price', 'DEMO1', '90.123456789', stdout=StringIO())
        self.assertEqual(Share.objects.get(ticker='DEMO1').last_price, Decimal('90.123456789'))


    def test_html_crud_is_authenticated_and_preserves_identifiers(self):
        payload = {'figi': 'HTML', 'isin': 'HTML', 'name': 'Created in HTML', 'ticker': 'HTML', 'currency': 'rub', 'uid': 'html-uid'}
        response = self.client.post(reverse('dashboard:create'), payload)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Share.objects.filter(ticker='HTML').exists())
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('dashboard:create'), payload).status_code, 302)
        share = Share.objects.get(ticker='HTML')
        payload['name'] = 'Edited in HTML'
        self.assertEqual(self.client.post(reverse('dashboard:update', args=[share.pk]), payload).status_code, 302)
        share.refresh_from_db()
        self.assertEqual(share.name, 'Edited in HTML')
        self.assertEqual(self.client.get(reverse('dashboard:delete', args=[share.pk])).status_code, 200)
        self.assertTrue(Share.objects.filter(pk=share.pk).exists())
        self.assertEqual(self.client.post(reverse('dashboard:delete', args=[share.pk])).status_code, 302)
        self.assertFalse(Share.objects.filter(pk=share.pk).exists())

    def test_api_filters_search_ordering_and_pagination(self):
        other = Share.objects.create(ticker='AAA', figi='AAA', uid='AAA', isin='AAA', name='Alpha', currency='rub')
        client = APIClient()
        response = client.get('/api/v1/shares/', {'ticker': 'AAA'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], other.pk)
        response = client.get('/api/v1/shares/', {'name': 'Test'})
        self.assertEqual(response.data['count'], 1)
        response = client.get('/api/v1/shares/', {'search': '^Al'})
        self.assertEqual(response.data['count'], 1)
        response = client.get('/api/v1/shares/', {'ordering': '-ticker', 'limit': 1, 'offset': 1})
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['ticker'], 'AAA')

    def test_unique_uid_is_enforced_for_second_api_create(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        for ticker in ('N1', 'N2'):
            payload = {'figi': ticker, 'uid': ticker, 'ticker': ticker, 'isin': ticker, 'name': ticker, 'currency': 'rub'}
            self.assertEqual(client.post('/api/v1/shares/', payload).status_code, 201)
        payload.update(figi='N3', ticker='N3')
        self.assertEqual(client.post('/api/v1/shares/', payload).status_code, 400)

    @override_settings(TINKOFF_TOKEN='')
    def test_missing_live_history_returns_usable_page_with_error(self):
        response = self.client.get(reverse('dashboard:detail', args=[self.share.pk]), {'source': 'market'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Внешние исторические данные временно недоступны')
