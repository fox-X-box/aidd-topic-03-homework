from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from user.models import User


class EmailForm(forms.Form):
    email = forms.EmailField(
        max_length=User._meta.get_field("username").max_length,
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class RegistrationForm(EmailForm):
    """Регистрация с нормализацией e-mail и стандартной проверкой пароля."""

    password1 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
    password2 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Повторите пароль"}
        ),
    )

    def clean_email(self):
        email = super().clean_email()
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            raise ValidationError("Данный e-mail уже зарегистрирован.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Введенные пароли не совпадают.")
        if password1:
            email = cleaned_data.get("email", "")
            candidate = User(username=email, email=email)
            try:
                validate_password(password1, candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        return User.objects.create_user(
            username=email, email=email, password=self.cleaned_data["password1"]
        )


class AuthForm(EmailForm):
    """Форма входа; неполный POST обрабатывается обычными ошибками полей."""

    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
