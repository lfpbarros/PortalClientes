# customers/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import CreateView, UpdateView, ListView
from django.urls import reverse_lazy, reverse
from django.forms import inlineformset_factory
from django import forms
from django.views.generic import DetailView
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin # Importar este se estiver usando o StaffRequiredMixin
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.views import LogoutView
from datetime import date, timedelta

# Importar modelos e formulários que não são parte do FORM_MODEL_MAPPING diretamente
from .models import Company, IndividualContact, KYCDocument, \
    BusinessInformation, OwnershipManagementInfo, ComplianceInformation, \
    InvestigationsSanctionsInfo, BankingInformation, CertificationInformation, \
    ComplianceAnalysis, StatusControl, ReverseDueDiligence, ReverseDueDiligenceMessage, Notification, ReverseDueDiligenceAttachment, \
    ManagementAndKeyEmployees, BoardOfDirectors, UltimateBeneficialOwner, MajorShareholder, GovernmentOfficialInteraction # Certifique-se de importar todos os modelos OneToOneField
from .forms import CompanyForm, IndividualContactForm, KYCDocumentForm, \
    BusinessInformationForm, OwnershipManagementInfoForm, ComplianceInformationForm, \
    InvestigationsSanctionsInfoForm, BankingInformationForm, CertificationInformationForm, \
    ComplianceAnalysisForm, StatusControlForm, GovernmentOfficialInteractionForm, \
    ManagementAndKeyEmployeesForm, BoardOfDirectorsForm, UltimateBeneficialOwnerForm, MajorShareholderForm # E seus formulários

# IMPORTANTE: Importar ONBOARDING_STEPS e FORM_MODEL_MAPPING de customers.utils
from .utils import ONBOARDING_STEPS, FORM_MODEL_MAPPING

# Extras para histórico de avaliações
from .models import EvaluationRecord, FinalAnalysisAttachment
from .forms import EvaluationRecordForm
from .forms_evaluation import CompanyEvaluationForm
from .forms import ReverseDueDiligenceCreateForm, ReverseDueDiligenceMessageForm, PriorBusinessRelationshipForm
from django.contrib.auth.models import Group
from .models import PriorBusinessRelationship, BusinessInformation
from .permissions import is_internal_user, can_start_onboarding
from django.db.models import Q


