from django.urls import path, re_path
from .views import (
    CompanyOnboardingCreateView,
    CompanyOnboardingUpdateView,
    CompanyOnboardingStepView,
    CompanyDetailView,
    CompanyListView,  # Certifique-se de que esta view está importada e definida em views.py
    DashboardView,
)
from .views import IndividualContactCreateView, IndividualContactUpdateView, IndividualContactDeleteView
from .views import (
    PriorBusinessRelationshipCreateView, PriorBusinessRelationshipUpdateView, PriorBusinessRelationshipDeleteView,
    MKECreateView, MKEUpdateView, MKEDeleteView,
    BoardCreateView, BoardUpdateView, BoardDeleteView,
    UBOCreateView, UBOUpdateView, UBODeleteView,
    ShareholderCreateView, ShareholderUpdateView, ShareholderDeleteView,
)
from .views_docs import KYCDocumentCreateView, KYCDocumentUpdateView, KYCDocumentDeleteView
from .views import PriorBusinessRelationshipCreateView, PriorBusinessRelationshipUpdateView, PriorBusinessRelationshipDeleteView
from .views import EvaluationRecordUploadView
from .views import CompanyEvaluationUpdateView
from .views import ReverseDueDiligenceCreateView, ReverseDueDiligenceDetailView, ReverseDueDiligenceListView
from .views import compliance_decision, finance_decision, trading_decision, final_analysis_decision, suprimentos_register_sap, FinalAnalysisAttachmentUploadView, final_analysis_attachment_approve

# IMPORTANTE: Importar ONBOARDING_STEP_SLUGS de customers.utils
# O ONBOARDING_STEPS em si não é usado diretamente aqui, apenas o slug string
from .utils import ONBOARDING_STEP_SLUGS


app_name = 'customers' # Define o namespace da aplicação para uso em {% url 'customers:...' %}

