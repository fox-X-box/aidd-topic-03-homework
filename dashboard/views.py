from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .forms import ShareModelForm, WatchlistCreateForm, WatchlistUpdateForm
from .models import PriceAlert, Share, WatchlistItem
from .services.graph import get_graph


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect("dashboard:index")


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, pk=pk)

        return render(
            request,
            "dashboard/detail.html",
            {"plot_div": get_graph(share), "share": share},
        )


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class WatchlistView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/watchlist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["watchlist"] = WatchlistItem.objects.filter(
            user=self.request.user
        ).select_related("share")
        context["alerts"] = PriceAlert.objects.filter(user=self.request.user)
        context["create_form"] = WatchlistCreateForm(user=self.request.user)
        return context


class WatchlistCreateView(LoginRequiredMixin, CreateView):
    form_class = WatchlistCreateForm
    template_name = "dashboard/watchlist_form.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class WatchlistUpdateView(LoginRequiredMixin, UpdateView):
    model = WatchlistItem
    form_class = WatchlistUpdateForm
    template_name = "dashboard/watchlist_form.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user)

    def form_valid(self, form):
        form.instance.is_above_target = False
        return super().form_valid(form)


class WatchlistDeleteView(LoginRequiredMixin, DeleteView):
    model = WatchlistItem
    template_name = "dashboard/watchlist_confirm_delete.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user)


class ShareUpdateView(IsUserAuthenticatedMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(IsUserAuthenticatedMixin, DeleteView):
    """Удаление задачи"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")
