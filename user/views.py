from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm


class AuthView(View):
    """Авторизация."""

    @staticmethod
    def get(request):
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "user/auth.html",
                {"form": form, "error": "Введите корректные email и пароль."},
            )

        user = authenticate(
            request,
            username=form.cleaned_data["email"].lower(),
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect("dashboard:index")

        return render(
            request,
            "user/auth.html",
            {
                "form": form,
                "error": "Неверный логин или пароль! Повторите попытку.",
            },
        )


class RegistrationView(View):
    """Регистрация."""

    @staticmethod
    def get(request):
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard:index")

        return render(
            request,
            "user/registration.html",
            {"form": form, "error": form.errors.as_text()},
        )


class LogoutView(View):
    """Выход."""

    @staticmethod
    def get(request):
        logout(request)
        return redirect("dashboard:index")
