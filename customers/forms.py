from django import forms
from django.conf import settings
import os
from .models import (
    Company,
    IndividualContact,
    BusinessInformation,
    OwnershipManagementInfo,
    ManagementAndKeyEmployees,
    BoardOfDirectors,
    UltimateBeneficialOwner,
    MajorShareholder,
    GovernmentOfficialInteraction,
    ComplianceInformation,
    InvestigationsSanctionsInfo,
    BankingInformation,
    CertificationInformation,
    KYCDocument,
    ComplianceAnalysis,
    StatusControl,
    EvaluationRecord,
    EMPLOYEE_SIZE_CHOICES, # Importe as choices
    RISK_CHOICES,          # Importe as choices
    DOCUMENT_TYPE_CHOICES,  # Importe as choices
    ReverseDueDiligence,
    ReverseDueDiligenceMessage,
    ReverseDueDiligenceAttachment,
    PriorBusinessRelationship,
)
from django.forms.widgets import CheckboxSelectMultiple # Para campos com múltiplas escolhas, se necessário

# --- Formulários para a seção de "General Information" (Company e IndividualContact) ---

class CompanyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Render "Is publicly listed?" as explicit Yes/No radios
        try:
            current = bool(getattr(self.instance, 'is_publicly_listed', False)) if getattr(self, 'instance', None) else False
        except Exception:
            current = False
        self.fields['is_publicly_listed'] = forms.TypedChoiceField(
            label=self.fields.get('is_publicly_listed').label if 'is_publicly_listed' in self.fields else 'Is the company publicly listed?',
            choices=((True, 'Sim'), (False, 'Não')),
            widget=forms.RadioSelect,
            coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on') else False,
            initial=current,
            required=True,
        )
        evaluation_fields = ['evaluation_periodicity', 'last_evaluation_date', 'next_evaluation_date']
        is_staff_member = False
        try:
            if self.user is not None:
                is_staff_member = bool(self.user.groups.filter(name='Equipe').exists())
        except Exception:
            is_staff_member = False
        if self.user is not None and not is_staff_member:
            for fname in evaluation_fields:
                if fname in self.fields:
                    self.fields[fname].widget = forms.HiddenInput()
                    self.fields[fname].required = False

        # Hide CNPJ unless client is National (server-side, reliable)
        try:
            # Determine current client_type considering form prefix
            client_type_key = self.add_prefix('client_type') if getattr(self, 'prefix', None) else 'client_type'
            if self.is_bound:
                current_client_type = self.data.get(client_type_key)
            else:
                current_client_type = self.initial.get('client_type') if 'client_type' in self.initial else getattr(self.instance, 'client_type', None)

            # Only hide CNPJ when explicitly INTERNATIONAL.
            # Default/blank or NATIONAL: keep visible so the user can fill it.
            if 'cnpj' in self.fields:
                ctype = (str(current_client_type).upper() if current_client_type is not None else '')
                if ctype == 'INTERNATIONAL':
                    self.fields['cnpj'].widget = forms.HiddenInput()
                    self.fields['cnpj'].required = False
        except Exception:
            # Fail-safe: do not break rendering if any issue occurs
            pass
    class Meta:
        model = Company
        # Exclua 'created_by', 'created_at', 'updated_at' pois serão preenchidos na view/admin
        exclude = ['created_by', 'created_at', 'updated_at']
        # Defina widgets customizados se necessário (ex: DateInput para datas)
        widgets = {
            'date_of_incorporation': forms.DateInput(attrs={'type': 'date'}),
            'last_evaluation_date': forms.DateInput(attrs={'type': 'date'}),
            'next_evaluation_date': forms.DateInput(attrs={'type': 'date'}),
            # Pode adicionar widgets para TextFields para torná-los maiores, ex:
            # 'previous_names': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'full_company_name': 'Full Company Name',
            'previous_names': 'Previous names',
            'aliases_trade_names': 'Any other aliases or trade names',
            'registered_business_address': 'Registered Business Address',
            'tax_vat_number': 'Tax identification / VAT number',
            'client_type': 'Tipo de Cliente',
            'cnpj': 'CNPJ',
            'trading_address': 'Trading Address (if different from Registered Address)',
            'phone': 'Phone',
            'website': 'Website',
            'email': 'Email',
            'date_of_incorporation': 'Date of Incorporation',
            'size_number_of_employees': 'Size of the company/number of employees',
            'country_of_incorporation': 'Country of Incorporation',
            'company_registration_number': 'Company registration number',
            'is_publicly_listed': 'Is the company publicly listed?',
            'stock_exchange_info': 'Stock Exchange(s) name and listing identifier(s)',
            'evaluation_periodicity': 'Periodicidade de avaliação',
            'last_evaluation_date': 'Última avaliação em',
            'next_evaluation_date': 'Próxima avaliação em',
        }

    def clean(self):
        cleaned = super().clean()
        # Protege campos de avaliação contra alteração por não-Equipe
        evaluation_fields = ['evaluation_periodicity', 'last_evaluation_date', 'next_evaluation_date']
        is_staff_member = bool(getattr(self, 'user', None) and self.user.groups.filter(name='Equipe').exists()) if getattr(self, 'user', None) else False
        if not is_staff_member and self.instance and self.instance.pk:
            for fname in evaluation_fields:
                if fname in cleaned:
                    cleaned[fname] = getattr(self.instance, fname)
        client_type = cleaned.get('client_type')
        full_company_name = cleaned.get('full_company_name')
        previous_names = cleaned.get('previous_names')
        registered_business_address = cleaned.get('registered_business_address')
        tax_vat_number = cleaned.get('tax_vat_number')
        country_of_incorporation = cleaned.get('country_of_incorporation')
        cnpj = cleaned.get('cnpj')

        # Se a empresa for listada publicamente, exigir informação de bolsa(s)
        is_listed = cleaned.get('is_publicly_listed')
        stock_info = cleaned.get('stock_exchange_info')
        if is_listed and not stock_info:
            self.add_error('stock_exchange_info', 'Informe a(s) bolsa(s) e identificador(es) de listagem.')

        if not client_type:
            raise forms.ValidationError('Selecione se o cliente é Nacional ou Internacional.')

        # Nacional: exigir CNPJ
        if client_type == 'NATIONAL':
            if not cnpj:
                self.add_error('cnpj', 'CNPJ é obrigatório para clientes nacionais.')
            else:
                # Validação simples de CNPJ: 14 dígitos (ignora máscara). Não faz checagem de dígitos verificadores.
                import re
                digits = re.sub(r'\D', '', str(cnpj))
                if len(digits) != 14:
                    self.add_error('cnpj', 'CNPJ deve conter 14 dígitos.')

        # Internacional: exigir campos específicos
        if client_type == 'INTERNATIONAL':
            # full_company_name e registered_business_address já são obrigatórios pelo modelo,
            # reforçamos previous_names, tax_vat_number e country_of_incorporation
            if not previous_names:
                self.add_error('previous_names', 'Previous names é obrigatório para clientes internacionais.')
            if not tax_vat_number:
                self.add_error('tax_vat_number', 'VAT number é obrigatório para clientes internacionais.')
            if not country_of_incorporation:
                self.add_error('country_of_incorporation', 'Country of Incorporation é obrigatório para clientes internacionais.')

        return cleaned