urlpatterns = [
    # --- URLs de Listagem e Detalhes de Clientes (Empresas) ---
    # Rota principal para listar todos os clientes (empresas).
    # Acessível via /customers/
    path('', CompanyListView.as_view(), name='company_list'),

    # Rota para ver os detalhes de um cliente (empresa) específico.
    # Acessível via /customers/<id_da_empresa>/
    path('<int:pk>/', CompanyDetailView.as_view(), name='company_detail'),
    path('<int:pk>/evaluations/upload/', EvaluationRecordUploadView.as_view(), name='evaluation_upload'),
    path('<int:pk>/evaluations/update/', CompanyEvaluationUpdateView.as_view(), name='evaluation_update'),

    # --- URLs do Fluxo de Onboarding KYC ---

    # Rota para iniciar um novo processo de Onboarding (cria uma nova empresa).
    # Acessível via /customers/onboarding/new/
    path('onboarding/new/', CompanyOnboardingCreateView.as_view(), name='company_onboarding_create'),

    # Rota para gerenciar as etapas do formulário de Onboarding para uma empresa existente.
    # Usa re_path para validar o 'step_slug' contra uma lista predefinida de slugs.
    # Acessível via /customers/onboarding/<id_da_empresa>/<slug_da_etapa>/
    # Ex: /customers/onboarding/123/general_information/
    re_path(
        r'onboarding/(?P<pk>\d+)/(?P<step_slug>' + ONBOARDING_STEP_SLUGS + r')/$',
        CompanyOnboardingStepView.as_view(),
        name='company_onboarding_step'
    ),

    # Individual Contacts CRUD durante o onboarding
    path('onboarding/<int:pk>/contacts/add/', IndividualContactCreateView.as_view(), name='individual_contact_add'),
    path('onboarding/<int:pk>/contacts/<int:contact_pk>/edit/', IndividualContactUpdateView.as_view(), name='individual_contact_edit'),
    path('onboarding/<int:pk>/contacts/<int:contact_pk>/delete/', IndividualContactDeleteView.as_view(), name='individual_contact_delete'),

    # Prior Business Relationships CRUD durante o onboarding
    path('onboarding/<int:pk>/business/prior/add/', PriorBusinessRelationshipCreateView.as_view(), name='prior_business_add'),
    path('onboarding/<int:pk>/business/prior/<int:rel_pk>/edit/', PriorBusinessRelationshipUpdateView.as_view(), name='prior_business_edit'),
    path('onboarding/<int:pk>/business/prior/<int:rel_pk>/delete/', PriorBusinessRelationshipDeleteView.as_view(), name='prior_business_delete'),

    # Ownership & Management CRUD (Etapa 4)
    path('onboarding/<int:pk>/ownership/mke/add/', MKECreateView.as_view(), name='ownership_mgmt_add_mke'),
    path('onboarding/<int:pk>/ownership/mke/<int:item_pk>/edit/', MKEUpdateView.as_view(), name='ownership_mgmt_edit_mke'),
    path('onboarding/<int:pk>/ownership/mke/<int:item_pk>/delete/', MKEDeleteView.as_view(), name='ownership_mgmt_del_mke'),
    path('onboarding/<int:pk>/ownership/board/add/', BoardCreateView.as_view(), name='ownership_mgmt_add_board'),
    path('onboarding/<int:pk>/ownership/board/<int:item_pk>/edit/', BoardUpdateView.as_view(), name='ownership_mgmt_edit_board'),
    path('onboarding/<int:pk>/ownership/board/<int:item_pk>/delete/', BoardDeleteView.as_view(), name='ownership_mgmt_del_board'),
    path('onboarding/<int:pk>/ownership/ubo/add/', UBOCreateView.as_view(), name='ownership_mgmt_add_ubo'),
    path('onboarding/<int:pk>/ownership/ubo/<int:item_pk>/edit/', UBOUpdateView.as_view(), name='ownership_mgmt_edit_ubo'),
    path('onboarding/<int:pk>/ownership/ubo/<int:item_pk>/delete/', UBODeleteView.as_view(), name='ownership_mgmt_del_ubo'),
    path('onboarding/<int:pk>/ownership/shareholder/add/', ShareholderCreateView.as_view(), name='ownership_mgmt_add_shareholder'),
    path('onboarding/<int:pk>/ownership/shareholder/<int:item_pk>/edit/', ShareholderUpdateView.as_view(), name='ownership_mgmt_edit_shareholder'),
    path('onboarding/<int:pk>/ownership/shareholder/<int:item_pk>/delete/', ShareholderDeleteView.as_view(), name='ownership_mgmt_del_shareholder'),

    # KYC Documents (Add Docs step)
    path('onboarding/<int:pk>/documents/add/', KYCDocumentCreateView.as_view(), name='kyc_document_add'),
    path('onboarding/<int:pk>/documents/<int:doc_pk>/edit/', KYCDocumentUpdateView.as_view(), name='kyc_document_edit'),
    path('onboarding/<int:pk>/documents/<int:doc_pk>/delete/', KYCDocumentDeleteView.as_view(), name='kyc_document_delete'),

    # Rota de redirecionamento para a primeira etapa do onboarding de uma empresa existente.
    # Útil se alguém acessar /customers/onboarding/<id_da_empresa>/ sem um slug de etapa.
    # Acessível via /customers/onboarding/<id_da_empresa>/start/
    path('onboarding/<int:pk>/start/', CompanyOnboardingUpdateView.as_view(), name='company_onboarding_start'),

    # Dashboard com KPIs e pendências
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # Reverse Due Diligence (RDD)
    path('rdd/', ReverseDueDiligenceListView.as_view(), name='rdd_list'),
    path('rdd/new/', ReverseDueDiligenceCreateView.as_view(), name='rdd_create'),
    path('rdd/<int:pk>/', ReverseDueDiligenceDetailView.as_view(), name='rdd_detail'),

    # Compliance actions
    path('<int:pk>/compliance/<str:decision>/', compliance_decision, name='compliance_decision'),
    # Finance actions
    path('<int:pk>/finance/<str:decision>/', finance_decision, name='finance_decision'),
    # Trading actions
    path('<int:pk>/trading/<str:decision>/', trading_decision, name='trading_decision'),
    # Trading final analysis (order matters: upload before decision)
    path('<int:pk>/trading-final/upload/', FinalAnalysisAttachmentUploadView.as_view(), name='final_analysis_upload'),
    path('<int:pk>/trading-final/<str:decision>/', final_analysis_decision, name='final_analysis_decision'),
    path('trading-final/attachment/<int:pk>/approve/', final_analysis_attachment_approve, name='final_analysis_attachment_approve'),
    # Suprimentos registers SAP
    path('<int:pk>/suprimentos/register-sap/', suprimentos_register_sap, name='suprimentos_register_sap'),
]
