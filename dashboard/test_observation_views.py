from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Notification, Observation, Share


class ObservationViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="owner")
        cls.other = User.objects.create_user(username="other")
        cls.stock = Share.objects.create(
            figi="TESTFIGI", isin="TESTISIN", uid="test-uid",
            ticker="TST", name="Тестовая акция", currency="usd",
        )

    def test_guest_and_owner_access(self):
        url = reverse("dashboard:observations")
        self.assertEqual(url, "/observations/")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("user:auth") + "?next=/observations/")

        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/observations.html")

    def test_create_update_delete(self):
        self.client.force_login(self.owner)
        create = reverse("dashboard:observation_create")
        self.assertTemplateUsed(self.client.get(create), "dashboard/observation_form.html")
        response = self.client.post(create, {"stock": self.stock.pk, "target_price": "100.50"})
        self.assertRedirects(response, reverse("dashboard:observations"))
        obs = Observation.objects.get(owner=self.owner, stock=self.stock)
        self.assertEqual(obs.target_price, Decimal("100.50"))

        edit = reverse("dashboard:observation_update", args=[obs.pk])
        response = self.client.post(edit, {"target_price": "110.25"})
        self.assertRedirects(response, reverse("dashboard:observations"))
        obs.refresh_from_db()
        self.assertEqual(obs.target_price, Decimal("110.25"))

        delete = reverse("dashboard:observation_delete", args=[obs.pk])
        self.assertTemplateUsed(self.client.get(delete), "dashboard/observation_confirm_delete.html")
        self.client.post(delete)
        self.assertFalse(Observation.objects.filter(pk=obs.pk).exists())

    def test_positive_price_required(self):
        self.client.force_login(self.owner)
        create = reverse("dashboard:observation_create")
        for price in ("0", "-1"):
            with self.subTest(price=price):
                response = self.client.post(create, {"stock": self.stock.pk, "target_price": price})
                self.assertEqual(response.status_code, 200)
                self.assertIn("target_price", response.context["form"].errors)
                self.assertFalse(Observation.objects.filter(owner=self.owner).exists())

    def test_other_user_cannot_access_observation(self):
        obs = Observation.objects.create(owner=self.owner, stock=self.stock, target_price="100.50")
        Notification.objects.create(
            observation=obs, event_time=timezone.now(),
            target_price="100.50", actual_price="123.45",
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("dashboard:observations"))
        self.assertEqual(response.context["notifications"].get().observation_id, obs.pk)
        self.assertRegex(response.content.decode(), r"123[.,]45")
        self.client.force_login(self.other)
        response = self.client.get(reverse("dashboard:observations"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(obs, response.context["observations"])
        self.assertNotContains(response, "123.45")
        self.assertNotContains(response, "123,45")

        for name in ("observation_update", "observation_delete"):
            with self.subTest(route=name):
                url = reverse(f"dashboard:{name}", args=[obs.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {"target_price": "1"}).status_code, 404)

        obs.refresh_from_db()
        self.assertEqual(obs.target_price, Decimal("100.50"))
