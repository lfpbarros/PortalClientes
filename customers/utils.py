# client/utils.py

from .forms import (
    CompanyForm, IndividualContactForm, BusinessInformationForm,
    OwnershipManagementInfoForm, ManagementAndKeyEmployeesForm, BoardOfDirectorsForm,
    UltimateBeneficialOwnerForm, MajorShareholderForm, GovernmentOfficialInteractionForm,
    ComplianceInformationForm, InvestigationsSanctionsInfoForm, BankingInformationForm,
    CertificationInformationForm, KYCDocumentForm, ComplianceAnalysisForm, StatusControlForm
)
from .models import (
    Company, IndividualContact, BusinessInformation, OwnershipManagementInfo,
    ManagementAndKeyEmployees, BoardOfDirectors, UltimateBeneficialOwner,
    MajorShareholder, GovernmentOfficialInteraction, ComplianceInformation,
    InvestigationsSanctionsInfo, BankingInformation, CertificationInformation,
    KYCDocument, ComplianceAnalysis, StatusControl
)
from django.forms import inlineformset_factory

# Definir as etapas do formulário e seus slugs
ONBOARDING_STEPS = {
    'general_information': 'Company Information',
    'individual_contacts': 'Individual Contact Information',
    'business_information': 'Business Information',
    'ownership_management': 'Ownership & Management Information',
    'compliance': 'Compliance',
    'investigations_sanctions': 'Investigations & Sanctions',
    'banking_information': 'Banking Information',
    'certification': 'Certification',
    'add_documents': 'To Add Docs',
    'compliance_analysis': 'Compliance Analysis',
    'status_control': 'Status Control',
}

# Mapeamento de slug para o modelo correspondente e seu formulário principal
FORM_MODEL_MAPPING = {
    'general_information': {'model': Company, 'form': CompanyForm},
    'individual_contacts': {'model': IndividualContact, 'form': IndividualContactForm,
                            'factory': inlineformset_factory(Company, IndividualContact, form=IndividualContactForm, extra=1, can_delete=True)},
    'business_information': {'model': BusinessInformation, 'form': BusinessInformationForm},
    'ownership_management': {'model': OwnershipManagementInfo, 'form': OwnershipManagementInfoForm,
                             'inlines': [
                                 {'form': ManagementAndKeyEmployeesForm, 'model': ManagementAndKeyEmployees, 'factory': inlineformset_factory(OwnershipManagementInfo, ManagementAndKeyEmployees, form=ManagementAndKeyEmployeesForm, extra=1, can_delete=True)},
                                 {'form': BoardOfDirectorsForm, 'model': BoardOfDirectors, 'factory': inlineformset_factory(OwnershipManagementInfo, BoardOfDirectors, form=BoardOfDirectorsForm, extra=1, can_delete=True)},
                                 {'form': UltimateBeneficialOwnerForm, 'model': UltimateBeneficialOwner, 'factory': inlineformset_factory(OwnershipManagementInfo, UltimateBeneficialOwner, form=UltimateBeneficialOwnerForm, extra=1, can_delete=True)},
                                 {'form': MajorShareholderForm, 'model': MajorShareholder, 'factory': inlineformset_factory(OwnershipManagementInfo, MajorShareholder, form=MajorShareholderForm, extra=1, can_delete=True)},
                                 {'form': GovernmentOfficialInteractionForm, 'model': GovernmentOfficialInteraction, 'factory': inlineformset_factory(OwnershipManagementInfo, GovernmentOfficialInteraction, form=GovernmentOfficialInteractionForm, extra=1, can_delete=True)},
                             ]},
    'compliance': {'model': ComplianceInformation, 'form': ComplianceInformationForm},
    'investigations_sanctions': {'model': InvestigationsSanctionsInfo, 'form': InvestigationsSanctionsInfoForm},
    'banking_information': {'model': BankingInformation, 'form': BankingInformationForm},
    'certification': {'model': CertificationInformation, 'form': CertificationInformationForm},
    'add_documents': {'model': KYCDocument, 'form': KYCDocumentForm, 'factory': inlineformset_factory(Company, KYCDocument, form=KYCDocumentForm, extra=1, can_delete=True)},
    'compliance_analysis': {'model': ComplianceAnalysis, 'form': ComplianceAnalysisForm},
    'status_control': {'model': StatusControl, 'form': StatusControlForm},
}

# Crie uma lista de slugs para as URLs (útil para iterar e para a regex)
ONBOARDING_STEP_SLUGS = '|'.join(ONBOARDING_STEPS.keys())