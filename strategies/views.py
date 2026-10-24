from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import StrategyForm
from .models import Strategy


@login_required
def index(request):
    strategies = Strategy.objects.filter(owner=request.user).select_related(
        "share", "portfolio", "execution__trade"
    )
    return render(request, "strategies/index.html", {"strategies": strategies})


@login_required
def create(request):
    form = StrategyForm(request.POST if request.method == "POST" else None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("strategies:index")
    return render(request, "strategies/create.html", {"form": form})


@login_required
@require_POST
def cancel(request, pk):
    with transaction.atomic():
        strategy = get_object_or_404(Strategy.objects.select_for_update(), pk=pk, owner=request.user)
        if strategy.status == Strategy.Status.PENDING:
            strategy.enabled = False
            strategy.status = Strategy.Status.CANCELLED
            strategy.save(update_fields=["enabled", "status"])
    return redirect("strategies:index")
