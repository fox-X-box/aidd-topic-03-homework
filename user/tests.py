from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .forms import RegistrationForm
from .models import User


class AuthenticationTests(TestCase):
    password = "N8w!Long-Akciya-Password"

    def register(self, **overrides):
        data = {
            "email": "Investor@Example.COM",
            "password1": self.password,
            "password2": self.password,
        }
        data.update(overrides)
        return self.client.post(reverse("user:registration"), data)

    def test_registration_normalizes_email_hashes_password_and_logs_in(self):
        response = self.register()
        self.assertRedirects(response, reverse("dashboard:index"))
        user = User.objects.get()
        self.assertEqual(user.email, "investor@example.com")
        self.assertEqual(user.username, "investor@example.com")
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user("Investor@Example.COM", "Investor@Example.COM", self.password)
        response = self.register(email="investor@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_missing_fields_does_not_crash(self):
        for data in ({}, {"email": "bad"}, {"email": "valid@example.com"}):
            with self.subTest(data=data):
                response = self.client.post(reverse("user:registration"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 0)

    def test_password_mismatch_is_rendered(self):
        response = self.register(password2="Different!Long-Password")
        self.assertEqual(response.status_code, 200)
        self.assertIn("password2", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 0)

    def test_weak_password_is_rejected(self):
        response = self.register(password1="123", password2="123")
        self.assertEqual(response.status_code, 200)
        self.assertIn("password1", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 0)

    def test_email_must_fit_username_column(self):
        form = RegistrationForm({
            "email": "a" * 64 + "@" + "b" * 63 + "." + "c" * 40 + ".com",
            "password1": self.password,
            "password2": self.password,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_authentication_missing_or_invalid_fields_does_not_crash(self):
        for data in ({}, {"email": "bad"}, {"email": "valid@example.com"}):
            with self.subTest(data=data):
                response = self.client.post(reverse("user:auth"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)

    def test_login_accepts_email_case_and_legacy_username(self):
        account = User.objects.create_user(
            "Investor@Example.COM", "Investor@Example.COM", self.password
        )
        response = self.client.post(reverse("user:auth"), {
            "email": "INVESTOR@EXAMPLE.COM", "password": self.password,
        })
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), account.pk)

    def test_login_invalid_credentials_and_inactive_account(self):
        User.objects.create_user("investor@example.com", password=self.password, is_active=False)
        for password in ("incorrect", self.password):
            response = self.client.post(reverse("user:auth"), {
                "email": "investor@example.com", "password": password,
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].non_field_errors())
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_clears_session(self):
        account = User.objects.create_user("investor@example.com", password=self.password)
        self.client.force_login(account)
        self.assertEqual(self.client.get(reverse("user:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(reverse("user:logout")), reverse("dashboard:index"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_rejects_post_without_csrf_token(self):
        account = User.objects.create_user("investor@example.com", password=self.password)
        client = Client(enforce_csrf_checks=True)
        client.force_login(account)
        self.assertEqual(client.post(reverse("user:logout")).status_code, 403)
        self.assertIn("_auth_user_id", client.session)


class ConcurrentRegistrationTests(TransactionTestCase):
    def test_same_normalized_email_can_only_be_registered_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from unittest.mock import patch

        from django.db import close_old_connections, connection

        if connection.vendor != "postgresql":
            self.skipTest("Real concurrent registration requires PostgreSQL row locking")
        barrier = Barrier(2)
        original_save = RegistrationForm.save

        def synchronized_save(form):
            # Both forms have passed prevalidation before either inserts the user.
            barrier.wait(timeout=10)
            return original_save(form)

        def register(email):
            close_old_connections()
            try:
                response = Client().post(reverse("user:registration"), {
                    "email": email,
                    "password1": "N8w!Long-Akciya-Password",
                    "password2": "N8w!Long-Akciya-Password",
                })
                return response.status_code, response.content.decode()
            finally:
                close_old_connections()

        with patch.object(RegistrationForm, "save", synchronized_save):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(register, ["RACE@example.com", "race@EXAMPLE.COM"]))
        self.assertEqual(sorted(status for status, _ in results), [200, 302])
        self.assertEqual(User.objects.filter(username="race@example.com").count(), 1)
        rejected_body = next(body for status, body in results if status == 200)
        self.assertIn("Данный e-mail уже зарегистрирован.", rejected_body)
