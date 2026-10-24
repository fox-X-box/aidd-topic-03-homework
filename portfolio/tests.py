from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from dashboard.models import Share
from .models import Portfolio, Position, Trade
from .services import execute_trade, portfolio_summary


class PortfolioTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="owner", password="safe-password-123")
        self.other = get_user_model().objects.create_user(username="other", password="safe-password-123")
        self.portfolio = Portfolio.objects.create(owner=self.owner, name="Основной", currency="rub", initial_cash=1000, cash=1000)
        self.share = Share.objects.create(figi="FIGI", isin="ISIN", name="Company", ticker="COMP", currency="rub", uid="UID", last_price=100)

    def trade(self, side="buy", quantity="2", price="100", **kwargs):
        return execute_trade(self.portfolio, self.share, side, quantity, price, **kwargs)

    def test_weighted_average_partial_sale_and_pnl(self):
        self.trade(quantity="2", price="100")
        self.trade(quantity="2", price="200")
        position = Position.objects.get(portfolio=self.portfolio)
        self.assertEqual(position.quantity, Decimal("4"))
        self.assertEqual(position.average_price, Decimal("150"))
        sale = self.trade("sell", "1", "180")
        position.refresh_from_db()
        self.portfolio.refresh_from_db()
        self.assertEqual(position.quantity, Decimal("3"))
        self.assertEqual(position.average_price, Decimal("150"))
        self.assertEqual(sale.realized_pnl, Decimal("30"))
        self.assertEqual(self.portfolio.cash, Decimal("580"))

    def test_full_sale_resets_cost_and_repurchase_starts_new_average(self):
        self.trade()
        self.trade("sell", "2", "150")
        self.trade(quantity="1", price="110")
        position = Position.objects.get(portfolio=self.portfolio)
        self.assertEqual(position.average_price, Decimal("110"))
        self.assertEqual(position.quantity, Decimal("1"))

    def test_insufficient_cash_rolls_back_position_and_ledger(self):
        with self.assertRaises(ValidationError):
            self.trade(quantity="11")
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal("1000"))
        self.assertFalse(Position.objects.exists())
        self.assertFalse(Trade.objects.exists())

    def test_oversell_rolls_back(self):
        self.trade()
        with self.assertRaises(ValidationError):
            self.trade("sell", "3")
        self.assertEqual(Position.objects.get().quantity, Decimal("2"))
        self.assertEqual(Trade.objects.count(), 1)

    def test_invalid_numbers_and_side_rejected(self):
        for value in ["0", "-1", "NaN", "Infinity", None, "not-a-number", "0.0000000001"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.trade(quantity=value)
            with self.subTest(price=value), self.assertRaises(ValidationError):
                self.trade(price=value)
        with self.assertRaises(ValidationError):
            self.trade(side="gift")
        self.assertEqual(Trade.objects.count(), 0)

    def test_currency_mismatch_rejected(self):
        self.share.currency = "usd"
        self.share.save()
        with self.assertRaises(ValidationError):
            self.trade()
        self.assertFalse(Trade.objects.exists())

    def test_fractional_decimal_cost(self):
        self.trade(quantity="0.3", price="0.1")
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal("999.97000000"))

    def test_idempotent_execution_and_key_collision(self):
        first = self.trade(idempotency_key="request:123")
        second = self.trade(idempotency_key="request:123")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(Position.objects.get().quantity, Decimal("2"))
        with self.assertRaises(ValidationError):
            self.trade(quantity="3", idempotency_key="request:123")

    def test_valuation_and_missing_prices(self):
        self.trade()
        self.share.last_price = Decimal("125")
        self.share.save()
        self.portfolio.refresh_from_db()
        summary = portfolio_summary(self.portfolio)
        self.assertEqual(summary["current_value"], Decimal("250"))
        self.assertEqual(summary["unrealized_pnl"], Decimal("50"))
        self.assertEqual(summary["total_pnl"], Decimal("50"))
        self.share.last_price = None
        self.share.save()
        summary = portfolio_summary(self.portfolio)
        self.assertIsNone(summary["equity"])
        self.assertIsNone(summary["total_pnl"])
        self.assertTrue(summary["has_missing_prices"])

    def test_trade_instance_is_immutable(self):
        trade = self.trade()
        trade.price = Decimal("50")
        with self.assertRaises(ValidationError):
            trade.save()
        with self.assertRaises(ValidationError):
            trade.delete()
        self.assertEqual(Trade.objects.get(pk=trade.pk).price, Decimal("100"))

    def test_owner_isolation_for_list_detail_and_trade(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("portfolio:index"))
        self.assertNotContains(response, self.portfolio.name)
        self.assertEqual(self.client.get(reverse("portfolio:detail", args=[self.portfolio.pk])).status_code, 404)
        response = self.client.post(reverse("portfolio:trade", args=[self.portfolio.pk]), {"share": self.share.pk, "side": "buy", "quantity": "1"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Trade.objects.exists())

    def test_anonymous_redirect_and_trade_get_forbidden(self):
        self.assertEqual(self.client.get(reverse("portfolio:index")).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("portfolio:trade", args=[self.portfolio.pk])).status_code, 405)

    def test_create_portfolio_and_http_trade_uses_market_price(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("portfolio:index"), {"name": "USD", "currency": "USD", "initial_cash": "500"})
        self.assertEqual(response.status_code, 302)
        portfolio = Portfolio.objects.get(name="USD")
        self.assertEqual(portfolio.currency, "usd")
        self.assertEqual(portfolio.cash, Decimal("500"))
        response = self.client.post(reverse("portfolio:trade", args=[self.portfolio.pk]), {"share": self.share.pk, "side": "buy", "quantity": "2", "price": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Trade.objects.get().price, Decimal("100"))
        self.assertEqual(self.client.get(reverse("portfolio:detail", args=[self.portfolio.pk])).status_code, 200)

    def test_http_missing_price_and_negative_initial_cash(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("portfolio:index"), {"name": "Bad", "currency": "rub", "initial_cash": "-1"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Portfolio.objects.filter(name="Bad").exists())
        self.share.last_price = None
        self.share.save()
        response = self.client.post(reverse("portfolio:trade", args=[self.portfolio.pk]), {"share": self.share.pk, "side": "buy", "quantity": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Цена")
        self.assertFalse(Trade.objects.exists())


class ConcurrentTradingTests(TransactionTestCase):
    """The production PostgreSQL locks must serialize competing orders."""
    def test_competing_buys_cannot_overspend(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connection, connections
        if connection.vendor != "postgresql":
            self.skipTest("Row locking requires PostgreSQL")
        owner = get_user_model().objects.create_user(username="concurrent")
        portfolio = Portfolio.objects.create(owner=owner, name="Lock", cash=100, initial_cash=100)
        share = Share.objects.create(figi="LOCK", isin="LOCK", name="Lock", ticker="LOCK", currency="rub", uid="LOCK", last_price=100)

        def purchase(_):
            try:
                execute_trade(Portfolio.objects.get(pk=portfolio.pk), Share.objects.get(pk=share.pk), "buy", "1", "100")
                return "bought"
            except ValidationError:
                return "insufficient"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(purchase, range(2)))
        self.assertCountEqual(outcomes, ["bought", "insufficient"])
        portfolio.refresh_from_db()
        self.assertEqual(portfolio.cash, 0)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(Position.objects.get().quantity, 1)
