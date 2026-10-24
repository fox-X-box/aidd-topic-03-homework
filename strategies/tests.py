from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from dashboard.models import Share
from portfolio.models import Portfolio, Position, Trade
from portfolio.services import execute_trade
from .models import Strategy, StrategyExecution
from .services import evaluate_strategies


class StrategyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="investor", password="test-password")
        self.other = get_user_model().objects.create_user(username="other", password="test-password")
        self.share = Share.objects.create(figi="figi", isin="isin", ticker="TEST", uid="uid",
                                          name="Test", currency="rub", last_price=100)
        self.portfolio = Portfolio.objects.create(owner=self.owner, name="Main", currency="rub",
                                                  initial_cash=1000, cash=1000)

    def strategy(self, **kwargs):
        return Strategy.objects.create(owner=self.owner, portfolio=self.portfolio, share=self.share,
                                       name="Threshold", side=kwargs.pop("side", "buy"),
                                       quantity=kwargs.pop("quantity", 2),
                                       price_threshold=kwargs.pop("price_threshold", 100), **kwargs)

    def test_buy_boundary_uses_observed_price_once(self):
        strategy = self.strategy()
        self.assertEqual(evaluate_strategies(self.share, 101), [])
        self.assertEqual(Trade.objects.count(), 0)
        self.assertEqual(len(evaluate_strategies(self.share, 100)), 1)
        evaluate_strategies(self.share, 90)
        strategy.refresh_from_db()
        self.portfolio.refresh_from_db()
        self.assertEqual(strategy.status, Strategy.Status.EXECUTED)
        self.assertFalse(strategy.enabled)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(StrategyExecution.objects.count(), 1)
        self.assertEqual(self.portfolio.cash, Decimal("800"))
        self.assertEqual(strategy.execution.trade.price, Decimal("100"))

    def test_sell_boundary_and_realized_profit(self):
        execute_trade(self.portfolio, self.share, "buy", 3, 80)
        strategy = self.strategy(side="sell", price_threshold=100)
        self.assertEqual(evaluate_strategies(self.share, 99), [])
        evaluate_strategies(self.share, 100)
        self.assertEqual(strategy.execution.trade.realized_pnl, Decimal("40"))
        self.assertEqual(strategy.execution.result, Decimal("40"))
        self.assertEqual(strategy.execution.result_percent, Decimal("25"))
        self.assertEqual(Position.objects.get(portfolio=self.portfolio).quantity, Decimal("1"))

    def test_insufficient_funds_logs_one_failure_without_side_effects(self):
        strategy = self.strategy(quantity=20)
        evaluate_strategies(self.share, 100)
        evaluate_strategies(self.share, 90)
        strategy.refresh_from_db()
        self.portfolio.refresh_from_db()
        self.assertEqual(strategy.status, Strategy.Status.FAILED)
        self.assertIn("Недостаточно", strategy.execution.error)
        self.assertIsNone(strategy.execution.trade)
        self.assertFalse(strategy.enabled)
        self.assertEqual(Trade.objects.count(), 0)
        self.assertEqual(StrategyExecution.objects.count(), 1)
        self.assertEqual(self.portfolio.cash, Decimal("1000"))
        self.assertFalse(Position.objects.exists())

    def test_oversell_is_recorded_as_failure(self):
        strategy = self.strategy(side="sell")
        evaluate_strategies(self.share, 100)
        strategy.refresh_from_db()
        self.assertEqual(strategy.status, Strategy.Status.FAILED)
        self.assertIsNone(strategy.execution.trade)
        self.assertEqual(Trade.objects.count(), 0)

    def test_currency_and_portfolio_owner_are_validated_at_execution(self):
        strategy = self.strategy()
        self.portfolio.currency = "usd"
        self.portfolio.save(update_fields=["currency"])
        evaluate_strategies(self.share, 100)
        strategy.refresh_from_db()
        self.assertEqual(strategy.status, Strategy.Status.FAILED)
        self.assertIn("Валюта", strategy.execution.error)
        self.assertFalse(Trade.objects.exists())
        self.portfolio.currency = "rub"
        self.portfolio.owner = self.other
        self.portfolio.save()
        strategy = self.strategy()
        evaluate_strategies(self.share, 100)
        strategy.refresh_from_db()
        self.assertEqual(strategy.status, Strategy.Status.FAILED)
        self.assertIn("владельцу", strategy.execution.error)

    def test_invalid_prices_cannot_trigger(self):
        self.strategy()
        for price in [0, -1, "NaN", "Infinity", None, "bad", "1e15", "1e100", "0.0000000001"]:
            with self.subTest(price=price), self.assertRaises(ValidationError):
                evaluate_strategies(self.share, price)
        self.assertFalse(StrategyExecution.objects.exists())

    def test_owner_only_listing_creation_and_cancellation(self):
        strategy = self.strategy()
        self.assertEqual(self.client.get(reverse("strategies:index")).status_code, 302)
        self.client.force_login(self.other)
        response = self.client.get(reverse("strategies:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Threshold")
        data = {"name": "Stolen", "portfolio": self.portfolio.pk, "share": self.share.pk,
                "side": "buy", "quantity": 1, "price_threshold": 10}
        response = self.client.post(reverse("strategies:create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Strategy.objects.count(), 1)
        self.assertEqual(self.client.post(reverse("strategies:cancel", args=[strategy.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("strategies:cancel", args=[strategy.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("strategies:cancel", args=[strategy.pk])).status_code, 302)
        strategy.refresh_from_db()
        self.assertEqual(strategy.status, Strategy.Status.CANCELLED)
        evaluate_strategies(self.share, 99)
        self.assertFalse(Trade.objects.exists())

    def test_form_positive_values_and_create(self):
        self.client.force_login(self.owner)
        data = {"name": "My strategy", "portfolio": self.portfolio.pk, "share": self.share.pk,
                "side": "buy", "quantity": 0, "price_threshold": -1}
        response = self.client.post(reverse("strategies:create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Strategy.objects.exists())
        data.update(quantity=1, price_threshold=100)
        self.assertEqual(self.client.post(reverse("strategies:create"), data).status_code, 302)
        strategy = Strategy.objects.get()
        self.assertEqual(strategy.owner, self.owner)
        evaluate_strategies(self.share, 90)
        self.share.last_price = 95
        self.share.save(update_fields=["last_price"])
        strategy.refresh_from_db()
        self.assertEqual(strategy.execution.result, Decimal("5"))
        response = self.client.get(reverse("strategies:index"))
        self.assertContains(response, "Журнал:")
        self.assertContains(response, "Гипотетическое изменение стоимости исходной покупки")
        self.assertContains(response, "5.56%")

    def test_purchase_metric_is_hypothetical_after_lot_has_been_sold(self):
        strategy = self.strategy()
        evaluate_strategies(self.share, 100)
        execute_trade(self.portfolio, self.share, "sell", 2, 110)
        self.assertEqual(Position.objects.get(portfolio=self.portfolio).quantity, 0)
        self.share.last_price = 125
        self.share.save(update_fields=["last_price"])
        execution = StrategyExecution.objects.select_related("strategy__share", "trade").get(strategy=strategy)
        self.assertEqual(execution.result, Decimal("50"))
        self.assertEqual(execution.result_percent, Decimal("25"))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("strategies:index"))
        self.assertContains(response, "гипотетическое изменение стоимости исходного объема")
        self.assertContains(response, "не фактическая прибыль после последующих продаж")

    def test_zero_quote_is_total_hypothetical_loss_and_missing_is_unknown(self):
        strategy = self.strategy()
        evaluate_strategies(self.share, 100)
        self.share.last_price = 0
        self.share.save(update_fields=["last_price"])
        execution = StrategyExecution.objects.select_related("strategy__share", "trade").get(strategy=strategy)
        self.assertEqual(execution.result, Decimal("-200"))
        self.assertEqual(execution.result_percent, Decimal("-100"))
        self.share.last_price = None
        self.share.save(update_fields=["last_price"])
        execution = StrategyExecution.objects.select_related("strategy__share", "trade").get(strategy=strategy)
        self.assertIsNone(execution.result)
        self.assertIsNone(execution.result_percent)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("strategies:index"))
        self.assertContains(response, "Нет текущей цены")
        self.assertNotContains(response, "None%")

    def test_quote_time_must_be_aware_and_nine_decimal_price_is_supported(self):
        from datetime import datetime, timezone

        strategy = self.strategy()
        for observed_at in [datetime(2026, 1, 1), "2026-01-01", 0]:
            with self.subTest(observed_at=observed_at), self.assertRaises(ValidationError):
                evaluate_strategies(self.share, 100, observed_at)
        self.assertFalse(StrategyExecution.objects.exists())
        observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        evaluate_strategies(self.share, Decimal("99.123456789"), observed_at)
        self.assertEqual(strategy.execution.observed_at, observed_at)
        self.assertEqual(strategy.execution.price, Decimal("99.123456789"))
        self.assertEqual(strategy.execution.trade.price, Decimal("99.123456789"))


class StrategyConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_ticks_execute_strategy_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections

        owner = get_user_model().objects.create_user(username="parallel")
        share = Share.objects.create(figi="parallel", isin="parallel", ticker="PAR", uid="parallel",
                                     name="Parallel", currency="rub", last_price=100)
        portfolio = Portfolio.objects.create(owner=owner, name="Parallel", initial_cash=1000, cash=1000)
        strategy = Strategy.objects.create(owner=owner, portfolio=portfolio, share=share, name="Once",
                                           side="buy", quantity=2, price_threshold=100)
        barrier = Barrier(2)

        def tick():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return len(evaluate_strategies(share, 100))
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            counts = list(executor.map(lambda _: tick(), range(2)))
        self.assertEqual(sum(counts), 1)
        self.assertEqual(StrategyExecution.objects.filter(strategy=strategy).count(), 1)
        self.assertEqual(Trade.objects.count(), 1)
        portfolio.refresh_from_db()
        self.assertEqual(portfolio.cash, Decimal("800"))
