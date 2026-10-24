from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Share
from .forms import WatchRuleForm
from .models import Notification, Watchlist, WatchRule
from .services import evaluate_alerts


def make_share():
    return Share.objects.create(
        figi="TEST-FIGI", isin="TEST-ISIN", name="Test company",
        ticker="TEST", currency="rub", uid="TEST-UID", last_price=Decimal("100.25"),
    )


class MonitoringTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("owner", password="Test-password-21")
        self.other = get_user_model().objects.create_user("other", password="Other-password-21")
        self.share = make_share()
        self.watchlist = Watchlist.objects.create(owner=self.owner, name="Основной")

    def rule(self, direction="above", target="100.25"):
        return WatchRule.objects.create(
            watchlist=self.watchlist, share=self.share,
            direction=direction, target_price=Decimal(target),
        )

    def test_inclusive_above_and_below_thresholds_and_no_duplicate_on_reentry(self):
        self.rule()
        self.assertEqual(evaluate_alerts(self.share, "100.24"), 0)
        observed_at = timezone.now()
        self.assertEqual(evaluate_alerts(self.share, "100.25", observed_at), 1)
        self.assertEqual(evaluate_alerts(self.share, "101.0000000000"), 0)
        self.assertEqual(evaluate_alerts(self.share, "90"), 0)
        self.assertEqual(evaluate_alerts(self.share, "110"), 0)
        notification = Notification.objects.get()
        self.assertEqual(notification.owner, self.owner)
        self.assertEqual(notification.observed_at, observed_at)
        self.assertEqual(notification.observed_price, Decimal("100.25"))
        self.assertEqual(notification.currency, "rub")
        self.rule("below", "99.125")
        self.assertEqual(evaluate_alerts(self.share, "99.126"), 0)
        self.assertEqual(evaluate_alerts(self.share, "99.125"), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_nonfinite_nonpositive_overflow_and_overprecision_rejected(self):
        self.rule()
        for value in ("NaN", "Infinity", "-Infinity", "0", "-1", "garbage", None, "1e15", "1.0000000001"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                evaluate_alerts(self.share, value)
        self.assertFalse(Notification.objects.exists())

    def test_rule_form_rejects_invalid_thresholds(self):
        for target in ("0", "-1", "NaN", "Infinity", "0.0000000001"):
            with self.subTest(target=target):
                form = WatchRuleForm(data={"share": self.share.pk, "direction": "above", "target_price": target})
                self.assertFalse(form.is_valid())
                self.assertIn("target_price", form.errors)

    def test_rule_delete_keeps_notification_and_new_rule_can_rearm(self):
        rule = self.rule()
        evaluate_alerts(self.share, "101")
        rule.delete()
        notification = Notification.objects.get()
        self.assertIsNone(notification.rule_id)
        self.rule()
        self.assertEqual(evaluate_alerts(self.share, "101"), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_authentication_and_owner_scoping_all_mutations(self):
        rule = self.rule()
        evaluate_alerts(self.share, "101")
        notification = Notification.objects.get()
        self.assertEqual(self.client.get(reverse("monitoring:index")).status_code, 302)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("monitoring:index")), self.watchlist.name)
        self.assertNotContains(self.client.get(reverse("monitoring:inbox")), self.share.ticker)
        for name, pk in (
            ("create_rule", self.watchlist.pk),
            ("delete_list", self.watchlist.pk),
            ("delete_rule", rule.pk),
            ("mark_read", notification.pk),
        ):
            with self.subTest(name=name):
                response = self.client.post(reverse(f"monitoring:{name}", args=[pk]), {})
                self.assertEqual(response.status_code, 404)
        self.assertTrue(WatchRule.objects.filter(pk=rule.pk).exists())
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_ui_creates_rule_lists_and_marks_notification_read(self):
        self.client.force_login(self.owner)
        url = reverse("monitoring:create_list")
        response = self.client.post(url, {"name": "Новые акции"})
        self.assertRedirects(response, reverse("monitoring:index"))
        self.assertEqual(Watchlist.objects.get(name="Новые акции").owner, self.owner)
        response = self.client.post(url, {"name": "Новые акции"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Список с таким названием уже существует")
        response = self.client.post(reverse("monitoring:create_rule", args=[self.watchlist.pk]), {
            "share": self.share.pk, "direction": "above", "target_price": "100.25",
        })
        self.assertRedirects(response, reverse("monitoring:index"))
        evaluate_alerts(self.share, "101")
        notification = Notification.objects.get()
        self.assertContains(self.client.get(reverse("monitoring:inbox")), "TEST")
        response = self.client.post(reverse("monitoring:mark_read", args=[notification.pk]))
        self.assertRedirects(response, reverse("monitoring:inbox"))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_get_cannot_delete_or_mark_read(self):
        rule = self.rule()
        evaluate_alerts(self.share, "101")
        notification = Notification.objects.get()
        self.client.force_login(self.owner)
        for name, pk in (("delete_list", self.watchlist.pk), ("delete_rule", rule.pk), ("mark_read", notification.pk)):
            self.assertEqual(self.client.get(reverse(f"monitoring:{name}", args=[pk])).status_code, 405)
        self.assertTrue(WatchRule.objects.filter(pk=rule.pk).exists())


class ConcurrentNotificationTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_ticks_only_deliver_once(self):
        user = get_user_model().objects.create_user("concurrent")
        share = make_share()
        watchlist = Watchlist.objects.create(owner=user, name="Concurrent")
        WatchRule.objects.create(watchlist=watchlist, share=share, direction="above", target_price="100")
        barrier = Barrier(2)

        def evaluate():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return evaluate_alerts(Share.objects.get(pk=share.pk), "101")
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: evaluate(), range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(Notification.objects.count(), 1)
