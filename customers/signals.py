from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.urls import reverse

from .models import Company, OwnershipManagementInfo, StatusControl, Notification


def _ensure_status_control(company):
    sc, _ = StatusControl.objects.get_or_create(company=company)
    return sc


def _notify_compliance(company):
    try:
        group = Group.objects.get(name='Compliance')
    except Group.DoesNotExist:
        return
    url = reverse('customers:company_detail', kwargs={'pk': company.pk})
    msg = f'Cliente pronto para avaliação de Compliance: {company.full_company_name}'
    for u in group.user_set.all():
        Notification.objects.create(recipient=u, message=msg, url=url)


def _notify_finance(company):
    try:
        group = Group.objects.get(name='Financeiro')
    except Group.DoesNotExist:
        return
    url = reverse('customers:company_detail', kwargs={'pk': company.pk})
    msg = f'Cliente pronto para avaliação do Financeiro: {company.full_company_name}'
    for u in group.user_set.all():
        Notification.objects.create(recipient=u, message=msg, url=url)


def _notify_user_missing(company, missing_list):
    user = company.created_by
    if not user:
        return
    # Evitar excesso de notificações idênticas: notificar se não houver uma não lida igual
    msg = f"Complete os requisitos mínimos para avançar: {', '.join(missing_list)}"
    exists_unread = Notification.objects.filter(recipient=user, message=msg, is_read=False).exists()
    if not exists_unread:
        url = reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': 'general_information'})
        Notification.objects.create(recipient=user, message=msg, url=url)


def _update_min_requirements_state(company):
    sc = _ensure_status_control(company)
    met = company.min_requirements_met()

    # Detecta transição para ligado/desligado
    previously = sc.min_requirements_met
    sc.min_requirements_met = met

    if not met:
        missing = company.missing_min_requirements()
        sc.is_pending = True
        sc.pending_owner = 'USER'
        sc.pending_details = f"Requisitos mínimos pendentes: {', '.join(missing)}" if missing else 'Requisitos mínimos pendentes.'
        sc.save(update_fields=['min_requirements_met', 'is_pending', 'pending_owner', 'pending_details', 'updated_at'])
        _notify_user_missing(company, missing)
    else:
        # Requisitos mínimos atendidos: libera Compliance e Financeiro em paralelo
        sc.is_pending = True
        sc.pending_owner = 'NONE'
        sc.pending_details = 'Aguardando avaliação de Compliance e Financeiro.'
        sc.save(update_fields=['min_requirements_met', 'is_pending', 'pending_owner', 'pending_details', 'updated_at'])
        if not previously:
            _notify_compliance(company)
            _notify_finance(company)


@receiver(post_save, sender=Company)
def on_company_saved(sender, instance: Company, created, **kwargs):
    _update_min_requirements_state(instance)


@receiver(post_save, sender=OwnershipManagementInfo)
def on_ownership_saved(sender, instance: OwnershipManagementInfo, created, **kwargs):
    _update_min_requirements_state(instance.company)