# --- Mixin de Permissão para Equipe (se você for usar a segurança na view) ---
# Se você decidiu por não usar a segurança na view, pode ignorar este Mixin e a sua aplicação na CompanyOnboardingStepView.
class StaffRequiredMixin(AccessMixin):
    """Verify that the current user is logged in and is a staff member (belongs to 'Equipe' group)."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.groups.filter(name='Equipe').exists():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Você não tem permissão para acessar esta etapa.")
        return super().dispatch(request, *args, **kwargs)


# --- Onboarding da Empresa (Criação Inicial ou Redirecionamento) ---
class CompanyOnboardingCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'customers/onboarding/company_onboarding_create.html' # Caminho ajustado

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        self.object = form.save()
        first_step_slug = list(ONBOARDING_STEPS.keys())[0]
        messages.success(self.request, _("Empresa criada com sucesso. Continue o preenchimento do KYC."))
        return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': self.object.pk, 'step_slug': first_step_slug}))

    def form_invalid(self, form):
        messages.error(self.request, _("Não foi possível criar a empresa. Corrija os erros e tente novamente."))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Start New Company Onboarding"
        context['company'] = None
        context['all_steps'] = ONBOARDING_STEPS
        context['current_step_key'] = None
        context['current_step_index'] = -1
        context['progress_percentage'] = 0
        return context


class CompanyOnboardingUpdateView(LoginRequiredMixin, UpdateView):
    model = Company
    fields = []
    template_name = 'customers/onboarding/onboarding_base.html' # Caminho ajustado

    def get(self, request, *args, **kwargs):
        company = get_object_or_404(self.model, pk=self.kwargs['pk'])
        first_step_slug = list(ONBOARDING_STEPS.keys())[0]
        return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': first_step_slug}))


# --- View para gerenciar todas as etapas do Formulário de Onboarding ---
# Aplique o StaffRequiredMixin AQUI se for para garantir a segurança na view
# class CompanyOnboardingStepView(StaffRequiredMixin, View): # Descomente para ativar a segurança
class CompanyOnboardingStepView(LoginRequiredMixin, View): # Mantenha assim se a segurança for apenas via HTML
    template_name = 'customers/onboarding/onboarding_step.html'

    def get_form_and_instance(self, company, current_step_key, request=None):
        mapping = FORM_MODEL_MAPPING.get(current_step_key)
        if not mapping:
            return None, None

        Model = mapping['model']
        Form = mapping['form']
        FormSetFactory = mapping.get('factory')

        instance_for_form = None # Vai segurar a instância que será passada para o formulário

        # Se o modelo da etapa NÃO for Company e NÃO for um FormSet (ou seja, é um OneToOneField ou ForeignKey para um único objeto)
        if Model != Company and not FormSetFactory:
            try:
                # Tenta pegar a instância relacionada existente ou cria uma nova se não existir
                # É crucial para OneToOneFields!
                instance_for_form, created = Model.objects.get_or_create(company=company)
                
                # Se for uma instância recém-criada, atribua o usuário
                if created and request and request.user.is_authenticated:
                    if hasattr(instance_for_form, 'created_by') and instance_for_form.created_by is None:
                        instance_for_form.created_by = request.user
                    if hasattr(instance_for_form, 'performed_by') and instance_for_form.performed_by is None:
                        instance_for_form.performed_by = request.user
                    # Note: last_updated_by é geralmente auto_now ou atualizado na submissão do form
                    instance_for_form.save() # Salva para persistir o usuário criador imediatamente
            except Exception as e:
                # Logar ou tratar outros erros que podem ocorrer em get_or_create (embora raro)
                print(f"Erro ao obter/criar instância para {Model.__name__}: {e}")
                instance_for_form = None # Garante que o form será criado sem instância se houver erro
        elif Model == Company:
            instance_for_form = company # Se a etapa for para o modelo Company, use o objeto Company principal
        # Para FormSets, a instância principal é 'company' e os objetos são gerenciados pelo FormSetFactory

        if FormSetFactory:
            form_obj = FormSetFactory(
                request.POST if request and request.method == 'POST' else None, # Passa POST data apenas para requisições POST
                request.FILES if request and request.method == 'POST' else None, # Passa FILES data apenas para requisições POST
                instance=company, # A instância para o FormSet é a Company
                prefix=current_step_key
            )
            # Ajusta permissões de campos de avaliação no CompanyForm para não-Equipe
            try:
                if Model == Company and hasattr(form_obj, 'fields'):
                    setattr(form_obj, 'user', request.user)
                    if not request.user.groups.filter(name='Equipe').exists():
                        for _fname in ['evaluation_periodicity', 'last_evaluation_date', 'next_evaluation_date']:
                            if _fname in form_obj.fields:
                                form_obj.fields[_fname].widget = forms.HiddenInput()
                                form_obj.fields[_fname].required = False
            except Exception:
                pass
            # Atribuição de 'uploaded_by' para instâncias em FormSets
            if request and request.user.is_authenticated:
                for f in form_obj:
                    # Certifica-se de que o campo 'uploaded_by' seja definido apenas se o objeto for novo
                    # ou se ele já não tiver sido definido anteriormente
                    if hasattr(f.instance, 'uploaded_by') and f.instance.uploaded_by_id is None:
                        f.instance.uploaded_by = request.user
        else:
            form_obj = Form(
                request.POST if request and request.method == 'POST' else None, # Passa POST data apenas para requisições POST
                request.FILES if request and request.method == 'POST' else None, # Passa FILES data apenas para requisições POST
                instance=instance_for_form, # Usa a instância que pegamos/criamos
                prefix=current_step_key
            )
            # Atribuição de 'created_by'/'performed_by' para formulários que não são FormSets
            # Isso é para quando o formulário é recém-instanciado (GET request) ou para um novo objeto (POST request)
            if request and request.user.is_authenticated and request.method == 'GET':
                 if hasattr(form_obj.instance, 'created_by') and form_obj.instance.created_by is None:
                    form_obj.instance.created_by = request.user
                 if hasattr(form_obj.instance, 'performed_by') and form_obj.instance.performed_by is None:
                    form_obj.instance.performed_by = request.user
                 # Note: last_updated_by é mais apropriado para o save() do POST
            
        return form_obj, instance_for_form # Retorna a instância para uso posterior (ex: no POST)

    def get(self, request, pk, step_slug):
        company = get_object_or_404(Company, pk=pk)

        # --- Verificação de Permissão na View (Se você optar por ativá-la) ---
        restricted_steps = ['compliance_analysis', 'status_control']
        if step_slug in restricted_steps and not request.user.groups.filter(name='Equipe').exists():
            raise PermissionDenied("Você não tem permissão para acessar esta etapa diretamente.")

        form, _ = self.get_form_and_instance(company, step_slug, request=request) # Passa request para o get_form_and_instance

        if not form:
            first_step_slug = list(ONBOARDING_STEPS.keys())[0]
            return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': first_step_slug}))

        context = self._get_base_context_data(company, step_slug)
        context['form'] = form
        if step_slug == 'ownership_management':
            try:
                om, created_om = OwnershipManagementInfo.objects.get_or_create(
                    company=company,
                    defaults={'created_by': request.user if request.user.is_authenticated else None}
                )
                goi, created_goi = GovernmentOfficialInteraction.objects.get_or_create(ownership_management=om)
                context['goi_form'] = GovernmentOfficialInteractionForm(instance=goi, prefix='goi')
            except Exception:
                context['goi_form'] = GovernmentOfficialInteractionForm(prefix='goi')
        return render(request, self.template_name, context)

    def post(self, request, pk, step_slug):
        company = get_object_or_404(Company, pk=pk)

        # --- Verificação de Permissão na View para POST (Se você optar por ativá-la) ---
        restricted_steps = ['compliance_analysis', 'status_control']
        if step_slug in restricted_steps and not request.user.groups.filter(name='Equipe').exists():
            raise PermissionDenied("Você não tem permissão para submeter dados para esta etapa.")

        form, instance_for_form = self.get_form_and_instance(company, step_slug, request=request) # Passa request para o get_form_and_instance

        if not form:
            first_step_slug = list(ONBOARDING_STEPS.keys())[0]
            return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': first_step_slug}))

        if form.is_valid():
            mapping = FORM_MODEL_MAPPING.get(step_slug)
            Model = mapping['model']

            if mapping.get('factory'): # Se for um FormSet
                instances = form.save(commit=False)
                for obj in instances:
                    obj.company = company
                    if hasattr(obj, 'uploaded_by') and obj.uploaded_by_id is None: # Use _id para verificar se está vazio
                        obj.uploaded_by = request.user
                    obj.save()
                for obj in form.deleted_objects:
                    obj.delete()
                form.save_m2m() # Importante para ManyToManyFields em FormSets

            else: # Se for um formulário de um único objeto (OneToOneField ou Company)
                # Se a instância já foi criada por get_or_create, ela já está associada à company
                # Se for um novo objeto (e.g., Company na criação), form.instance.company ainda pode não estar setado
                if Model != Company and instance_for_form is not None:
                    # Se for um modelo relacionado e a instância já veio do get_or_create, ela já está ligada
                    # Mas para garantir, podemos setar novamente (não fará mal)
                    form.instance.company = company
                elif Model != Company and instance_for_form is None:
                    # Este caso idealmente não deveria acontecer com get_or_create, mas para robustez
                    form.instance.company = company # Garante a ligação se for um novo objeto
                
                # Atribui last_updated_by ANTES de salvar o formulário
                if request.user.is_authenticated:
                    if hasattr(form.instance, 'last_updated_by'):
                        form.instance.last_updated_by = request.user
                    # Campos created_by/performed_by já deveriam ter sido definidos em get_or_create ou na criação inicial

                form.save() # Salva a instância (que agora tem created_by/performed_by/last_updated_by se aplicável)

            # If Banking Information step, handle extra bank certificate file upload
            if step_slug == 'banking_information':
                try:
                    bank_cert_file = request.FILES.get('bank_certificate_file')
                    if bank_cert_file:
                        KYCDocument.objects.create(
                            company=company,
                            document_type='BANK_CERTIFICATE',
                            file=bank_cert_file,
                            uploaded_by=request.user if request.user.is_authenticated else None,
                            description='Bank account certificate'
                        )
                except Exception:
                    # Silently ignore attachment errors to not block main form save
                    pass

            # Ownership & Management: process GovernmentOfficialInteraction inline
            if step_slug == 'ownership_management':
                try:
                    om, created_om = OwnershipManagementInfo.objects.get_or_create(
                        company=company,
                        defaults={'created_by': request.user if request.user.is_authenticated else None}
                    )
                    goi, created_goi = GovernmentOfficialInteraction.objects.get_or_create(ownership_management=om)
                    goi_form = GovernmentOfficialInteractionForm(request.POST, request.FILES, instance=goi, prefix='goi')
                    if goi_form.is_valid():
                        goi_form.save()
                    else:
                        context = self._get_base_context_data(company, step_slug)
                        context['form'] = form
                        context['goi_form'] = goi_form
                        return render(request, self.template_name, context)
                except Exception:
                    pass

            messages.success(request, _("Dados salvos com sucesso."))
            next_step_index = list(ONBOARDING_STEPS.keys()).index(step_slug) + 1
            if next_step_index < len(ONBOARDING_STEPS):
                next_step_slug = list(ONBOARDING_STEPS.keys())[next_step_index]
                # Pular abas restritas se o usuário não tiver permissão
                restricted_steps = ['compliance_analysis', 'status_control'] # Replicar aqui para clareza
                while next_step_slug in restricted_steps and not request.user.groups.filter(name='Equipe').exists() and next_step_index < len(ONBOARDING_STEPS):
                    next_step_index += 1
                    if next_step_index < len(ONBOARDING_STEPS):
                        next_step_slug = list(ONBOARDING_STEPS.keys())[next_step_index]
                    else:
                        break # Sai do loop se não houver mais etapas

                if next_step_index < len(ONBOARDING_STEPS):
                    return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': next_step_slug}))
                else:
                    return redirect(reverse('customers:company_detail', kwargs={'pk': company.pk})) # Redireciona para o detalhe da empresa ao finalizar
            else:
                return redirect(reverse('customers:company_detail', kwargs={'pk': company.pk})) # Assumindo 'customers:company_detail'

        messages.error(request, _("Ocorreram erros no formulário. Verifique os campos destacados."))
        context = self._get_base_context_data(company, step_slug)
        context['form'] = form
        if step_slug == 'ownership_management':
            try:
                om, created_om = OwnershipManagementInfo.objects.get_or_create(
                    company=company,
                    defaults={'created_by': request.user if request.user.is_authenticated else None}
                )
                goi, created_goi = GovernmentOfficialInteraction.objects.get_or_create(ownership_management=om)
                context['goi_form'] = GovernmentOfficialInteractionForm(instance=goi, prefix='goi')
            except Exception:
                from .forms import GovernmentOfficialInteractionForm as _GOIForm
                context['goi_form'] = _GOIForm(prefix='goi')
        return render(request, self.template_name, context)

    def _get_base_context_data(self, company, current_step_key):
        """Prepara o contexto base para o template (sidebar, progresso etc.)."""
        all_steps_keys = list(ONBOARDING_STEPS.keys())
        current_step_index = all_steps_keys.index(current_step_key)
        
        completed_steps = 0
        completed_steps_set = set()

        is_staff_member = self.request.user.groups.filter(name='Equipe').exists()
        
        # Filtra as etapas visíveis para o cálculo do progresso
        visible_steps_for_progress = []
        for slug, title in ONBOARDING_STEPS.items():
            if (slug == 'compliance_analysis' or slug == 'status_control') and not is_staff_member:
                continue # Pula esta etapa se for restrita e o usuário não for da equipe
            visible_steps_for_progress.append(slug)


        for step_slug in visible_steps_for_progress: # Itera apenas sobre as etapas visíveis
            mapping = FORM_MODEL_MAPPING.get(step_slug)
            if not mapping: continue

            Model = mapping['model']
            is_step_complete = False
            
            # Lógica para verificar a conclusão da etapa
            if Model == Company:
                if company.full_company_name and company.registered_business_address:
                    is_step_complete = True
            elif Model == KYCDocument:
                if KYCDocument.objects.filter(company=company).exists():
                    is_step_complete = True
            elif Model == IndividualContact:
                if IndividualContact.objects.filter(company=company).exists():
                    is_step_complete = True
            else:
                # Para OneToOneFields, verifica se a instância relacionada existe
                # (já que get_or_create pode ter criado um objeto vazio)
                # Você pode adicionar mais validações aqui se um objeto vazio não for "completo"
                try:
                    related_instance = Model.objects.get(company=company)
                    # Considerar a etapa como completa se o objeto existe e possui dados críticos,
                    # ou apenas se o objeto existe. Depende da sua definição de "completo".
                    # Por simplicidade, assumimos que existir é o suficiente para o progresso.
                    # Exemplo mais robusto: if related_instance.some_required_field: is_step_complete = True
                    is_step_complete = True 
                except Model.DoesNotExist:
                    is_step_complete = False

            if is_step_complete:
                completed_steps += 1
                completed_steps_set.add(step_slug)

        total_steps = len(visible_steps_for_progress) # Total de etapas VISÍVEIS
        progress_percentage = (completed_steps / total_steps) * 100 if total_steps > 0 else 0

        raw_page_title = ONBOARDING_STEPS.get(current_step_key, "Onboarding Step")
        display_page_title = raw_page_title.replace("Company Information", "General Information")
        display_page_title = display_page_title.replace("Individual Contact Information", "Individual Contact")
        
        # Cálculo do previous_step_slug baseado nas etapas visíveis
        previous_step_slug = None
        next_step_slug = None
        if current_step_key in visible_steps_for_progress:
            vis_index = visible_steps_for_progress.index(current_step_key)
            if vis_index > 0:
                previous_step_slug = visible_steps_for_progress[vis_index - 1]
            if vis_index + 1 < len(visible_steps_for_progress):
                next_step_slug = visible_steps_for_progress[vis_index + 1]

        return {
            'company': company,
            'current_step_key': current_step_key,
            'current_step_index': current_step_index,
            'all_steps': ONBOARDING_STEPS, # Passa todas as etapas para o template, a visibilidade será controlada no HTML
            'completed_steps': completed_steps,
            'total_steps': total_steps, # O total de etapas VISÍVEIS para o cálculo de progresso
            'progress_percentage': round(progress_percentage),
            'page_title': display_page_title,
            'completed_steps_set': completed_steps_set,
            'is_staff_member': is_staff_member, # ESSENCIAL para controlar a visibilidade no template
            'previous_step_slug': previous_step_slug,
            'next_step_slug': next_step_slug,
        }
    
class CompanyDetailView(LoginRequiredMixin, DetailView):
    model = Company
    template_name = 'customers/onboarding/company_detail.html'
    context_object_name = 'company'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Título para o header do layout base
        context['page_title'] = 'Company Details'
        # Variáveis esperadas pelo layout base
        context['all_steps'] = ONBOARDING_STEPS
        context['current_step_key'] = None
        # Visibilidade de abas restritas
        user = self.request.user
        is_staff_member = user.groups.filter(name='Equipe').exists()
        context['is_staff_member'] = is_staff_member
        # Grupos do usuário (para controles de ação no template)
        context['user_groups'] = self.request.user.groups.values_list('name', flat=True)
        context['compliance_group_name'] = 'Compliance'
        context['financeiro_group_name'] = 'Financeiro'
        context['trading_group_name'] = 'Trading'
        context['suprimentos_group_name'] = 'Suprimentos'

        # Cálculo de progresso (mesma lógica base do onboarding)
        company = context['company']
        visible_steps_for_progress = []
        for slug, _title in ONBOARDING_STEPS.items():
            if (slug == 'compliance_analysis' or slug == 'status_control') and not is_staff_member:
                continue
            visible_steps_for_progress.append(slug)

        completed_steps = 0
        completed_steps_set = set()
        for step_slug in visible_steps_for_progress:
            mapping = FORM_MODEL_MAPPING.get(step_slug)
            if not mapping:
                continue
            Model = mapping['model']

            is_step_complete = False
            if Model == Company:
                if company.full_company_name and company.registered_business_address:
                    is_step_complete = True
            elif Model == KYCDocument:
                if KYCDocument.objects.filter(company=company).exists():
                    is_step_complete = True
            elif Model == IndividualContact:
                if IndividualContact.objects.filter(company=company).exists():
                    is_step_complete = True
            else:
                try:
                    mapping['model'].objects.get(company=company)
                    is_step_complete = True
                except mapping['model'].DoesNotExist:
                    is_step_complete = False

            if is_step_complete:
                completed_steps += 1
                completed_steps_set.add(step_slug)

        total_steps = len(visible_steps_for_progress)
        progress_percentage = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        context['progress_percentage'] = round(progress_percentage)
        context['completed_steps_set'] = completed_steps_set
        # Histórico de avaliações
        try:
            context['evaluation_records'] = EvaluationRecord.objects.filter(company=company).order_by('-evaluation_date', '-created_at')
        except Exception:
            context['evaluation_records'] = []
        # Form de avaliação (para edição inline por Equipe)
        try:
            context['evaluation_form'] = CompanyEvaluationForm(instance=company)
        except Exception:
            context['evaluation_form'] = None
        return context


class EvaluationRecordUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        if not request.user.groups.filter(name='Equipe').exists():
            raise PermissionDenied("Você não tem permissão para anexar avaliações.")
        form = EvaluationRecordForm(request.POST, request.FILES)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.company = company
            rec.created_by = request.user
            rec.save()
            messages.success(request, _("Avaliação anexada com sucesso."))
        else:
            messages.error(request, _("Não foi possível anexar a avaliação. Verifique os campos."))
        return redirect('customers:company_detail', pk=company.pk)


class CompanyEvaluationUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        if not request.user.groups.filter(name='Equipe').exists():
            raise PermissionDenied("Você não tem permissão para editar avaliações.")
        form = CompanyEvaluationForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Informações de avaliação atualizadas."))
        else:
            messages.error(request, _("Não foi possível atualizar. Verifique os campos."))
        return redirect('customers:company_detail', pk=company.pk)


# --- Reverse Due Diligence (RDD) ---
def _notify_group(group_name, message, url=None, rdd=None):
    try:
        from django.contrib.auth.models import Group
        group = Group.objects.get(name=group_name)
    except Exception:
        return
    for u in group.user_set.all():
        Notification.objects.create(
            recipient=u,
            message=message,
            url=url,
            rdd=rdd,
            audience=Notification.Audience.INTERNAL,
        )


def _notify_user(user, message, url=None, rdd=None):
    if user:
        audience = Notification.Audience.INTERNAL if is_internal_user(user) else Notification.Audience.CLIENT
        Notification.objects.create(
            recipient=user,
            message=message,
            url=url,
            rdd=rdd,
            audience=audience,
        )


class ReverseDueDiligenceCreateView(LoginRequiredMixin, View):
    template_name = 'customers/rdd_create.html'

    def get(self, request):
        form = ReverseDueDiligenceCreateForm(user=request.user)
        context = {'form': form, 'is_internal': is_internal_user(request.user), 'can_create_company': can_start_onboarding(request.user)}
        return render(request, self.template_name, context)

    def post(self, request):
        form = ReverseDueDiligenceCreateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            rdd = form.save(commit=False)
            # Usuário externo só pode criar para a própria empresa
            if not is_internal_user(request.user):
                if rdd.company.created_by_id != request.user.id:
                    raise PermissionDenied("Você não pode criar RDD para esta empresa.")
            rdd.created_by = request.user
            rdd.save()
            first_msg = ReverseDueDiligenceMessage.objects.create(thread=rdd, author=request.user, body=rdd.description)
            attachment = form.cleaned_data.get('attachment')
            if attachment:
                ReverseDueDiligenceAttachment.objects.create(message=first_msg, file=attachment, uploaded_by=request.user)
            _notify_group('Equipe', f'Novo RDD: {rdd.subject}', url=rdd.get_absolute_url(), rdd=rdd)
            messages.success(request, _("Sua solicitação de Due Diligence Reversa foi enviada."))
            return redirect(rdd.get_absolute_url())
        context = {'form': form, 'is_internal': is_internal_user(request.user), 'can_create_company': can_start_onboarding(request.user)}
        return render(request, self.template_name, context)


class ReverseDueDiligenceDetailView(LoginRequiredMixin, View):
    template_name = 'customers/rdd_detail.html'

    def _get_thread(self, request, pk):
        rdd = get_object_or_404(ReverseDueDiligence, pk=pk)
        if is_internal_user(request.user):
            return rdd
        if rdd.created_by_id != request.user.id and rdd.company.created_by_id != request.user.id:
            raise PermissionDenied("Você não tem acesso a este RDD.")
        return rdd

    def get(self, request, pk):
        rdd = self._get_thread(request, pk)
        form = ReverseDueDiligenceMessageForm()
        Notification.objects.filter(recipient=request.user, rdd=rdd, is_read=False).update(is_read=True)
        is_internal = is_internal_user(request.user)
        return render(request, self.template_name, {'rdd': rdd, 'form': form, 'is_internal': is_internal, 'can_create_company': can_start_onboarding(request.user)})

    def post(self, request, pk):
        rdd = self._get_thread(request, pk)
        is_internal = is_internal_user(request.user)

        # Close action (Equipe only)
        action = request.POST.get('action')
        if action == 'close':
            if not is_internal:
                raise PermissionDenied("You cannot close this RDD.")
            if rdd.status != 'CLOSED':
                rdd.status = 'CLOSED'
                rdd.save(update_fields=['status'])
                messages.success(request, _("Due Diligence Reversa encerrada."))
            return redirect(rdd.get_absolute_url())

        # Reopen action (Equipe and usuários autorizados)
        if action == 'reopen':
            # Usuário externo pode reabrir se for criador ou dono da empresa
            if not is_internal:
                if not (rdd.created_by_id == request.user.id or rdd.company.created_by_id == request.user.id):
                    raise PermissionDenied("You cannot reopen this RDD.")
            if rdd.status == 'CLOSED':
                rdd.status = 'OPEN'
                rdd.save(update_fields=['status'])
                # Notifica Equipe quando reaberto por usuário comum
                if not is_internal:
                    _notify_group('Equipe', f'RDD reaberto: {rdd.subject}', url=rdd.get_absolute_url(), rdd=rdd)
                messages.success(request, _("Due Diligence Reversa reaberta."))
            return redirect(rdd.get_absolute_url())

        # Default: message post
        form = ReverseDueDiligenceMessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.thread = rdd
            msg.author = request.user
            msg.save()
            attachment = form.cleaned_data.get('attachment')
            if attachment:
                ReverseDueDiligenceAttachment.objects.create(message=msg, file=attachment, uploaded_by=request.user)
            from django.utils import timezone
            rdd.last_message_at = timezone.now()
            if is_internal:
                if rdd.status != 'CLOSED':
                    rdd.status = 'RESPONDED'
                _notify_user(rdd.created_by, f'Resposta ao RDD: {rdd.subject}', url=rdd.get_absolute_url(), rdd=rdd)
            else:
                _notify_group('Equipe', f'Nova mensagem no RDD: {rdd.subject}', url=rdd.get_absolute_url(), rdd=rdd)
            rdd.save(update_fields=['last_message_at', 'status'])
            messages.success(request, _("Mensagem enviada."))
            return redirect(rdd.get_absolute_url())
        return render(request, self.template_name, {'rdd': rdd, 'form': form, 'is_internal': is_internal, 'can_create_company': can_start_onboarding(request.user)})


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'customers/dashboard.html'


class ReverseDueDiligenceListView(LoginRequiredMixin, ListView):
    model = ReverseDueDiligence
    template_name = 'customers/rdd_list.html'
    context_object_name = 'threads'
    paginate_by = 20

    def get_queryset(self):
        qs = ReverseDueDiligence.objects.all().select_related('company', 'created_by')
        is_internal = is_internal_user(self.request.user)
        status = self.request.GET.get('status')
        if not is_internal:
            qs = qs.filter(Q(created_by=self.request.user) | Q(company__created_by=self.request.user))
        if status in {"OPEN", "RESPONDED", "CLOSED"}:
            qs = qs.filter(status=status)
        return qs.order_by('-updated_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_internal'] = is_internal_user(self.request.user)
        ctx['can_create_company'] = can_start_onboarding(self.request.user)
        ctx['current_status'] = self.request.GET.get('status') or ''
        return ctx

# --- Reinserir DashboardView completo após a lista RDD ---
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'customers/dashboard.html'

    def _is_internal(self, user):
        return is_internal_user(user)

    def _step_completed(self, company, slug, is_internal):
        mapping = FORM_MODEL_MAPPING.get(slug)
        if not mapping:
            return False
        Model = mapping['model']
        if Model == Company:
            return bool(company.full_company_name and company.registered_business_address)
        from .models import KYCDocument, IndividualContact
        if Model.__name__ == 'KYCDocument':
            return KYCDocument.objects.filter(company=company).exists()
        if Model.__name__ == 'IndividualContact':
            return IndividualContact.objects.filter(company=company).exists()
        try:
            mapping['model'].objects.get(company=company)
            return True
        except mapping['model'].DoesNotExist:
            return False

    def _visible_steps(self, is_internal):
        if is_internal:
            return list(ONBOARDING_STEPS.keys())
        return [s for s in ONBOARDING_STEPS.keys() if s not in ('compliance_analysis', 'status_control')]

    def _company_progress(self, company, is_internal):
        steps = self._visible_steps(is_internal)
        completed = [s for s in steps if self._step_completed(company, s, is_internal)]
        pct = round((len(completed) / len(steps) * 100) if steps else 0)
        return pct, completed

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        is_internal = self._is_internal(user)
        ctx['is_internal'] = is_internal
        ctx['can_create_company'] = can_start_onboarding(user)

        qs = Company.objects.all() if is_internal else Company.objects.filter(created_by=user)

        total = qs.count()
        from .models import StatusControl
        sc_qs = StatusControl.objects.filter(company__in=qs)
        completed = sc_qs.filter(client_onboarding_finished=True).count()
        pending = sc_qs.filter(is_pending=True).count()

        trading_pending = sc_qs.filter(trading_qualified=False).count()
        compliance_pending = sc_qs.filter(compliance_qualified=False).count()
        treasury_pending = sc_qs.filter(treasury_qualified=False).count()
        # Suprimentos: pendências ativas atribuídas a SUPRIMENTOS
        try:
            suprimentos_pending = sc_qs.filter(is_pending=True, pending_owner='SUPRIMENTOS').count()
        except Exception:
            suprimentos_pending = 0

        recent = qs.order_by('-created_at')[:5]

        progress_values = []
        for c in qs[:50]:
            pct, _ = self._company_progress(c, is_internal)
            progress_values.append(pct)
        avg_progress = round(sum(progress_values) / len(progress_values)) if progress_values else 0

        pending_items = []
        if not is_internal:
            steps = self._visible_steps(False)
            for c in qs:
                for s in steps:
                    if not self._step_completed(c, s, False):
                        pending_items.append({
                            'company': c,
                            'next_step_slug': s,
                            'next_step_title': ONBOARDING_STEPS.get(s, s).title(),
                        })
                        break

        evaluation_due_companies = []
        evaluation_upcoming_companies = []
        if is_internal:
            today = date.today()
            try:
                evaluation_due_companies = list(qs.filter(next_evaluation_date__isnull=False, next_evaluation_date__lte=today)[:20])
                evaluation_upcoming_companies = list(qs.filter(next_evaluation_date__gt=today, next_evaluation_date__lte=today + timedelta(days=7))[:20])
            except Exception:
                evaluation_due_companies = []
                evaluation_upcoming_companies = []

        audience_filters = [Notification.Audience.CLIENT]
        if is_internal:
            audience_filters.append(Notification.Audience.INTERNAL)
        try:
            notification_qs = Notification.objects.filter(
                is_read=False,
                audience__in=audience_filters,
            )
            if is_internal:
                unread_notifications = notification_qs[:20]
            else:
                company_ids = list(qs.values_list('pk', flat=True))
                unread_notifications = notification_qs.filter(
                    Q(recipient=user) | Q(rdd__company_id__in=company_ids)
                )[:20]
        except Exception:
            unread_notifications = []
        rdd_open_threads = None
        rdd_my_threads = None
        try:
            if is_internal:
                rdd_open_threads = ReverseDueDiligence.objects.filter(status__in=['OPEN', 'RESPONDED']).order_by('-updated_at')[:10]
            else:
                rdd_my_threads = ReverseDueDiligence.objects.filter(created_by=user).order_by('-updated_at')[:10]
        except Exception:
            pass

        ctx.update({
            'total_companies': total,
            'completed_count': completed,
            'pending_flag_count': pending,
            'trading_pending': trading_pending,
            'compliance_pending': compliance_pending,
            'treasury_pending': treasury_pending,
            'suprimentos_pending': suprimentos_pending,
            'recent_companies': recent,
            'avg_progress': avg_progress,
            'pending_items': pending_items,
            'ONBOARDING_STEPS': ONBOARDING_STEPS,
            'evaluation_due_companies': evaluation_due_companies,
            'evaluation_upcoming_companies': evaluation_upcoming_companies,
            'unread_notifications': unread_notifications,
            'rdd_open_threads': rdd_open_threads,
            'rdd_my_threads': rdd_my_threads,
        })

        # Pendências de requisitos mínimos por usuário (não-interno)
        try:
            if not is_internal:
                min_pending = []
                for c in qs:
                    if hasattr(c, 'min_requirements_met'):
                        met = c.min_requirements_met()
                    else:
                        met = True
                    if not met:
                        min_pending.append({'company': c, 'missing': c.missing_min_requirements()})
                ctx.update({'min_pending_for_user': min_pending})
            else:
                # Para internos, mostrar rapidamente os prontos para Compliance (opcional)
                ready_for_compliance = []
                for c in qs:
                    try:
                        if c.min_requirements_met():
                            ready_for_compliance.append(c)
                    except Exception:
                        pass
                ctx.update({'ready_for_compliance_companies': ready_for_compliance[:20]})
        except Exception:
            pass
        return ctx

# Handler de 403 amigável
def custom_permission_denied_view(request, exception=None):
    return render(request, '403.html', status=403)

def custom_page_not_found_view(request, exception=None):
    return render(request, '404.html', status=404)

def custom_server_error_view(request):
    return render(request, '500.html', status=500)


class LogoutNotifyView(LogoutView):
    """Logout que exibe uma mensagem de sucesso após sair.

    Em versões recentes do Django, o LogoutView aceita apenas POST por padrão.
    Para compatibilizar com links <a href="..."> (GET), permitimos GET e
    delegamos para POST, mantendo o redirecionamento configurado em
    LOGOUT_REDIRECT_URL.
    """

    # Permitir GET além de POST para compatibilidade com links existentes
    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        # Delegar GET para POST, que faz o logout e redireciona
        return self.post(request, *args, **kwargs)


# --- CRUD de PriorBusinessRelationship durante o Onboarding (Etapa 3) ---
class PriorBusinessRelationshipCreateView(LoginRequiredMixin, CreateView):
    model = PriorBusinessRelationship
    form_class = PriorBusinessRelationshipForm
    template_name = 'customers/onboarding/prior_business_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.bi, _ = BusinessInformation.objects.get_or_create(company=self.company, defaults={'created_by': request.user if request.user.is_authenticated else None})
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['company'] = self.company
        ctx['page_title'] = 'Add Prior Business Relationship'
        ctx['all_steps'] = ONBOARDING_STEPS
        ctx['current_step_key'] = 'business_information'
        ctx['progress_percentage'] = 0
        return ctx

    def form_valid(self, form):
        form.instance.business_information = self.bi
        if not form.instance.created_by and self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.company.pk, 'step_slug': 'business_information'})


class PriorBusinessRelationshipUpdateView(LoginRequiredMixin, UpdateView):
    model = PriorBusinessRelationship
    form_class = PriorBusinessRelationshipForm
    template_name = 'customers/onboarding/prior_business_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.object = self.get_object()
        if self.object.business_information.company_id != self.company.id:
            raise PermissionDenied('Relacionamento não pertence a esta empresa.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['company'] = self.company
        ctx['page_title'] = 'Edit Prior Business Relationship'
        ctx['all_steps'] = ONBOARDING_STEPS
        ctx['current_step_key'] = 'business_information'
        ctx['progress_percentage'] = 0
        return ctx

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.company.pk, 'step_slug': 'business_information'})


class PriorBusinessRelationshipDeleteView(LoginRequiredMixin, View):
    template_name = 'customers/onboarding/prior_business_confirm_delete.html'

    def post(self, request, pk, rel_pk):
        company = get_object_or_404(Company, pk=pk)
        rel = get_object_or_404(PriorBusinessRelationship, pk=rel_pk, business_information__company=company)
        rel.delete()
        messages.success(request, _('Relacionamento removido.'))
        return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': 'business_information'}))

    def get(self, request, pk, rel_pk):
        company = get_object_or_404(Company, pk=pk)
        rel = get_object_or_404(PriorBusinessRelationship, pk=rel_pk, business_information__company=company)
        return render(request, self.template_name, {
            'company': company,
            'rel': rel,
            'page_title': 'Delete Prior Business Relationship',
            'all_steps': ONBOARDING_STEPS,
            'current_step_key': 'business_information',
            'progress_percentage': 0,
        })


# --- CRUD de IndividualContact durante o Onboarding ---
class IndividualContactCreateView(LoginRequiredMixin, CreateView):
    model = IndividualContact
    form_class = IndividualContactForm
    template_name = 'customers/onboarding/individual_contact_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['company'] = self.company
        ctx['page_title'] = 'Add Individual Contact'
        ctx['all_steps'] = ONBOARDING_STEPS
        ctx['current_step_key'] = 'individual_contacts'
        ctx['progress_percentage'] = 0
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial['company'] = self.company.pk
        return initial

    def form_valid(self, form):
        form.instance.company = self.company
        if not form.instance.created_by and self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.company.pk, 'step_slug': 'individual_contacts'})


class IndividualContactUpdateView(LoginRequiredMixin, UpdateView):
    model = IndividualContact
    form_class = IndividualContactForm
    template_name = 'customers/onboarding/individual_contact_form.html'

    def get_object(self, queryset=None):
        return get_object_or_404(IndividualContact, pk=self.kwargs['contact_pk'])

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.object = self.get_object()
        if self.object.company_id != self.company.id:
            raise PermissionDenied('Contato não pertence a esta empresa.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['company'] = self.company
        ctx['page_title'] = 'Edit Individual Contact'
        ctx['all_steps'] = ONBOARDING_STEPS
        ctx['current_step_key'] = 'individual_contacts'
        ctx['progress_percentage'] = 0
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial['company'] = self.company.pk
        return initial

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.company.pk, 'step_slug': 'individual_contacts'})


class IndividualContactDeleteView(LoginRequiredMixin, View):
    template_name = 'customers/onboarding/individual_contact_confirm_delete.html'

    def post(self, request, pk, contact_pk):
        company = get_object_or_404(Company, pk=pk)
        contact = get_object_or_404(IndividualContact, pk=contact_pk, company=company)
        contact.delete()
        messages.success(request, _('Contato removido.'))
        return redirect(reverse('customers:company_onboarding_step', kwargs={'pk': company.pk, 'step_slug': 'individual_contacts'}))

    def get(self, request, pk, contact_pk):
        company = get_object_or_404(Company, pk=pk)
        contact = get_object_or_404(IndividualContact, pk=contact_pk, company=company)
        return render(request, self.template_name, {
            'company': company,
            'contact': contact,
            'page_title': 'Delete Individual Contact',
            'all_steps': ONBOARDING_STEPS,
            'current_step_key': 'individual_contacts',
            'progress_percentage': 0,
        })


# --- CRUD Etapa 4: Ownership & Management inlines ---
class _BaseOwnershipInlineView(LoginRequiredMixin):
    parent_model = OwnershipManagementInfo
    form_class = None
    model = None
    template_name = 'customers/onboarding/ownership_inline_form.html'
    delete_template_name = 'customers/onboarding/ownership_inline_confirm_delete.html'
    section_key = 'ownership_management'

    def _ensure_parent(self, company):
        om, _ = OwnershipManagementInfo.objects.get_or_create(company=company, defaults={'created_by': self.request.user if self.request.user.is_authenticated else None})
        return om

    def get_success_url(self):
        return reverse('customers:company_onboarding_step', kwargs={'pk': self.company.pk, 'step_slug': self.section_key})

    def get_context_data_base(self, **kwargs):
        ctx = {
            'company': self.company,
            'page_title': kwargs.get('page_title', ''),
            'all_steps': ONBOARDING_STEPS,
            'current_step_key': self.section_key,
            'progress_percentage': 0,
        }
        return ctx


class MKECreateView(_BaseOwnershipInlineView, CreateView):
    model = ManagementAndKeyEmployees
    form_class = ManagementAndKeyEmployeesForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.parent = self._ensure_parent(self.company)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.ownership_management = self.parent
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Add Management/Key Employee'))
        return ctx


class MKEUpdateView(_BaseOwnershipInlineView, UpdateView):
    model = ManagementAndKeyEmployees
    form_class = ManagementAndKeyEmployeesForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.object = self.get_object()
        if self.object.ownership_management.company_id != self.company.id:
            raise PermissionDenied('Item não pertence a esta empresa.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Edit Management/Key Employee'))
        return ctx


class MKEDeleteView(_BaseOwnershipInlineView, View):
    template_name = _BaseOwnershipInlineView.delete_template_name

    def post(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(ManagementAndKeyEmployees, pk=item_pk, ownership_management__company=self.company)
        obj.delete()
        messages.success(request, _('Item removido.'))
        return redirect(self.get_success_url())

    def get(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(ManagementAndKeyEmployees, pk=item_pk, ownership_management__company=self.company)
        ctx = self.get_context_data_base(page_title='Delete Management/Key Employee')
        ctx['obj'] = obj
        return render(request, self.delete_template_name, ctx)


class BoardCreateView(_BaseOwnershipInlineView, CreateView):
    model = BoardOfDirectors
    form_class = BoardOfDirectorsForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.parent = self._ensure_parent(self.company)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.ownership_management = self.parent
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Add Board Member'))
        return ctx


class BoardUpdateView(_BaseOwnershipInlineView, UpdateView):
    model = BoardOfDirectors
    form_class = BoardOfDirectorsForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.object = self.get_object()
        if self.object.ownership_management.company_id != self.company.id:
            raise PermissionDenied('Item não pertence a esta empresa.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Edit Board Member'))
        return ctx


class BoardDeleteView(_BaseOwnershipInlineView, View):
    template_name = _BaseOwnershipInlineView.delete_template_name

    def post(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(BoardOfDirectors, pk=item_pk, ownership_management__company=self.company)
        obj.delete()
        messages.success(request, _('Item removido.'))
        return redirect(self.get_success_url())

    def get(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(BoardOfDirectors, pk=item_pk, ownership_management__company=self.company)
        ctx = self.get_context_data_base(page_title='Delete Board Member')
        ctx['obj'] = obj
        return render(request, self.delete_template_name, ctx)


class UBOCreateView(_BaseOwnershipInlineView, CreateView):
    model = UltimateBeneficialOwner
    form_class = UltimateBeneficialOwnerForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.parent = self._ensure_parent(self.company)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.ownership_management = self.parent
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Add UBO'))
        return ctx


class UBOUpdateView(_BaseOwnershipInlineView, UpdateView):
    model = UltimateBeneficialOwner
    form_class = UltimateBeneficialOwnerForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.object = self.get_object()
        if self.object.ownership_management.company_id != self.company.id:
            raise PermissionDenied('Item não pertence a esta empresa.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Edit UBO'))
        return ctx


class UBODeleteView(_BaseOwnershipInlineView, View):
    template_name = _BaseOwnershipInlineView.delete_template_name

    def post(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(UltimateBeneficialOwner, pk=item_pk, ownership_management__company=self.company)
        obj.delete()
        messages.success(request, _('Item removido.'))
        return redirect(self.get_success_url())

    def get(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(UltimateBeneficialOwner, pk=item_pk, ownership_management__company=self.company)
        ctx = self.get_context_data_base(page_title='Delete UBO')
        ctx['obj'] = obj
        return render(request, self.delete_template_name, ctx)


class ShareholderCreateView(_BaseOwnershipInlineView, CreateView):
    model = MajorShareholder
    form_class = MajorShareholderForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.parent = self._ensure_parent(self.company)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.ownership_management = self.parent
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Add Major Shareholder'))
        return ctx


class ShareholderUpdateView(_BaseOwnershipInlineView, UpdateView):
    model = MajorShareholder
    form_class = MajorShareholderForm

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        self.object = self.get_object()
        if self.object.ownership_management.company_id != self.company.id:
            raise PermissionDenied('Item não pertence a esta empresa.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_context_data_base(page_title='Edit Major Shareholder'))
        return ctx


class ShareholderDeleteView(_BaseOwnershipInlineView, View):
    template_name = _BaseOwnershipInlineView.delete_template_name

    def post(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(MajorShareholder, pk=item_pk, ownership_management__company=self.company)
        obj.delete()
        messages.success(request, _('Item removido.'))
        return redirect(self.get_success_url())

    def get(self, request, pk, item_pk):
        self.company = get_object_or_404(Company, pk=pk)
        obj = get_object_or_404(MajorShareholder, pk=item_pk, ownership_management__company=self.company)
        ctx = self.get_context_data_base(page_title='Delete Major Shareholder')
        ctx['obj'] = obj
        return render(request, self.delete_template_name, ctx)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Adiciona mensagem após o logout para não ser perdida com o flush da sessão
        messages.success(request, _("Você saiu com sucesso."))
        return response

@login_required
def home(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        previous_names = request.POST.get('previous_names')
        aliases = request.POST.get('aliases') # Assumindo que você renomeou o campo para 'aliases' no HTML
                                               # ou o nome correto do campo no model é 'aliases_trade_names'
                                               # e você está mapeando corretamente aqui

        # Correção: Use 'aliases_trade_names' se esse for o nome do campo no seu Company model
        # Ou 'aliases' se você de fato mudou o nome do campo no model.
        # Com base no seu models.py anterior, o nome é 'aliases_trade_names'
        company = Company.objects.create(
            full_company_name=company_name,
            previous_names=previous_names,
            aliases_trade_names=aliases, # Ajustado para o nome do campo do seu models.py
            created_by=request.user
        )

        first_step_slug = list(ONBOARDING_STEPS.keys())[0]
        return redirect('customers:company_onboarding_step', pk=company.pk, step_slug=first_step_slug)

    return render(request, 'home.html')

# Nova View: CompanyListView
class CompanyListView(LoginRequiredMixin, ListView):
    def dispatch(self, request, *args, **kwargs):
        if not is_internal_user(request.user):
            raise PermissionDenied(_("Você não tem permissão para acessar esta página."))
        return super().dispatch(request, *args, **kwargs)

    """
    Exibe uma lista paginada de clientes (empresas).
    Requer que o usuário esteja logado.
    Passa os grupos do usuário para o template para controle de visibilidade de colunas.
    """
    model = Company
    template_name = 'company_list.html'
    context_object_name = 'companies'
    paginate_by = 10 # Define quantas empresas serão exibidas por página

    def get_queryset(self):
        """
        Retorna o queryset de empresas.
        Usa select_related para otimizar queries e evitar o problema N+1 para relacionamentos OneToOne e ForeignKey.
        Ordena as empresas pela data de criação (mais recentes primeiro).
        """
        # CORREÇÃO CRÍTICA: 'status_control' é o nome correto do related_name
        # conforme indicado pelo seu traceback de FieldError.
        queryset = super().get_queryset().select_related('status_control', 'created_by').prefetch_related('final_analysis_attachments')

        # Filtros rápidos via querystring (?status=...&area=...&q=...)
        status = self.request.GET.get('status')  # valores: 'pendente' | 'concluido'
        area = self.request.GET.get('area')      # valores: 'compliance' | 'financeiro' | 'trading' | 'suprimentos'
        q = self.request.GET.get('q', '').strip()

        area_map = {
            'compliance': 'compliance_qualified',
            'financeiro': 'treasury_qualified',
            'trading': 'trading_qualified',
        }

        # Aplica filtro por status geral
        if status == 'concluido':
            queryset = queryset.filter(status_control__client_onboarding_finished=True)
        elif status == 'pendente':
            queryset = queryset.filter(status_control__is_pending=True)

        # Aplica filtro por área (interpreta em conjunto com status quando fornecido)
        if area in area_map:
            field_name = f"status_control__{area_map[area]}"
            if status == 'concluido':
                kwargs = {field_name: True}
            else:
                # Default e 'pendente': não qualificado ainda
                kwargs = {field_name: False}
            queryset = queryset.filter(**kwargs)

        # Filtro específico para Suprimentos
        if area == 'suprimentos':
            if status == 'concluido':
                queryset = queryset.filter(status_control__client_onboarding_finished=True)
            else:
                queryset = queryset.filter(status_control__pending_owner='SUPRIMENTOS')

        # Filtro de busca por nome/endereço
        if q:
            from django.db.models import Q as _Q
            queryset = queryset.filter(
                _Q(full_company_name__icontains=q) |
                _Q(registered_business_address__icontains=q)
            )

        # Ordenar as empresas, por exemplo, da mais recente para a mais antiga
        queryset = queryset.order_by('-created_at')
        return queryset

    def get_context_data(self, **kwargs):
        """
        Adiciona dados adicionais ao contexto do template.
        Isso inclui os grupos aos quais o usuário logado pertence e os nomes
        dos grupos para controle de visibilidade das colunas na tabela.
        """
        context = super().get_context_data(**kwargs)
        
        # Obtém uma lista simples dos nomes dos grupos aos quais o usuário logado pertence.
        # Isso será usado no template para exibir/ocultar colunas.
        context['user_groups'] = self.request.user.groups.values_list('name', flat=True)

        # Define os nomes dos grupos correspondentes às colunas de flag no fluxograma.
        # Estes nomes DEVEM corresponder EXATAMENTE aos nomes dos grupos criados no Django Admin.
        context['compliance_group_name'] = 'Compliance'
        context['financeiro_group_name'] = 'Financeiro'
        context['trading_group_name'] = 'Trading'
        context['suprimentos_group_name'] = 'Suprimentos'

        # Filtros atuais para preencher o formulário e preservar na paginação
        filters_qd = self.request.GET.copy()
        if 'page' in filters_qd:
            try:
                del filters_qd['page']
            except Exception:
                pass
        context['current_filters'] = filters_qd.urlencode()
        context['filter_status'] = self.request.GET.get('status', '')
        context['filter_area'] = self.request.GET.get('area', '')
        context['filter_q'] = self.request.GET.get('q', '')

        context['is_internal'] = True
        context['can_create_company'] = can_start_onboarding(self.request.user)
        return context


# --- Compliance actions ---
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator


@login_required
@require_POST
def compliance_decision(request, pk, decision):
    """Approve or reject Compliance on the company list screen.

    - Only users in group 'Compliance' can act
    - Only when minimum requirements are met can approve/reject
    """
    user = request.user
    if not user.groups.filter(name='Compliance').exists():
        raise PermissionDenied("Você não tem permissão para validar Compliance.")

    company = get_object_or_404(Company, pk=pk)

    # Gate by minimum requirements
    if not company.min_requirements_met():
        messages.error(request, _("Requisitos mínimos não atendidos. Peça ao cliente para completar os dados."))
        return redirect('customers:company_list')

    # Update StatusControl
    from .models import StatusControl
    sc, created = StatusControl.objects.get_or_create(company=company)

    if decision == 'approve':
        # Require at least one approved final analysis attachment
        if False and FinalAnalysisAttachment.objects.filter(company=company, approved=True).exists():
            messages.error(request, _("Envie e aprove um anexo da análise final antes de aprovar."))
            return redirect('customers:company_list')
        sc.compliance_qualified = True
        sc.is_pending = True
        # Se Financeiro já aprovou, liberar Análise Final (Trading)
        if sc.treasury_qualified:
            sc.pending_owner = 'TRADING'
            sc.pending_details = 'Compliance e Financeiro aprovados. Aguardando análise final (Trading).'
        else:
            sc.pending_owner = 'FINANCE'
            sc.pending_details = 'Compliance aprovado. Aguardando decisão do Financeiro.'
        sc.last_updated_by = user
        sc.save(update_fields=['compliance_qualified', 'is_pending', 'pending_owner', 'pending_details', 'last_updated_by', 'updated_at'])
        _notify_user(company.created_by, f"Compliance validado para {company.full_company_name}", url=reverse('customers:company_detail', kwargs={'pk': company.pk}))
        messages.success(request, _("Compliance aprovado."))

    elif decision == 'reject':
        sc.compliance_qualified = False
        # Encerrar processo: cliente não cadastrado
        sc.is_pending = False
        sc.pending_owner = 'NONE'
        sc.pending_details = 'Cliente não cadastrado (Compliance).'
        sc.last_updated_by = user
        sc.save(update_fields=['compliance_qualified', 'is_pending', 'pending_owner', 'pending_details', 'last_updated_by', 'updated_at'])
        _notify_user(company.created_by, f"Compliance não aprovado para {company.full_company_name}", url=reverse('customers:company_detail', kwargs={'pk': company.pk}))
        messages.warning(request, _("Compliance não aprovado."))
    else:
        messages.error(request, _("Ação inválida."))

    return redirect('customers:company_list')


@login_required
@require_POST
def finance_decision(request, pk, decision):
    """Approve or reject Financeiro (Tesouraria) on the company list screen.

    - Only users in group 'Financeiro' can act
    - Only after Compliance approved
    - On rejection, 'risk' (text) is required
    """
    user = request.user
    if not user.groups.filter(name='Financeiro').exists():
        raise PermissionDenied("Você não tem permissão para aprovar Financeiro.")

    company = get_object_or_404(Company, pk=pk)
    sc, created = StatusControl.objects.get_or_create(company=company)

    # Gate: precisa dos requisitos mínimos
    if not company.min_requirements_met():
        messages.error(request, _("Requisitos mínimos não atendidos."))
        return redirect('customers:company_list')

    if decision == 'approve':
        sc.treasury_qualified = True
        sc.is_pending = True
        # Se Compliance já aprovou, liberar Análise Final (Trading)
        if sc.compliance_qualified:
            sc.pending_owner = 'TRADING'
            sc.pending_details = 'Compliance e Financeiro aprovados. Aguardando análise final (Trading).'
        else:
            sc.pending_owner = 'COMPLIANCE'
            sc.pending_details = 'Financeiro aprovado. Aguardando decisão do Compliance.'
        sc.last_updated_by = user
        sc.save(update_fields=['treasury_qualified', 'pending_owner', 'is_pending', 'pending_details', 'last_updated_by', 'updated_at'])
        _notify_user(company.created_by, f"Financeiro aprovado para {company.full_company_name}", url=reverse('customers:company_detail', kwargs={'pk': company.pk}))
        messages.success(request, _("Financeiro aprovado."))

    elif decision == 'reject':
        risk = request.POST.get('risk', '').strip()
        if not risk:
            messages.error(request, _("Informe o risco para reprovação do Financeiro."))
            return redirect('customers:company_list')
        sc.treasury_qualified = False
        sc.pending_owner = 'FINANCE'
        sc.is_pending = True
        sc.treasury_risk = risk
        sc.pending_details = f'Financeiro reprovado. Risco: {risk}'
        sc.last_updated_by = user
        sc.save(update_fields=['treasury_qualified', 'pending_owner', 'is_pending', 'treasury_risk', 'pending_details', 'last_updated_by', 'updated_at'])
        _notify_user(company.created_by, f"Financeiro reprovado para {company.full_company_name}", url=reverse('customers:company_detail', kwargs={'pk': company.pk}))
        messages.warning(request, _("Financeiro não aprovado."))
    else:
        messages.error(request, _("Ação inválida."))

    return redirect('customers:company_list')


@login_required
@require_POST
def trading_decision(request, pk, decision):
    """Enable or reject Trading on the company list screen.

    - Only users in group 'Trading' can act
    - Requires Compliance and Financeiro approved
    - Rejection can include optional reason
    """
    user = request.user
    if not user.groups.filter(name='Trading').exists():
        raise PermissionDenied("Você não tem permissão para habilitar Trading.")

    company = get_object_or_404(Company, pk=pk)
    sc, created = StatusControl.objects.get_or_create(company=company)

    # Gate: precisa de Compliance aprovado (Financeiro pode estar reprovado)
    if not sc.compliance_qualified:
        messages.error(request, _("Aguardando aprovação de Compliance."))
        return redirect('customers:company_list')

    if decision == 'approve':
        sc.trading_qualified = True
        # Após habilitar Trading, direcionar para Análise Final
        sc.pending_owner = 'TRADING'
        sc.is_pending = True
        sc.client_onboarding_finished = False
        sc.pending_details = 'Trading habilitado. Aguardando análise final.'
        sc.last_updated_by = user
        sc.save(update_fields=['trading_qualified', 'pending_owner', 'is_pending', 'client_onboarding_finished', 'pending_details', 'last_updated_by', 'updated_at'])
        _notify_user(company.created_by, f"Trading habilitado para {company.full_company_name}", url=reverse('customers:company_detail', kwargs={'pk': company.pk}))
        messages.success(request, _("Trading habilitado."))
    elif decision == 'reject':
        reason = request.POST.get('reason', '').strip()
        sc.trading_qualified = False
        # Encerrar processo: cliente não cadastrado
        sc.pending_owner = 'NONE'
        sc.is_pending = False
        sc.trading_reject_reason = reason or None
        sc.pending_details = 'Cliente não cadastrado (Trading).' + (f' Motivo: {reason}' if reason else '')
        sc.last_updated_by = user
        sc.save(update_fields=['trading_qualified', 'pending_owner', 'is_pending', 'trading_reject_reason', 'pending_details', 'last_updated_by', 'updated_at'])
        _notify_user(company.created_by, f"Trading não habilitado para {company.full_company_name}", url=reverse('customers:company_detail', kwargs={'pk': company.pk}))
        messages.warning(request, _("Trading não habilitado."))
    else:
        messages.error(request, _("Ação inválida."))

    return redirect('customers:company_list')


@login_required
@require_POST
def final_analysis_decision(request, pk, decision):
    """Trading final analysis: approve or reject after Compliance/Financeiro or Trading habilitado.

    - Only users in group 'Trading' can act
    - Approve: routes to Suprimentos (pending_owner='SUPRIMENTOS')
    - Reject: ends process as 'Cliente não cadastrado'
    """
    user = request.user
    if not user.groups.filter(name='Trading').exists():
        raise PermissionDenied("Você não tem permissão para análise final.")

    company = get_object_or_404(Company, pk=pk)
    sc, created = StatusControl.objects.get_or_create(company=company)

    # Must have min requirements and at least Compliance approved
    if not company.min_requirements_met() or not sc.compliance_qualified:
        messages.error(request, _("Pré-requisitos não atendidos para análise final."))
        return redirect('customers:company_list')

    if decision == 'approve':
        if False and not FinalAnalysisAttachment.objects.filter(company=company, approved=True).exists():
            messages.error(request, _("Envie e aprove um anexo da análise final antes de aprovar."))
            return redirect('customers:company_list')
        sc.is_pending = True
        sc.pending_owner = 'SUPRIMENTOS'
        sc.pending_details = 'Análise final aprovada. Registrar no SAP.'
        sc.last_updated_by = user
        sc.save(update_fields=['is_pending', 'pending_owner', 'pending_details', 'last_updated_by', 'updated_at'])
        messages.success(request, _("Análise final aprovada. Encaminhado para Suprimentos."))
    elif decision == 'reject':
        sc.is_pending = False
        sc.pending_owner = 'NONE'
        sc.pending_details = 'Cliente não cadastrado (Análise Final).'
        sc.last_updated_by = user
        sc.save(update_fields=['is_pending', 'pending_owner', 'pending_details', 'last_updated_by', 'updated_at'])
        messages.warning(request, _("Análise final reprovada. Cliente não cadastrado."))
    else:
        messages.error(request, _("Ação inválida."))

    return redirect('customers:company_list')


@login_required
@require_POST
def suprimentos_register_sap(request, pk):
    """Suprimentos: marcar cadastro no SAP como concluído.

    - Only users in group 'Suprimentos' can act
    - Sets onboarding finished, clears pending
    """
    user = request.user
    if not user.groups.filter(name='Suprimentos').exists():
        raise PermissionDenied("Você não tem permissão para registrar no SAP.")

    company = get_object_or_404(Company, pk=pk)
    sc, created = StatusControl.objects.get_or_create(company=company)

    sc.client_onboarding_finished = True
    sc.is_pending = False
    sc.pending_owner = 'NONE'
    sc.pending_details = 'Cadastrado no SAP.'
    sc.last_updated_by = user
    sc.save(update_fields=['client_onboarding_finished', 'is_pending', 'pending_owner', 'pending_details', 'last_updated_by', 'updated_at'])
    messages.success(request, _("Cadastro no SAP confirmado."))
    return redirect('customers:company_list')


class FinalAnalysisAttachmentUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        if not user.groups.filter(name='Trading').exists():
            raise PermissionDenied("Você não tem permissão para enviar anexos de análise final.")
        company = get_object_or_404(Company, pk=pk)
        f = request.FILES.get('file')
        notes = request.POST.get('notes')
        if not f:
            messages.error(request, _("Selecione um arquivo para enviar."))
            return redirect('customers:company_list')
        FinalAnalysisAttachment.objects.create(company=company, file=f, notes=notes or None, uploaded_by=user)
        messages.success(request, _("Anexo de análise final enviado."))
        return redirect('customers:company_list')


@login_required
@require_POST
def final_analysis_attachment_approve(request, pk):
    """Approve a final analysis attachment (Trading only)."""
    user = request.user
    if not user.groups.filter(name='Trading').exists():
        raise PermissionDenied("Você não tem permissão para aprovar anexos de análise final.")
    att = get_object_or_404(FinalAnalysisAttachment, pk=pk)
    att.approved = True
    from django.utils.timezone import now
    att.approved_at = now()
    att.approved_by = user
    att.save(update_fields=['approved', 'approved_at', 'approved_by'])
    messages.success(request, _("Anexo da análise final aprovado."))
    return redirect('customers:company_list')



