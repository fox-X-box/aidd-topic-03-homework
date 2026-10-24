from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm
from .models import User


class AuthView(View):
    """Вход по e-mail с проверкой данных до обращения к аутентификации."""

    @staticmethod
    def get(request):
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            # Поддерживаем учетные записи исходного проекта с разным регистром.
            account = User.objects.filter(username__iexact=email).first()
            user = authenticate(
                request,
                username=account.username if account else email,
                password=form.cleaned_data["password"],
            )
            if user is not None:
                login(request, user)
                return redirect("dashboard:index")
            form.add_error(None, "Неверный логин или пароль! Повторите попытку.")
        return render(request, "user/auth.html", {"form": form})


class RegistrationView(View):
    """Создание пользователя и вход после успешной валидации."""

    @staticmethod
    def get(request):
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                # Нормализованный username уникален и защищает от гонки регистраций.
                form.add_error("email", "Данный e-mail уже зарегистрирован.")
            else:
                login(request, user)
                return redirect("dashboard:index")
        return render(request, "user/registration.html", {"form": form})


class LogoutView(View):
    """Завершение сессии через POST с CSRF-защитой middleware."""

    @staticmethod
    def post(request):
        logout(request)
        return redirect("dashboard:index")
