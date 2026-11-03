from django.test import TestCase
from unittest.mock import patch

from dashboard.models import Share, Observation, Notification
from dashboard.tasks import update_last_price


class ObservationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create(username="testuser")
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
        self.observation = Observation.objects.create(
            owner=self.user,
            stock=self.apple_share,
            target_price=100,
            target_reached=False,
        )

    def test_goal_100_notification_sequence(self):
        # Цель 100. Подай цены 99 → 100 → 101 → 98 → 100.
        # Число уведомлений после каждого шага: 0 → 1 → 1 → 1 → 2.
        # target_reached: False → True → True → False → True.

        # Шаг 1: цена 99 (цель не достигнута)
        with patch("dashboard.tasks.get_last_data", return_value=[99, "2024-01-01T00:00:00"]):
            update_last_price()
        self.apple_share.refresh_from_db()
        self.observation.refresh_from_db()
        self.assertFalse(self.observation.target_reached)
        self.assertEqual(Notification.objects.filter(observation=self.observation).count(), 0)

        # Шаг 2: цена 100 (цель достигнута)
        with patch("dashboard.tasks.get_last_data", return_value=[100, "2024-01-01T00:00:00"]):
            update_last_price()
        self.apple_share.refresh_from_db()
        self.observation.refresh_from_db()
        self.assertTrue(self.observation.target_reached)
        self.assertEqual(Notification.objects.filter(observation=self.observation).count(), 1)

        # Шаг 3: цена 101 (цель уже достигнута, повторное уведомление не создается)
        with patch("dashboard.tasks.get_last_data", return_value=[101, "2024-01-01T00:00:00"]):
            update_last_price()
        self.observation.refresh_from_db()
        self.assertEqual(Notification.objects.filter(observation=self.observation).count(), 1)

        # Шаг 4: цена 98 (цена опустилась ниже цели, сбросим флаг)
        with patch("dashboard.tasks.get_last_data", return_value=[98, "2024-01-01T00:00:00"]):
            update_last_price()
        self.observation.refresh_from_db()
        self.assertFalse(self.observation.target_reached)

        # Шаг 5: цена 100 (опять >= цели, создаем новое уведомление)
        with patch("dashboard.tasks.get_last_data", return_value=[100, "2024-01-01T00:00:00"]):
            update_last_price()
        self.observation.refresh_from_db()
        self.assertEqual(Notification.objects.filter(observation=self.observation).count(), 2)

    def test_goal_100_50(self):
        # Цель 100.50. При 100.49 уведомлений ноль. При 100.50 — ровно одно.
        # Проверь сохраненную целевую и фактическую цену.
        self.observation.target_price = 100.50
        self.observation.save()
        self.observation.refresh_from_db()

        # Шаг 1: цена 100.49 (меньше цели 100.50)
        with patch("dashboard.tasks.get_last_data", return_value=[100.49, "2024-01-01T00:00:00"]):
            update_last_price()
        self.apple_share.refresh_from_db()
        self.observation.refresh_from_db()
        self.assertFalse(self.observation.target_reached)
        self.assertEqual(Notification.objects.filter(observation=self.observation).count(), 0)

        # Шаг 2: цена 100.50 (достигли цели)
        with patch("dashboard.tasks.get_last_data", return_value=[100.50, "2024-01-01T00:00:00"]):
            update_last_price()
        self.observation.refresh_from_db()
        self.assertTrue(self.observation.target_reached)
        self.assertEqual(Notification.objects.filter(observation=self.observation).count(), 1)
        notif = Notification.objects.get(observation=self.observation)
        self.assertEqual(float(notif.target_price), 100.50)
        self.assertEqual(float(notif.actual_price), 100.50)

    def test_preserve_when_quote_unavailable(self):
        # Сначала достигni цели и получи одно уведомление.
        # Затем верни из источника котировок None.
        # Проверь, что уведомление осталось одно, target_reached остался True,
        # а последняя цена акции сохранилась (становится 100 после достижения цели).
        with patch("dashboard.tasks.get_last_data", return_value=[100, "2024-01-01T00:00:00"]):
            update_last_price()
        self.observation.refresh_from_db()
        self.apple_share.refresh_from_db()
        self.assertTrue(self.observation.target_reached)
        notif_count_before = Notification.objects.filter(observation=self.observation).count()
        self.assertEqual(notif_count_before, 1)
        # Цена теперь 100 (была достигнута цель)
        self.assertEqual(float(self.apple_share.last_price), 100)
        with patch("dashboard.tasks.get_last_data", return_value=None):
            update_last_price()
        self.observation.refresh_from_db()
        self.apple_share.refresh_from_db()
        self.assertTrue(self.observation.target_reached)
        notif_count_after = Notification.objects.filter(observation=self.observation).count()
        self.assertEqual(notif_count_after, notif_count_before)
        # Цена не менялась при отсутствии котировок
        self.assertEqual(float(self.apple_share.last_price), 100)