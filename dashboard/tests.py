import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import Share
from dashboard.services.graph import get_graph
from dashboard.services.market_data import get_last_data, money_value_to_float
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
            with self.assertRaisesRegex(RuntimeError, "optional tinkoff-investments"):
                from dashboard.services.market_data import get_last_data

                get_last_data(self.apple_share)

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
