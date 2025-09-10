from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.utils.translation import gettext as _

from .models import Company, KYCDocument
from .forms import KYCDocumentForm
from .utils import ONBOARDING_STEPS


class KYCDocumentCreateView(LoginRequiredMixin, CreateView):
    model = KYCDocument
    form_class = KYCDocumentForm
    template_name = 'customers/onboarding/kyc_document_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'company': self.company,
            'page_title': 'Add Document',
            'all_steps': ONBOARDING_STEPS,
            'current_step_key': 'add_documents',
        })
        return ctx

    def form_valid(self, form):
        form.instance.company = self.company
        try:
            if self.request.user.is_authenticated and hasattr(form.instance, 'uploaded_by'):
                if form.instance.uploaded_by_id is None:
                    form.instance.uploaded_by = self.request.user
        except Exception:
            pass
        messages.success(self.request, _('Documento adicionado com sucesso.'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.company.pk, 'step_slug': 'add_documents'})


class KYCDocumentUpdateView(LoginRequiredMixin, UpdateView):
    model = KYCDocument
    form_class = KYCDocumentForm
    template_name = 'customers/onboarding/kyc_document_form.html'
    pk_url_kwarg = 'doc_pk'

    def get_queryset(self):
        return KYCDocument.objects.filter(company_id=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = get_object_or_404(Company, pk=self.kwargs['pk'])
        ctx.update({
            'company': company,
            'page_title': 'Edit Document',
            'all_steps': ONBOARDING_STEPS,
            'current_step_key': 'add_documents',
        })
        return ctx

    def form_valid(self, form):
        try:
            if self.request.user.is_authenticated and hasattr(form.instance, 'uploaded_by'):
                if form.instance.uploaded_by_id is None:
                    form.instance.uploaded_by = self.request.user
        except Exception:
            pass
        messages.success(self.request, _('Documento atualizado com sucesso.'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.kwargs['pk'], 'step_slug': 'add_documents'})


class KYCDocumentDeleteView(LoginRequiredMixin, DeleteView):
    model = KYCDocument
    template_name = 'customers/onboarding/kyc_document_confirm_delete.html'
    pk_url_kwarg = 'doc_pk'

    def get_queryset(self):
        return KYCDocument.objects.filter(company_id=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = get_object_or_404(Company, pk=self.kwargs['pk'])
        ctx.update({
            'company': company,
            'page_title': 'Delete Document',
            'all_steps': ONBOARDING_STEPS,
            'current_step_key': 'add_documents',
        })
        return ctx

    def get_success_url(self):
        messages.success(self.request, _('Documento excluído com sucesso.'))
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.kwargs['pk'], 'step_slug': 'add_documents'})

