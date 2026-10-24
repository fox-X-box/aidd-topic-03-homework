from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, View, UpdateView

from .forms import ShareModelForm, HistoryRangeForm
from .models import Share
from .services.graph import get_graph
from .services.market_data import MarketDataError


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect('dashboard:index')


class ShareListView(ListView):
    model = Share
    template_name = 'dashboard/list.html'
    paginate_by = 100
    ordering = ['name', 'pk']


class ShareDetailView(View):
    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, pk=pk)
        form = HistoryRangeForm(request.GET)
        end = timezone.now()
        if not form.is_valid():
            return render(request, 'dashboard/detail.html', {'share': share, 'history_form': form}, status=400)
        if form.cleaned_data.get('end'):
            end = datetime.combine(form.cleaned_data['end'], time.max, tzinfo=dt_timezone.utc)
        start = end - timedelta(days=180)
        if form.cleaned_data.get('start'):
            start = datetime.combine(form.cleaned_data['start'], time.min, tzinfo=dt_timezone.utc)
        if start > end:
            form.add_error(None, 'Начало периода не может быть позже окончания.')
            return render(request, 'dashboard/detail.html', {'share': share, 'history_form': form}, status=400)
        history = list(share.price_history.filter(observed_at__gte=start, observed_at__lte=end))
        absolute = percent = None
        if len(history) >= 2:
            absolute = history[-1].price - history[0].price
            if history[0].price:
                percent = absolute / history[0].price * Decimal(100)
        error = None
        try:
            graph = get_graph(share, start, end, source=form.cleaned_data.get("source") or "local")
        except (MarketDataError, KeyError, ValueError):
            graph = ''
            error = 'Внешние исторические данные временно недоступны.'
        return render(request, 'dashboard/detail.html', {
            'share': share, 'plot_div': graph, 'history_form': form,
            'history': history, 'absolute_change': absolute, 'percent_change': percent,
            'market_error': error,
        })


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    template_name = 'dashboard/create.html'
    form_class = ShareModelForm
    success_url = reverse_lazy('dashboard:index')


class ShareUpdateView(IsUserAuthenticatedMixin, UpdateView):
    model = Share
    template_name = 'dashboard/create.html'
    form_class = ShareModelForm
    success_url = reverse_lazy('dashboard:index')


class ShareDeleteView(IsUserAuthenticatedMixin, DeleteView):
    model = Share
    template_name = 'dashboard/delete.html'
    success_url = reverse_lazy('dashboard:index')

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            form.add_error(None, 'Акция используется в виртуальном портфеле и не может быть удалена.')
            return self.form_invalid(form)