class IndividualContactForm(forms.ModelForm):
    class Meta:
        model = IndividualContact
        exclude = ['created_by', 'created_at', 'updated_at', 'is_active']
        labels = {
            'company': 'Associated Company',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'position_job_title': 'Position / Job Title',
            'business_address': 'Business Address',
            'country_based': 'Country where based if different than business address',
            'direct_corporate_phone': 'Direct corporate phone',
            'direct_corporate_email': 'Direct corporate email',
        }
    # Opcional: Para esconder o campo 'company' se o formulário for acessado via URL de empresa
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial.get('company'): # Se a empresa já foi pré-definida
            self.fields['company'].widget = forms.HiddenInput()


# --- Formulário para a seção de "Business Information" ---
class BusinessInformationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Render "has_agents_intermediaries" como Sim/Não (radio)
        if 'has_agents_intermediaries' in self.fields:
            current = bool(getattr(self.instance, 'has_agents_intermediaries', False)) if getattr(self, 'instance', None) else False
            self.fields['has_agents_intermediaries'] = forms.TypedChoiceField(
                label=self.fields['has_agents_intermediaries'].label,
                choices=((True, 'Sim'), (False, 'Não')),
                widget=forms.RadioSelect,
                coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on') else False,
                initial=current,
                required=True,
            )
        # Render "has_prior_business_relationships" como Sim/Não (radio)
        if 'has_prior_business_relationships' in self.fields:
            current2 = bool(getattr(self.instance, 'has_prior_business_relationships', False)) if getattr(self, 'instance', None) else False
            self.fields['has_prior_business_relationships'] = forms.TypedChoiceField(
                label=self.fields['has_prior_business_relationships'].label,
                choices=((True, 'Sim'), (False, 'Não')),
                widget=forms.RadioSelect,
                coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on') else False,
                initial=current2,
                required=True,
            )
        # Remover campos antigos de relacionamento (agora gerenciados na tabela separada)
        for fname in ['company_name', 'nature_of_agreement', 'starting_date_relationship', 'key_contacts']:
            self.fields.pop(fname, None)
    class Meta:
        model = BusinessInformation
        exclude = ['company', 'created_by', 'created_at', 'updated_at']
        widgets = {
            'starting_date_relationship': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'nature_of_proposed_contract': "Please explain the nature of the business you intend to conduct with PRIO.",
            'has_agents_intermediaries': "Will agents or intermediaries or subcontractors be involved in our business relationship?",
            'agents_intermediaries_details': "Please provide the details in the table below (including but not limited to: Name, Country of Residence and Role):",
            'has_prior_business_relationships': "Has the company had any pre-existing business relationships with PRIO or its subsidiaries?",
            'company_name': "Company name",
            'nature_of_agreement': "Nature of the agreement",
            'starting_date_relationship': "Starting date and whether the relationship is maintained today",
            'key_contacts': "Key contacts",
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('has_agents_intermediaries') and not cleaned.get('agents_intermediaries_details'):
            self.add_error('agents_intermediaries_details', 'Informe os detalhes quando houver agentes/intermediários/subcontratados envolvidos.')
        try:
            if cleaned.get('has_prior_business_relationships') and self.instance and self.instance.pk:
                if not PriorBusinessRelationship.objects.filter(business_information=self.instance).exists():
                    self.add_error(None, 'Adicione pelo menos um relacionamento prévio na tabela.')
        except Exception:
            pass
        return cleaned


class PriorBusinessRelationshipForm(forms.ModelForm):
    class Meta:
        model = PriorBusinessRelationship
        exclude = ['business_information', 'created_by', 'created_at', 'updated_at']
        widgets = {
            'starting_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'company_name': 'Company name',
            'nature_of_agreement': 'Nature of the agreement',
            'starting_date': 'Starting date and whether the relationship is maintained today',
            'key_contacts': 'Key contacts',
        }


# --- Formulários para a seção de "Ownership & Management Information" ---
class OwnershipManagementInfoForm(forms.ModelForm):
    class Meta:
        model = OwnershipManagementInfo
        exclude = ['company', 'created_by', 'created_at', 'updated_at']
        labels = {} # Pode adicionar labels se os verbose_names não forem suficientes

class ManagementAndKeyEmployeesForm(forms.ModelForm):
    class Meta:
        model = ManagementAndKeyEmployees
        exclude = ['ownership_management']
        labels = {
            'full_name': 'Full Name',
            'job_title': 'Job Title',
            'nationality': 'Nationality',
            'passport_number': 'Passport Number',
            'country_of_residence': 'Country of Residence',
            'government_official': 'Government Official?',
        }

class BoardOfDirectorsForm(forms.ModelForm):
    class Meta:
        model = BoardOfDirectors
        exclude = ['ownership_management']
        labels = {
            'full_name': 'Full Name',
            'board_position': 'Board Position',
            'nationality': 'Nationality',
            'passport_number': 'Passport Number',
            'country_of_residence': 'Country of Residence',
            'government_official': 'Government Official?',
        }

class UltimateBeneficialOwnerForm(forms.ModelForm):
    class Meta:
        model = UltimateBeneficialOwner
        exclude = ['ownership_management']
        labels = {
            'company_individual': 'Company/Individual',
            'full_name': 'Full Name',
            'nationality_registered_country': 'Nationality / Registered Country',
            'country_of_residence': 'Country of Residence',
            'government_official_state_owned_entity': 'Government Official / State Owned Entity',
            'percentage_of_ownership': 'Percentage of Ownership',
        }

class MajorShareholderForm(forms.ModelForm):
    class Meta:
        model = MajorShareholder
        exclude = ['ownership_management']
        labels = {
            'company_individual': 'Company/Individual',
            'name_of_individual_company': 'Name of Individual / Company',
            'nationality_registered_country': 'Nationality or Registered Country',
            'address_registered_business_address': 'Address / Registered Business Address',
            'type_of_relationship': 'Type of Relationship',
            'government_official_state_owned_entity': 'Government Official / State Owned Entity',
            'percentage_of_ownership': 'Percentage of Ownership',
        }

class GovernmentOfficialInteractionForm(forms.ModelForm):
    class Meta:
        model = GovernmentOfficialInteraction
        exclude = ['ownership_management']
        labels = {
            'needs_to_interact': "Does your Company need to interact with Government Officials in order to perform the proposed contract?",
            'details': "Details (including but not limited to: Name, Country of Residence and Role)",
            'has_commercial_advantage': "Has the Company, in order to obtain or retain business or any other form of commercial advantage, provided any payments or other compensation, directly or through intermediaries, to a Government Official?",
            'commercial_advantage_details': "Details",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Render boolean fields as explicit Yes/No radios
        for fname in ['needs_to_interact', 'has_commercial_advantage']:
            if fname in self.fields:
                current = bool(getattr(self.instance, fname, False)) if getattr(self, 'instance', None) else False
                self.fields[fname] = forms.TypedChoiceField(
                    label=self.fields[fname].label,
                    choices=((True, 'Sim'), (False, 'Não')),
                    widget=forms.RadioSelect,
                    coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on') else False,
                    initial=current,
                    required=True,
                )


# --- Formulário para a seção de "Compliance" ---
class ComplianceInformationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Render selected policy booleans as Yes/No radios
        policy_fields = [
            'policy_code_of_ethics',
            'policy_crime_prevention',
            'policy_anti_bribery_corruption',
            'policy_due_diligence_processes',
            'policy_human_rights',
            'policy_donations_gifts',
            'policy_monitoring_payments',
            'monitoring_reporting_policies_procedures',
        ]
        for fname in policy_fields:
            if fname in self.fields:
                try:
                    current = bool(getattr(self.instance, fname)) if getattr(self, 'instance', None) else False
                except Exception:
                    current = False
                label = self.fields[fname].label
                self.fields[fname] = forms.TypedChoiceField(
                    label=label,
                    choices=((True, 'Sim'), (False, 'Não')),
                    widget=forms.RadioSelect,
                    coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on', 'Sim', 'sim') else False,
                    initial=current,
                    required=True,
                )
        # Render training boolean fields as Yes/No radios
        training_fields = [
            'training_bribery_corruption',
            'training_business_ethics',
            'training_market_abuse',
            'training_reporting_transactions',
        ]
        for fname in training_fields:
            if fname in self.fields:
                try:
                    current = bool(getattr(self.instance, fname)) if getattr(self, 'instance', None) else False
                except Exception:
                    current = False
                label = self.fields[fname].label
                self.fields[fname] = forms.TypedChoiceField(
                    label=label,
                    choices=((True, 'Sim'), (False, 'Não')),
                    widget=forms.RadioSelect,
                    coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on', 'Sim', 'sim') else False,
                    initial=current,
                    required=True,
                )
    class Meta:
        model = ComplianceInformation
        exclude = ['company', 'created_by', 'created_at', 'updated_at']
        labels = {
            'policy_code_of_ethics': 'Business code of ethics / code of conduct',
            'policy_crime_prevention': 'Crime prevention policies',
            'policy_anti_bribery_corruption': 'Anti-Bribery and corruption policies and procedures to prevent, detect and report bribery and corruption',
            'policy_due_diligence_processes': 'Due Diligence Processes of services providers, contractors, suppliers, and customers covering business integrity risks, e.g. Anti-Bribery and Corruption, International Sanctions and Embargoes, Anti-Money Laundering & Terrorism Financing',
            'due_diligence_process_description': 'Please describe the Due Diligence process in the table below',
            'policy_human_rights': 'Human rights and working conditions',
            'policy_donations_gifts': 'Donations, gifts and entertainment or political contributions',
            'policy_monitoring_payments': 'Monitoring system for all payments to enable to detect suspicious payments or transactions',
            'training_bribery_corruption': 'Bribery and corruption, money laundering, terrorist financing and sanctions violation',
            'training_business_ethics': 'Business ethics and conduct',
            'training_market_abuse': 'Market abuse and prohibited trading practices',
            'training_reporting_transactions': 'Identification and reporting of transactions to government authorities',
            'monitoring_reporting_policies_procedures': "Does the company have risk based policies, procedures and monitoring processes for the identification and reporting of suspicious activities?",
            'compliance_requirements_description': "Describe how the company identifies and maintains compliance with regulatory requirements",
        }


# --- Formulário para a seção de "Investigations & Sanctions" ---
class InvestigationsSanctionsInfoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Render boolean fields as explicit Yes/No radios
        bool_fields = [
            'suspended_from_business',
            'subject_of_investigations',
            'company_operations_governmental_authority',
            'sanctioned_entity_individual',
            'has_sanctioned_entity_dealings_1',
            'has_sanctioned_entity_dealings_2',
            'has_sanctioned_entity_dealings_3',
            'has_sanctioned_entity_dealings_4',
            'has_sanctioned_entity_dealings_5',
        ]
        for fname in bool_fields:
            if fname in self.fields:
                try:
                    current = bool(getattr(self.instance, fname)) if getattr(self, 'instance', None) else False
                except Exception:
                    current = False
                label = self.fields[fname].label
                self.fields[fname] = forms.TypedChoiceField(
                    label=label,
                    choices=((True, 'Sim'), (False, 'Não')),
                    widget=forms.RadioSelect,
                    coerce=lambda x: True if x in (True, 'True', 'true', '1', 1, 'on', 'Sim', 'sim') else False,
                    initial=current,
                    required=True,
                )

    def clean(self):
        cleaned = super().clean()
        # Require details when a corresponding boolean is Yes
        pairs = [
            ('suspended_from_business', 'suspended_from_business_details'),
            ('subject_of_investigations', 'subject_of_investigations_details'),
            ('company_operations_governmental_authority', 'company_operations_governmental_authority_details'),
            ('sanctioned_entity_individual', 'sanctioned_entity_individual_details'),
            ('has_sanctioned_entity_dealings_1', 'sanctioned_entity_dealings_1_details'),
            ('has_sanctioned_entity_dealings_2', 'sanctioned_entity_dealings_2_details'),
            ('has_sanctioned_entity_dealings_3', 'sanctioned_entity_dealings_3_details'),
            ('has_sanctioned_entity_dealings_4', 'sanctioned_entity_dealings_4_details'),
            ('has_sanctioned_entity_dealings_5', 'sanctioned_entity_dealings_5_details'),
        ]
        for flag, details in pairs:
            if cleaned.get(flag) and not cleaned.get(details):
                self.add_error(details, 'Por favor, descreva os detalhes quando a resposta for Sim.')
        return cleaned

    class Meta:
        model = InvestigationsSanctionsInfo
        exclude = ['company', 'created_by', 'created_at', 'updated_at']
        labels = {
            'suspended_from_business': "Has the company or any ultimate beneficial owner (including a parent company), shareholder, officer, director, employee or subsidiary been suspended from doing business in any capacity?",
            'suspended_from_business_details': "If yes, please specify the actions that have been taken to avoid similar enforcement issues in the future",
            'subject_of_investigations': "Has the company or any ultimate beneficial owner (including a parent company), shareholder, officer, director, employee or subsidiary been subject of any former investigations, allegations, or conviction for offenses involving fraud, misrepresentation, corruption, bribery, tax evasion, terrorist financing, money laundering, accounting irregularities, fake human rights violation?",
            'subject_of_investigations_details': "If yes, please provide details as well as the corrective and mitigation measures implemented, if any",
            'company_operations_governmental_authority': "Is the company or any ultimate beneficial owner (including a parent company), shareholder, officer, director, employee or subsidiary under investigation by a competent authority in any jurisdiction for criminal offenses involving fraud, misrepresentation, corruption, bribery, tax evasion, terrorist financing, money laundering, accounting irregularities, labor and/or human rights violation?",
            'company_operations_governmental_authority_details': "If the answer is yes, please specify the actions that have been taken to avoid similar enforcement issues in the future",
            'sanctioned_entity_individual': "Is the company or any of its subsidiaries or any ultimate beneficial owner (UBO), director, officer, agent, employee or affiliate of the Company, currently included on the U.S. Treasury Department's List of Specially Designated Nationals (SDN), Sectoral Sanctions Identifications (SSI) List, or otherwise subject to any U.S. sanctions administered by the U.S. Treasury Department's Office of Foreign Assets Control ('OFAC'), the United Nations ('UN') Security Council Resolutions, the European Union ('EU') sanctions, or any similar sanctions programs enforced by other national or other international sanctioning agencies/measure, including sanctions imposed against certain states, organizations and individuals (collectively 'Sanctions')?",
            'sanctioned_entity_individual_details': "If the answer is yes, please specify the details in the table below",
            'has_sanctioned_entity_dealings_1': "Does the Company or any of its UBOs, directors, officers, agents, employees or affiliates and its subsidiaries, have any locations, assets, direct or indirect investments, direct or indirect business or financial dealings in, or is organized under the laws of a Sanctioned Country or with any individual or entity subject to Sanctions (e.g. Cuba, Iran, North Korea, Russia and any other OFAC-Designated Territories or Citizens), such a 'Sanctioned Country' or with any individual or entity subject to Sanctions (each a 'Sanctioned Person')?",
            'sanctioned_entity_dealings_1_details': "If the answer is yes, please specify the details in the table below",
            'has_sanctioned_entity_dealings_2': "Does the Company or any of its subsidiaries engaged in the direct or indirect financing or facilitating of a loan to, investment in or other transaction involving a Sanctioned Country and/or a Sanctioned Person in the past?",
            'sanctioned_entity_dealings_2_details': "If yes, please describe such activities",
            'has_sanctioned_entity_dealings_3': "Does the Company or any of its directors, officers, agents, employees or affiliates have any business, operations or other direct or indirect dealings involving commodities or services of a Sanctioned Country origin or shipped to, through, or from a Sanctioned Country, or an Sanctioned Country owned or registered vessels or aircraft, or finance or sale or export of the Company's or any of its subsidiaries products for or with the involvement of any Sanctioned Country company or individual?",
            'sanctioned_entity_dealings_3_details': "If the answer is yes, please specify the details in the table below",
            'has_sanctioned_entity_dealings_4': "Does the company have any place policies and procedures to ensure compliance with Sanctions? / to prevent Sanctions violations (including but not limited to, third party screening, sanctions clauses in contracts, employee and third-party training, due diligence processes for transactions, and employee reporting or whistleblowing function, pre-embargoes and export control regulations?",
            'sanctioned_entity_dealings_4_details': "If the answer is yes, please specify the details in the table below",
            'has_sanctioned_entity_dealings_5': "Has the Company or any of its shareholders, members of the board, employees, etc. been subject to an investigation regarding Sanctions?",
            'sanctioned_entity_dealings_5_details': "If the answer is yes, please specify the details in the table below",
            'main_source_revenue_located': "Where is the company's main source of revenue located?",
            'main_source_revenue_details': "Details",
        }


# --- Formulário para a seção de "Banking Information" ---
class BankingInformationForm(forms.ModelForm):
    class Meta:
        model = BankingInformation
        exclude = ['company', 'created_by', 'created_at', 'updated_at']
        labels = {
            'bank_name': 'Bank name',
            'swift_code': 'SWIFT:',
            'account_number_iban': 'Account Number or IBAN',
        }


# --- Formulário para a seção de "Certification" ---
class CertificationInformationForm(forms.ModelForm):
    class Meta:
        model = CertificationInformation
        exclude = ['company', 'created_by', 'created_at', 'updated_at', 'date'] # 'date' é auto_now_add
        labels = {
            'full_name': 'FULL NAME:',
            'company_name': 'COMPANY:',
            'position': 'POSITION:',
            # 'date' label is implicit from auto_now_add
        }
    # Opcional: preencher company_name automaticamente
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial.get('company_name') is None and self.instance and self.instance.company:
            self.initial['company_name'] = self.instance.company.full_company_name


# --- Reverse Due Diligence (RDD) ---
class ReverseDueDiligenceCreateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        qs = Company.objects.all()
        try:
            if self.user and not self.user.groups.filter(name='Equipe').exists():
                qs = qs.filter(created_by=self.user)
        except Exception:
            qs = Company.objects.none()
        self.fields['company'].queryset = qs.order_by('full_company_name')

    attachment = forms.FileField(required=False, label='Anexo (opcional)')

    class Meta:
        model = ReverseDueDiligence
        fields = ['company', 'subject', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }
        labels = {
            'company': 'Empresa',
            'subject': 'Assunto',
            'description': 'Descrição do processo de Due Diligence Reversa',
        }


class ReverseDueDiligenceMessageForm(forms.ModelForm):
    attachment = forms.FileField(required=False, label='Anexo (opcional)')
    class Meta:
        model = ReverseDueDiligenceMessage
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Escreva sua mensagem...'}),
        }
        labels = {
            'body': 'Mensagem',
        }


# --- Formulário para a seção de "To Add Docs" ---
# Usamos FormSet para múltiplos documentos
from django.forms import inlineformset_factory

class KYCDocumentForm(forms.ModelForm):
    class Meta:
        model = KYCDocument
        fields = ['document_type', 'file', 'description', 'is_recommended']
        labels = {
            'document_type': 'Document Type',
            'file': 'Upload Document',
            'description': 'Description / Notes',
            'is_recommended': 'Recommended Document',
        }

    def clean_file(self):
        f = self.cleaned_data.get('file')
        if not f:
            return f
        allowed_exts = {'.pdf', '.jpg', '.jpeg', '.png'}
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in allowed_exts:
            raise forms.ValidationError('Tipo de arquivo não suportado. Envie PDF ou imagem (JPG/PNG).')
        try:
            max_size = int(os.getenv('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))
        except Exception:
            max_size = 10 * 1024 * 1024
        if getattr(f, 'size', None) and f.size > max_size:
            raise forms.ValidationError('Arquivo muito grande. Tamanho máximo permitido: 10MB.')
        return f

# Formulário para a seção de "Compliance Analysis"
class ComplianceAnalysisForm(forms.ModelForm):
    class Meta:
        model = ComplianceAnalysis
        exclude = ['company', 'performed_by', 'created_at', 'updated_at']
        widgets = {
            'qualified_in': forms.DateInput(attrs={'type': 'date'}),
            'next_qualification_in': forms.DateInput(attrs={'type': 'date'}),
            'risk_level': forms.RadioSelect(choices=RISK_CHOICES), # Exibe como radio buttons
        }
        labels = {
            'qualified': "Qualified 'Yes' or 'No'",
            'risk_level': "Risk Level",
            'risk_comment': "If the answer is Very High or Critical, please comment.",
            'qualified_in': "Qualified in (Date)",
            'next_qualification_in': "Next Qualification in (Date)",
        }


# Formulário para a seção de "Status Control"
class StatusControlForm(forms.ModelForm):
    class Meta:
        model = StatusControl
        exclude = ['company', 'last_updated_by', 'created_at', 'updated_at']
        labels = {
            'trading_qualified': "Trading Qualified?",
            'compliance_qualified': "Compliance Qualified?",
            'treasury_qualified': "Treasury Qualified?",
            'client_request_information': "Client Request Information?",
            'client_request_information_details': "If the answer is yes, when did client requested PRIO's information, detail indicating if via e-mail, to compile form or link",
            'prio_responded': "PRIO Responded?",
            'prio_responded_details': "If the answer is yes, when did PRIO respond, detail indicating if via e-mail, compiled form or link",
            'is_pending': "Is anything pending?",
            'pending_details': "If the answer is yes, what information/action is pending",
            'client_onboarding_finished': "Did Client Respond with OK / Finishing its Onboarding/KYC?",
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.get('instance').company if kwargs.get('instance') else None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        finished = cleaned.get('client_onboarding_finished')
        company = self.company or (self.instance.company if hasattr(self.instance, 'company') else None)
        if finished and company:
            # Se internacional, exigir que a aba 3 (Ownership & Management) tenha sido preenchida (instância exista)
            if getattr(company, 'client_type', None) == 'INTERNATIONAL':
                from .models import OwnershipManagementInfo
                if not OwnershipManagementInfo.objects.filter(company=company).exists():
                    raise forms.ValidationError('Para clientes internacionais, é obrigatório preencher a etapa "Ownership & Management Information" antes de finalizar o onboarding.')
        return cleaned


class EvaluationRecordForm(forms.ModelForm):
    class Meta:
        model = EvaluationRecord
        exclude = ['company', 'created_by', 'created_at']
        widgets = {
            'evaluation_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'evaluation_date': 'Data da Avaliação',
            'file': 'Arquivo da Avaliação',
            'notes': 'Observações',
        }
