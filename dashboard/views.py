from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, View, UpdateView

from .forms import ObservationCreateForm, ObservationTargetForm, ShareModelForm
from .models import Share, Observation, Notification
from .services.graph import get_graph
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


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
        share = get_object_or_404(Share, id=pk)
        plot_div = get_graph(share)

        return render(
            request,
            "dashboard/detail.html",
            {
                "plot_div": plot_div,
                "share": share,
                "graph_available": plot_div is not None,
            },
        )


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


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


class ObservationAccessMixin(LoginRequiredMixin):
    login_url = reverse_lazy("user:auth")
    success_url = reverse_lazy("dashboard:observations")
    model = Observation

    def get_queryset(self):
        return Observation.objects.filter(owner=self.request.user).select_related("stock")


class ObservationListView(ObservationAccessMixin, ListView):
    template_name = "dashboard/observations.html"
    context_object_name = "observations"
    ordering = ["stock__ticker"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["notifications"] = Notification.objects.filter(
            observation__owner=self.request.user
        ).select_related("observation__stock").order_by("-event_time", "-pk")
        return context


class ObservationCreateView(ObservationAccessMixin, CreateView):
    template_name = "dashboard/observation_form.html"
    form_class = ObservationCreateForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Observation(owner=self.request.user)
        return kwargs

    def form_valid(self, form):
        self.object, created = Observation.objects.get_or_create(
            owner=self.request.user, stock=form.cleaned_data["stock"],
            defaults={"target_price": form.cleaned_data["target_price"]},
        )
        if not created:
            form.add_error("stock", "Вы уже наблюдаете за этой акцией.")
            return self.form_invalid(form)
        return redirect(self.success_url)


class ObservationUpdateView(ObservationAccessMixin, UpdateView):
    template_name = "dashboard/observation_form.html"
    form_class = ObservationTargetForm

    def form_valid(self, form):
        if "target_price" in form.changed_data:
            self.get_queryset().filter(pk=self.object.pk).update(
                target_price=form.cleaned_data["target_price"], target_reached=False
            )
        return redirect(self.success_url)


class ObservationDeleteView(ObservationAccessMixin, DeleteView):
    template_name = "dashboard/observation_confirm_delete.html"
