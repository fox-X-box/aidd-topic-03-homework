import sys
from decimal import Decimal
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import PriceAlert, Share, WatchlistItem
from dashboard.services.graph import get_graph
from dashboard.services.market_data import (
    MarketDataError,
    get_last_data,
    money_value_to_float,
)
from dashboard.tasks import update_last_price


class DashboardTests(APITestCase):
    def setUp(self) -> None:
        self.apple_share = Share.objects.create(
            figi="BBG000B9XRY4",
            isin="US0378331005",
            name="Apple",
            ticker="AAPL",
            currency="usd",
            uid="a9eb4238-eba9-488c-b102-b6140fd08e38",
            last_price=100.50,
            is_trend_high=True,
        )

        self.second_company = {
            "figi": "BBG000B9XRY5",
            "isin": "US0378331004",
            "name": "Company_test",
            "ticker": "TESTTEST",
            "currency": "usd",
            "uid": "a9eb4238-eba9-488c-b102-b6140fd08e39",
            "last_price": 1.50,
            "is_trend_high": False,
        }

    def test_share_list_html(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_share_list(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        apple_share = response.json().get("results")[0]
        self.assertEqual(apple_share["id"], self.apple_share.id)
        self.assertEqual(apple_share["figi"], self.apple_share.figi)
        self.assertEqual(apple_share["isin"], self.apple_share.isin)
        self.assertEqual(apple_share["name"], self.apple_share.name)
        self.assertEqual(apple_share["ticker"], self.apple_share.ticker)
        self.assertEqual(apple_share["currency"], self.apple_share.currency)

    def test_share_detail(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.get(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_share_detail_invalid(self):
        response = self.client.get("/api/v1/shares/2/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_html_share_detail_invalid(self):
        response = self.client.get("/999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_guest_cannot_use_html_share_management_views(self):
        for path in ("/create", "/update/1", "/delete/1"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(response, reverse("dashboard:index"))

    def test_share_update(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.put(
            f"/api/v1/shares/{share_detail['id']}/",
            {
                "id": share_detail["id"],
                "figi": self.apple_share.figi,
                "isin": self.apple_share.isin,
                "name": f"{self.apple_share.name}_test",
                "ticker": self.apple_share.ticker,
                "uid": self.apple_share.uid,
                "currency": self.apple_share.currency,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["figi"], self.apple_share.figi)
        self.assertEqual(body["name"], f"{self.apple_share.name}_test")

    def test_share_update_invalid(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.put(
            f"/api/v1/shares/{share_detail['id']}/",
            {
                "figi": self.apple_share.figi,
                "name": f"{self.apple_share.name}_test",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_create(self):
        response = self.client.post(
            "/api/v1/shares/", self.second_company, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["figi"], self.second_company["figi"])
        self.assertEqual(body["name"], self.second_company["name"])
        self.assertEqual(body["ticker"], self.second_company["ticker"])
        self.assertEqual(body["uid"], self.second_company["uid"])

        response = self.client.get("/api/v1/shares/")
        self.assertEqual(len(response.data["results"]), 2)

    def test_share_create_rejects_duplicate_uid(self):
        first_response = self.client.post(
            "/api/v1/shares/", self.second_company, format="json"
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        duplicate_uid_share = {
            **self.second_company,
            "figi": "BBG000B9XRY6",
            "isin": "US0378331003",
            "name": "Another company",
            "ticker": "OTHER",
        }
        response = self.client.post(
            "/api/v1/shares/", duplicate_uid_share, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("uid", response.data)

    def test_share_create_invalid(self):
        response = self.client.post(
            "/api/v1/shares/", {"figi": "BBG000B9XRY5"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_delete(self):
        response = self.client.get("/api/v1/shares/")
        share_detail = response.json().get("results")[0]
        response = self.client.delete(f"/api/v1/shares/{share_detail['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_share_delete_invalid(self):
        response = self.client.delete("/api/v1/shares/3/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "new@example.com",
                "password1": "first-password",
                "password2": "different-password",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Введенные пароли не совпадают")

    def test_registration_and_login_round_trip(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "NewUser@example.com",
                "password1": "a-valid-password",
                "password2": "a-valid-password",
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        user = get_user_model().objects.get(email="newuser@example.com")
        self.assertEqual(user.username, "newuser@example.com")

        self.client.get(reverse("user:logout"))
        response = self.client.post(
            reverse("user:auth"),
            {"email": "NEWUSER@example.com", "password": "a-valid-password"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))

    def test_login_invalid_form_returns_form_errors(self):
        response = self.client.post(reverse("user:auth"), {"email": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_last_price_saves_fraction_trend_and_market_time(self):
        market_time = timezone.now()
        with patch("dashboard.tasks.get_last_data", return_value=(100.75, market_time)):
            update_last_price.run()

        self.apple_share.refresh_from_db()
        self.assertEqual(self.apple_share.last_price, 100.75)
        self.assertTrue(self.apple_share.is_trend_high)
        self.assertEqual(self.apple_share.updated_at, market_time)

    def test_money_value_conversion_keeps_fraction(self):
        value = SimpleNamespace(units=123, nano=450_000_000)
        self.assertEqual(money_value_to_float(value), 123.45)

    def test_market_data_reports_missing_optional_sdk(self):
        with patch.dict(sys.modules, {"tinkoff": None}):
            with self.assertRaisesRegex(
                MarketDataError, "optional tinkoff-investments"
            ):
                from dashboard.services.market_data import get_last_data

                get_last_data(self.apple_share)

    def test_update_task_preserves_prices_when_sdk_is_missing(self):
        previous_price = self.apple_share.last_price
        previous_trend = self.apple_share.is_trend_high
        previous_updated_at = self.apple_share.updated_at

        with patch.dict(sys.modules, {"tinkoff": None}):
            update_last_price.run()

        self.apple_share.refresh_from_db()
        self.assertEqual(self.apple_share.last_price, previous_price)
        self.assertEqual(self.apple_share.is_trend_high, previous_trend)
        self.assertEqual(self.apple_share.updated_at, previous_updated_at)

    def test_get_last_data_parses_mocked_tinkoff_response(self):
        market_time = timezone.now()
        price = SimpleNamespace(units=123, nano=450_000_000)
        last_price = SimpleNamespace(price=price, time=market_time)
        tinkoff_module = ModuleType("tinkoff")
        tinkoff_module.__path__ = []
        invest_module = ModuleType("tinkoff.invest")
        invest_module.__path__ = []
        client = MagicMock()
        client.__enter__.return_value = client
        client.market_data.get_last_prices.return_value.last_prices = [last_price]
        invest_module.Client = MagicMock(return_value=client)
        tinkoff_module.invest = invest_module
        grpc_module = ModuleType("grpc")
        grpc_module.RpcError = type("RpcError", (Exception,), {})

        with patch.dict(
            sys.modules,
            {
                "tinkoff": tinkoff_module,
                "tinkoff.invest": invest_module,
                "grpc": grpc_module,
            },
        ):
            result = get_last_data(self.apple_share)

        self.assertEqual(result, (123.45, market_time))

    def test_graph_uses_fractional_candle_close(self):
        candle = SimpleNamespace(
            time=timezone.now(),
            close=SimpleNamespace(units=123, nano=450_000_000),
        )
        tinkoff_module = ModuleType("tinkoff")
        tinkoff_module.__path__ = []
        invest_module = ModuleType("tinkoff.invest")
        invest_module.__path__ = []
        invest_module.CandleInterval = SimpleNamespace(CANDLE_INTERVAL_DAY="day")
        invest_module.Client = MagicMock()
        utils_module = ModuleType("tinkoff.invest.utils")
        utils_module.now = timezone.now
        tinkoff_module.invest = invest_module

        with patch.dict(
            sys.modules,
            {
                "tinkoff": tinkoff_module,
                "tinkoff.invest": invest_module,
                "tinkoff.invest.utils": utils_module,
            },
        ):
            with patch(
                "dashboard.services.graph.plot", return_value="<div></div>"
            ) as plot:
                (
                    invest_module.Client.return_value.__enter__.return_value.get_all_candles
                ).return_value = [candle]
                result = get_graph(self.apple_share)

        self.assertEqual(result, "<div></div>")
        trace = plot.call_args.args[0][0]
        self.assertEqual(list(trace.y), [123.45])

    def test_add_shares_is_idempotent_for_existing_figi(self):
        instrument = SimpleNamespace(
            figi=self.apple_share.figi,
            isin=self.apple_share.isin,
            name="Renamed Apple",
            ticker=self.apple_share.ticker,
            currency=self.apple_share.currency,
            uid=self.apple_share.uid,
        )
        tinkoff_module = ModuleType("tinkoff")
        tinkoff_module.__path__ = []
        invest_module = ModuleType("tinkoff.invest")
        invest_module.__path__ = []
        client = MagicMock()
        client.__enter__.return_value = client
        client.instruments.shares.return_value.instruments = [instrument]
        invest_module.Client = MagicMock(return_value=client)
        tinkoff_module.invest = invest_module

        with patch.dict(
            sys.modules,
            {"tinkoff": tinkoff_module, "tinkoff.invest": invest_module},
        ):
            call_command("add_shares")

        self.assertEqual(Share.objects.count(), 1)
        self.apple_share.refresh_from_db()
        self.assertEqual(self.apple_share.name, "Apple")

    def create_watchlist_item(self, user, target="100.00", **kwargs):
        return WatchlistItem.objects.create(
            user=user,
            share=self.apple_share,
            target_price=target,
            **kwargs,
        )

    def create_authenticated_user(self, username):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.com", password="password"
        )
        self.client.force_login(user)
        return user

    def test_watchlist_web_create_update_and_delete(self):
        user = self.create_authenticated_user("watcher")
        response = self.client.post(
            reverse("dashboard:watchlist_add"),
            {"share": self.apple_share.pk, "target_price": "100.00"},
        )
        self.assertRedirects(response, reverse("dashboard:watchlist"))

        item = WatchlistItem.objects.get(user=user, share=self.apple_share)
        response = self.client.get(reverse("dashboard:watchlist"))
        self.assertContains(response, "Список наблюдения")
        self.assertContains(response, "Apple")

        response = self.client.post(
            reverse("dashboard:watchlist_update", args=[item.pk]),
            {"target_price": "110.50"},
        )
        self.assertRedirects(response, reverse("dashboard:watchlist"))
        item.refresh_from_db()
        self.assertEqual(item.target_price, Decimal("110.500000"))

        response = self.client.post(
            reverse("dashboard:watchlist_delete", args=[item.pk])
        )
        self.assertRedirects(response, reverse("dashboard:watchlist"))
        self.assertFalse(WatchlistItem.objects.filter(pk=item.pk).exists())

    def test_watchlist_rejects_non_positive_target(self):
        self.create_authenticated_user("watcher")
        response = self.client.post(
            reverse("dashboard:watchlist_add"),
            {"share": self.apple_share.pk, "target_price": "0"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(WatchlistItem.objects.exists())

    def test_watchlist_and_notifications_are_private(self):
        owner = get_user_model().objects.create_user(
            username="owner", password="password"
        )
        other_user = self.create_authenticated_user("other")
        item = self.create_watchlist_item(owner)
        alert = PriceAlert.objects.create(
            user=owner,
            share=self.apple_share,
            share_name="OWNER-ONLY-ALERT",
            ticker="ONLY",
            target_price=Decimal("987.123"),
            triggered_price=Decimal("988.123"),
        )

        response = self.client.get(reverse("dashboard:watchlist"))
        self.assertNotContains(response, "OWNER-ONLY-ALERT")
        self.assertNotContains(response, "988.123")

        for route, method, data in (
            ("dashboard:watchlist_update", self.client.get, None),
            ("dashboard:watchlist_update", self.client.post, {"target_price": "1"}),
            ("dashboard:watchlist_delete", self.client.get, None),
            ("dashboard:watchlist_delete", self.client.post, {}),
        ):
            with self.subTest(route=route, method=method.__name__):
                response = (
                    method(reverse(route, args=[item.pk]), data=data)
                    if data is not None
                    else method(reverse(route, args=[item.pk]))
                )
                self.assertEqual(response.status_code, 404)

        item.refresh_from_db()
        self.assertEqual(item.target_price, Decimal("100.000000"))
        self.assertTrue(PriceAlert.objects.filter(pk=alert.pk, user=owner).exists())
        self.assertNotEqual(other_user, owner)

    def test_watchlist_requires_login(self):
        response = self.client.get(reverse("dashboard:watchlist"))
        self.assertRedirects(
            response, f"{reverse('user:auth')}?next={reverse('dashboard:watchlist')}"
        )

    def test_target_alerts_once_per_crossing_sequence(self):
        user = get_user_model().objects.create_user(
            username="sequence", password="password"
        )
        item = self.create_watchlist_item(user, target="100")

        for price in (99, 100, 101, 98, 100):
            with self.subTest(price=price):
                with patch(
                    "dashboard.tasks.get_last_data",
                    return_value=(price, timezone.now()),
                ):
                    update_last_price.run()

        alerts = PriceAlert.objects.filter(user=user, share=self.apple_share)
        self.assertEqual(alerts.count(), 2)
        self.assertEqual(
            list(
                alerts.order_by("created_at").values_list("triggered_price", flat=True)
            ),
            [Decimal("100.000000"), Decimal("100.000000")],
        )
        item.refresh_from_db()
        self.assertTrue(item.is_above_target)

    def test_decimal_target_alerts_on_exact_threshold(self):
        user = get_user_model().objects.create_user(
            username="decimal", password="password"
        )
        self.create_watchlist_item(user, target="100.50")

        for price in (100.49, 100.50):
            with patch(
                "dashboard.tasks.get_last_data",
                return_value=(price, timezone.now()),
            ):
                update_last_price.run()

        alert = PriceAlert.objects.get(user=user, share=self.apple_share)
        self.assertEqual(alert.target_price, Decimal("100.500000"))
        self.assertEqual(alert.triggered_price, Decimal("100.500000"))

    def test_missing_quote_does_not_change_watchlist_state(self):
        user = get_user_model().objects.create_user(
            username="noquote", password="password"
        )
        item = self.create_watchlist_item(user, target="100", is_above_target=True)
        previous_price = self.apple_share.last_price

        with patch("dashboard.tasks.get_last_data", side_effect=IndexError):
            update_last_price.run()

        item.refresh_from_db()
        self.apple_share.refresh_from_db()
        self.assertTrue(item.is_above_target)
        self.assertEqual(self.apple_share.last_price, previous_price)
        self.assertFalse(PriceAlert.objects.filter(user=user).exists())
