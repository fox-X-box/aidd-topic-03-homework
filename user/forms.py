from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class RegistrationForm(forms.Form):
    """Форма регистрации пользователей."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )
    password1 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
    password2 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Повторите пароль"}
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if email:
            email = email.lower()
            cleaned_data["email"] = email
            if User.objects.filter(email__iexact=email).exists():
                self.add_error(
                    "email",
                    ValidationError(
                        "Данный e-mail уже зарегистрирован! Введите другой e-mail "
                        "или воспользуйтесь формой авторизации."
                    ),
                )

        if password1 and password2 and password1 != password2:
            self.add_error(None, "Введенные пароли не совпадают")

        return cleaned_data

    def save(self):
        if not self.is_valid():
            raise ValueError("Нельзя создать пользователя по некорректной форме")

        email = self.cleaned_data["email"]
        return User.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password1"],
        )


class AuthForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
