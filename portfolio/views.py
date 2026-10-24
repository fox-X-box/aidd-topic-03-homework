from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PortfolioForm, TradeForm
from .models import Portfolio
from .services import execute_trade, portfolio_summary


def owned_portfolio(request, pk):
    return get_object_or_404(Portfolio, pk=pk, owner=request.user)


@login_required(login_url="user:auth")
def index(request):
    form = PortfolioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        portfolio = form.save(commit=False)
        portfolio.owner = request.user
        portfolio.cash = portfolio.initial_cash
        portfolio.save()
        return redirect("portfolio:detail", pk=portfolio.pk)
    return render(request, "portfolio/index.html", {
        "portfolios": Portfolio.objects.filter(owner=request.user), "form": form,
    })


def render_detail(request, portfolio, form=None):
    return render(request, "portfolio/detail.html", {
        "portfolio": portfolio, "summary": portfolio_summary(portfolio),
        "trades": Paginator(portfolio.trades.select_related("share"), 50).get_page(request.GET.get("page")),
        "form": form if form is not None else TradeForm(portfolio=portfolio),
    })


@login_required(login_url="user:auth")
def detail(request, pk):
    return render_detail(request, owned_portfolio(request, pk))


@login_required(login_url="user:auth")
@require_POST
def trade(request, pk):
    portfolio = owned_portfolio(request, pk)
    form = TradeForm(request.POST, portfolio=portfolio)
    if form.is_valid():
        share = form.cleaned_data["share"]
        try:
            execute_trade(portfolio, share, form.cleaned_data["side"], form.cleaned_data["quantity"], share.last_price)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("portfolio:detail", pk=portfolio.pk)
    return render_detail(request, portfolio, form)
