from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import WatchlistForm, WatchRuleForm
from .models import Notification, Watchlist, WatchRule


@login_required
def index(request):
    lists = Watchlist.objects.filter(owner=request.user).prefetch_related(
        "rules__share", "rules__notification"
    )
    return render(request, "monitoring/index.html", {"watchlists": lists})


@login_required
def create_list(request):
    form = WatchlistForm(request.POST if request.method == "POST" else None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("monitoring:index")
    return render(request, "monitoring/form.html", {"form": form, "title": "Новый список наблюдения"})


@login_required
@require_POST
def delete_list(request, pk):
    get_object_or_404(Watchlist, pk=pk, owner=request.user).delete()
    return redirect("monitoring:index")


@login_required
def create_rule(request, pk):
    watchlist = get_object_or_404(Watchlist, pk=pk, owner=request.user)
    form = WatchRuleForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        rule = form.save(commit=False)
        rule.watchlist = watchlist
        rule.save()
        return redirect("monitoring:index")
    return render(request, "monitoring/form.html", {
        "form": form, "title": f"Добавить акцию в список «{watchlist.name}»"
    })


@login_required
@require_POST
def delete_rule(request, pk):
    get_object_or_404(WatchRule, pk=pk, watchlist__owner=request.user).delete()
    return redirect("monitoring:index")


@login_required
def inbox(request):
    from django.core.paginator import Paginator

    page = Paginator(Notification.objects.filter(owner=request.user), 50).get_page(request.GET.get("page"))
    return render(request, "monitoring/inbox.html", {"page_obj": page})


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, owner=request.user)
    notification.is_read = True
    notification.save(update_fields=("is_read",))
    return redirect("monitoring:inbox")
