from django.db import models
from django.conf import settings
from datetime import date
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

# 1.General Information

# Choices para o campo de tamanho de empresa/número de funcionários
EMPLOYEE_SIZE_CHOICES = [
    ('1-10', '1-10 employees'),
    ('11-50', '11-50 employees'),
    ('51-200', '51-200 employees'),
    ('201-500', '201-500 employees'),
    ('501-1000', '501-1000 employees'),
    ('1001-5000', '1001-5000 employees'),
    ('5001+', '5001+ employees'),
]

# Avaliação periódica da Empresa
EVALUATION_FREQUENCY_CHOICES = [
    ('NONE', 'Sem periodicidade'),
    ('MONTHLY', 'Mensal'),
    ('QUARTERLY', 'Trimestral'),
    ('SEMIANNUAL', 'Semestral'),
    ('ANNUAL', 'Anual'),
]

class Company(models.Model):
    CLIENT_TYPE_CHOICES = [
        ('NATIONAL', 'Nacional'),
        ('INTERNATIONAL', 'Internacional'),
    ]

    full_company_name = models.CharField(max_length=255, verbose_name="Full Company Name")
    previous_names = models.TextField(blank=True, null=True, verbose_name="Previous Names")
    aliases_trade_names = models.TextField(blank=True, null=True, verbose_name="Any other aliases or trade names")
    registered_business_address = models.TextField(verbose_name="Registered Business Address")
    tax_vat_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tax identification / VAT number")
    # Define se o cliente é nacional ou internacional
    client_type = models.CharField(
        max_length=20,
        choices=CLIENT_TYPE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tipo de Cliente"
    )
    # CNPJ para clientes nacionais
    cnpj = models.CharField(
        max_length=18,  # permite máscara 00.000.000/0000-00
        blank=True,
        null=True,
        verbose_name="CNPJ"
    )
    trading_address = models.TextField(blank=True, null=True, verbose_name="Trading Address (if different from Registered Address)")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Phone")
    website = models.URLField(max_length=200, blank=True, null=True, verbose_name="Website")
    email = models.EmailField(max_length=255, blank=True, null=True, verbose_name="Email")
    date_of_incorporation = models.DateField(blank=True, null=True, verbose_name="Date of Incorporation")
    size_number_of_employees = models.CharField(
        max_length=50,
        choices=EMPLOYEE_SIZE_CHOICES, # Implementação do dropdown
        blank=True,
        null=True,
        verbose_name="Size of the company/number of employees"
    )
    country_of_incorporation = models.CharField(max_length=100, blank=True, null=True, verbose_name="Country of Incorporation")
    company_registration_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Company registration number")
    is_publicly_listed = models.BooleanField(default=False, verbose_name="Is the company publicly listed?")
    stock_exchange_info = models.TextField(blank=True, null=True, verbose_name="Stock Exchange(s) name and listing identifier(s)")
    # Campos de avaliação periódica
    evaluation_periodicity = models.CharField(
        max_length=12,
        choices=EVALUATION_FREQUENCY_CHOICES,
        default='ANNUAL',
        verbose_name="Periodicidade de avaliação"
    )
    last_evaluation_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Última avaliação em"
    )
    next_evaluation_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Próxima avaliação em"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies_created', # related_name ajustado para evitar futuros conflitos
        verbose_name="Created By User"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_company_name

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ['full_company_name']

    @property
    def evaluation_is_due(self):
        return bool(self.next_evaluation_date and self.next_evaluation_date <= date.today())

    # Requisitos mínimos para avançar para Compliance
    def min_requirements_met(self):
        """Return True if the minimum info to advance to Compliance is present."""
        # Nacional: exige CNPJ
        if self.client_type == 'NATIONAL':
            return bool(self.cnpj)

        # Internacional: exige campos básicos + aba Ownership & Management criada
        if self.client_type == 'INTERNATIONAL':
            basics_ok = all([
                bool(self.full_company_name),
                bool(self.previous_names),
                bool(self.registered_business_address),
                bool(self.tax_vat_number),
                bool(self.country_of_incorporation),
            ])
            ownership_ok = hasattr(self, 'ownership_management')
            return bool(basics_ok and ownership_ok)

        # Outros casos: considerar não atendido
        return False

    def missing_min_requirements(self):
        """Return a human-readable list of missing minimum fields for gating."""
        missing = []
        if self.client_type == 'NATIONAL':
            if not self.cnpj:
                missing.append('CNPJ')
            return missing

        if self.client_type == 'INTERNATIONAL':
            if not self.full_company_name:
                missing.append('Full Company Name')
            if not self.previous_names:
                missing.append('Previous Names')
            if not self.registered_business_address:
                missing.append('Registered Business Address')
            if not self.tax_vat_number:
                missing.append('VAT number')
            if not self.country_of_incorporation:
                missing.append('Country of Incorporation')
            if not hasattr(self, 'ownership_management'):
                missing.append('Sheet 3. Ownership & Management info')
            return missing

        # Client type indefinido
        if not self.client_type:
            missing.append('Tipo de Cliente (Nacional/Internacional)')
        return missing

    @property
    def has_min_requirements(self):
        """Template-friendly boolean for minimum requirements met."""
        return self.min_requirements_met()

    @property
    def latest_final_analysis_attachment(self):
        try:
            return self.final_analysis_attachments.first()
        except Exception:
            return None


# Evaluation history attachments
class EvaluationRecord(models.Model):
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='evaluation_records',
        verbose_name="Company"
    )
    evaluation_date = models.DateField(verbose_name="Evaluation Date")
    file = models.FileField(upload_to='evaluations/', verbose_name="Evaluation File")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluation_records_created',
        verbose_name="Created By"
    )

    def __str__(self):
        return f"Evaluation {self.evaluation_date} - {self.company.full_company_name}"

    class Meta:
        verbose_name = "Evaluation Record"
        verbose_name_plural = "Evaluation Records"
        ordering = ['-evaluation_date', '-created_at']


class FinalAnalysisAttachment(models.Model):
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='final_analysis_attachments',
        verbose_name="Company"
    )
    file = models.FileField(upload_to='final_analysis/', verbose_name="Final Analysis File")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    approved = models.BooleanField(default=False, verbose_name="Approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='final_analysis_approved',
        verbose_name="Approved By"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='final_analysis_uploaded',
        verbose_name="Uploaded By"
    )

    def __str__(self):
        return f"Final Analysis Attachment for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Final Analysis Attachment"
        verbose_name_plural = "Final Analysis Attachments"
        ordering = ['-uploaded_at']

class IndividualContact(models.Model):
    # CORREÇÃO: Adicionado o campo company_id
    company = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL, # Consider SET_NULL se o contato puder existir sem a empresa
        null=True,
        blank=True,
        related_name='individual_contacts',
        verbose_name="Associated Company"
    )
    first_name = models.CharField(max_length=100, verbose_name="First Name")
    last_name = models.CharField(max_length=100, verbose_name="Last Name")
    position_job_title = models.CharField(max_length=100, blank=True, null=True, verbose_name="Position / Job Title")
    business_address = models.TextField(blank=True, null=True, verbose_name="Business Address")
    country_based = models.CharField(max_length=100, blank=True, null=True, verbose_name="Country where based if different than business address")
    direct_corporate_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Direct corporate phone")
    direct_corporate_email = models.EmailField(max_length=255, blank=True, null=True, verbose_name="Direct corporate email")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='individual_contacts_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}"
        if self.company:
            return f"{full_name} ({self.company.full_company_name})"
        return full_name

    class Meta:
        verbose_name = "Individual Contact"
        verbose_name_plural = "Individual Contacts"
        ordering = ['last_name', 'first_name']

# 2. Business Information

class BusinessInformation(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='business_information',
        verbose_name="Associated Company"
    )
    # Section 1: NATURE OF PROPOSED CONTRACT
    nature_of_proposed_contract = models.TextField(verbose_name="Please explain the nature of the business you intend to conduct with PRIO.")

    # Section 2: AGENTS/INTERMEDIARIES
    has_agents_intermediaries = models.BooleanField(
        default=False,
        verbose_name="Will agents or intermediaries or subcontractors be involved in our business relationship?"
    )
    agents_intermediaries_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="Please provide the details in the table below (including but not limited to: Name, Country of Residence and Role):"
    )

    # Section 3: PRIOR BUSINESS RELATIONSHIPS WITH PRIO
    has_prior_business_relationships = models.BooleanField(
        default=False,
        verbose_name="Has the company had any pre-existing business relationships with Repsol or its subsidiaries?"
    )
    repsol_company_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Repsol company name")
    nature_of_agreement = models.TextField(blank=True, null=True, verbose_name="Nature of the agreement")
    starting_date_relationship = models.DateField(blank=True, null=True, verbose_name="Starting date and whether the relationship is maintained today")
    key_contacts = models.TextField(blank=True, null=True, verbose_name="Key contacts")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_info_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"Business Information for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Business Information"
        verbose_name_plural = "Business Information"
        ordering = ['company__full_company_name']


class PriorBusinessRelationship(models.Model):
    business_information = models.ForeignKey(
        BusinessInformation,
        on_delete=models.CASCADE,
        related_name='prior_relationships',
        verbose_name="Business Information",
    )
    repsol_company_name = models.CharField(max_length=255, verbose_name="Repsol company name")
    nature_of_agreement = models.TextField(blank=True, null=True, verbose_name="Nature of the agreement")
    starting_date = models.DateField(blank=True, null=True, verbose_name="Starting date and whether the relationship is maintained today")
    key_contacts = models.TextField(blank=True, null=True, verbose_name="Key contacts")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prior_relationships_created',
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"{self.repsol_company_name} - {self.business_information.company.full_company_name}"

    class Meta:
        verbose_name = "Prior Business Relationship"
        verbose_name_plural = "Prior Business Relationships"

# 3. OWNERSHIP & MANAGEMENT INFORMATION

class OwnershipManagementInfo(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='ownership_management',
        verbose_name="Associated Company"
    )
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ownership_mgmt_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"Ownership & Management Info for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Ownership & Management Information"
        verbose_name_plural = "Ownership & Management Information"
        ordering = ['company__full_company_name']

class ManagementAndKeyEmployees(models.Model):
    ownership_management = models.ForeignKey(
        OwnershipManagementInfo,
        on_delete=models.CASCADE,
        related_name='management_and_key_employees',
        verbose_name="Ownership & Management Info"
    )
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    job_title = models.CharField(max_length=255, verbose_name="Job Title")
    nationality = models.CharField(max_length=100, verbose_name="Nationality")
    passport_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Passport Number")
    country_of_residence = models.CharField(max_length=100, verbose_name="Country of Residence")
    government_official = models.BooleanField(default=False, verbose_name="Government Official?")

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Management and Key Employee"
        verbose_name_plural = "Management and Key Employees"

class BoardOfDirectors(models.Model):
    ownership_management = models.ForeignKey(
        OwnershipManagementInfo,
        on_delete=models.CASCADE,
        related_name='board_of_directors',
        verbose_name="Ownership & Management Info"
    )
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    board_position = models.CharField(max_length=255, verbose_name="Board Position")
    nationality = models.CharField(max_length=100, verbose_name="Nationality")
    passport_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Passport Number")
    country_of_residence = models.CharField(max_length=100, verbose_name="Country of Residence")
    government_official = models.BooleanField(default=False, verbose_name="Government Official?")

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Board of Director"
        verbose_name_plural = "Board of Directors"

class UltimateBeneficialOwner(models.Model):
    ownership_management = models.ForeignKey(
        OwnershipManagementInfo,
        on_delete=models.CASCADE,
        related_name='ultimate_beneficial_owners',
        verbose_name="Ownership & Management Info"
    )
    company_individual = models.CharField(max_length=255, verbose_name="Company/Individual")
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    nationality_registered_country = models.CharField(max_length=100, verbose_name="Nationality / Registered Country")
    country_of_residence = models.CharField(max_length=100, verbose_name="Country of Residence")
    government_official_state_owned_entity = models.CharField(max_length=255, blank=True, null=True, verbose_name="Government Official / State Owned Entity")
    percentage_of_ownership = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Percentage of Ownership")

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Ultimate Beneficial Owner"
        verbose_name_plural = "Ultimate Beneficial Owners"
        constraints = [
            models.CheckConstraint(
                check=Q(percentage_of_ownership__gte=0) & Q(percentage_of_ownership__lte=100),
                name='ubo_percentage_between_0_100',
            ),
        ]

class MajorShareholder(models.Model):
    ownership_management = models.ForeignKey(
        OwnershipManagementInfo,
        on_delete=models.CASCADE,
        related_name='major_shareholders',
        verbose_name="Ownership & Management Info"
    )
    company_individual = models.CharField(max_length=255, verbose_name="Company/Individual")
    name_of_individual_company = models.CharField(max_length=255, verbose_name="Name of Individual / Company")
    nationality_registered_country = models.CharField(max_length=100, verbose_name="Nationality or Registered Country")
    address_registered_business_address = models.TextField(verbose_name="Address / Registered Business Address")
    type_of_relationship = models.CharField(max_length=255, verbose_name="Type of Relationship")
    government_official_state_owned_entity = models.CharField(max_length=255, blank=True, null=True, verbose_name="Government Official / State Owned Entity")
    percentage_of_ownership = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Percentage of Ownership")

    def __str__(self):
        return self.name_of_individual_company

    class Meta:
        verbose_name = "Major Shareholder"
        verbose_name_plural = "Major Shareholders"
        constraints = [
            models.CheckConstraint(
                check=Q(percentage_of_ownership__gte=0) & Q(percentage_of_ownership__lte=100),
                name='major_shareholder_percentage_between_0_100',
            ),
        ]

class GovernmentOfficialInteraction(models.Model):
    ownership_management = models.ForeignKey(
        OwnershipManagementInfo,
        on_delete=models.CASCADE,
        related_name='government_official_interactions',
        verbose_name="Ownership & Management Info"
    )
    needs_to_interact = models.BooleanField(
        default=False,
        verbose_name="Does your Company need to interact with Government Officials in order to perform the proposed contract?"
    )
    details = models.TextField(blank=True, null=True, verbose_name="Details (including but not limited to: Name, Country of Residence and Role)")
    has_commercial_advantage = models.BooleanField(
        default=False,
        verbose_name="Has the Company, in order to obtain or retain business or any other form of commercial advantage, provided any payments or other compensation, directly or through intermediaries, to a Government Official?"
    )
    commercial_advantage_details = models.TextField(blank=True, null=True, verbose_name="Details")

    def __str__(self):
        return f"Interaction with Government Officials: {self.needs_to_interact}"

    class Meta:
        verbose_name = "Government Official Interaction"
        verbose_name_plural = "Government Official Interactions"

# 4. Compliance

class ComplianceInformation(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='compliance_information',
        verbose_name="Associated Company"
    )

    policy_code_of_ethics = models.BooleanField(default=False, verbose_name="Business code of ethics / code of conduct")
    policy_crime_prevention = models.BooleanField(default=False, verbose_name="Crime prevention policies")
    policy_anti_bribery_corruption = models.BooleanField(default=False, verbose_name="Anti-Bribery and corruption policies and procedures to prevent, detect and report bribery and corruption")
    policy_due_diligence_processes = models.BooleanField(default=False, verbose_name="Due Diligence Processes of services providers, contractors, suppliers, and customers covering business integrity risks, e.g. Anti-Bribery and Corruption, International Sanctions and Embargoes, Anti-Money Laundering & Terrorism Financing")
    due_diligence_process_description = models.TextField(blank=True, null=True, verbose_name="Describe the Due Diligence process")

    policy_human_rights = models.BooleanField(default=False, verbose_name="Human rights and working conditions")
    policy_donations_gifts = models.BooleanField(default=False, verbose_name="Donations, gifts and entertainment or political contributions")
    policy_monitoring_payments = models.BooleanField(default=False, verbose_name="Monitoring system for all payments to enable to detect suspicious payments or transactions")

    training_bribery_corruption = models.BooleanField(default=False, verbose_name="Bribery and corruption, money laundering, terrorist financing and sanctions violation")
    training_business_ethics = models.BooleanField(default=False, verbose_name="Business ethics and conduct")
    training_market_abuse = models.BooleanField(default=False, verbose_name="Market abuse and prohibited trading practices")
    training_reporting_transactions = models.BooleanField(default=False, verbose_name="Identification and reporting of transactions to government authorities")

    monitoring_reporting_policies_procedures = models.BooleanField(
        default=False,
        verbose_name="Does the company have risk based policies, procedures and monitoring processes for the identification and reporting of suspicious activities?"
    )
    compliance_requirements_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Describe how the company identifies and maintains compliance with regulatory requirements"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_records_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"Compliance Information for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Compliance Information"
        verbose_name_plural = "Compliance Information"
        ordering = ['company__full_company_name']

# 5. Investigations & Sanctions

class InvestigationsSanctionsInfo(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='investigations_sanctions',
        verbose_name="Associated Company"
    )

    # Section 1: Prior Investigations
    suspended_from_business = models.BooleanField(
        default=False,
        verbose_name="Has the company or any ultimate beneficial owner (including a parent company), shareholder, officer, director, employee or subsidiary been suspended from doing business in any capacity?"
    )
    suspended_from_business_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If yes, please specify the actions that have been taken to avoid similar enforcement issues in the future"
    )

    subject_of_investigations = models.BooleanField(
        default=False,
        verbose_name="Has the company or any ultimate beneficial owner (including a parent company), shareholder, officer, director, employee or subsidiary been subject of any former investigations, allegations, or conviction for offenses involving fraud, misrepresentation, corruption, bribery, tax evasion, terrorist financing, money laundering, accounting irregularities, fake human rights violation?"
    )
    subject_of_investigations_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If yes, please provide details as well as the corrective and mitigation measures implemented, if any"
    )

    company_operations_governmental_authority = models.BooleanField(
        default=False,
        verbose_name="Is the company or any ultimate beneficial owner (including a parent company), shareholder, officer, director, employee or subsidiary under investigation by a competent authority in any jurisdiction for criminal offenses involving fraud, misrepresentation, corruption, bribery, tax evasion, terrorist financing, money laundering, accounting irregularities, labor and/or human rights violation?"
    )
    company_operations_governmental_authority_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, please specify the actions that have been taken to avoid similar enforcement issues in the future"
    )

    # Section 2: Sanctions Information
    sanctioned_entity_individual = models.BooleanField(
        default=False,
        verbose_name="Is the company or any of its subsidiaries or any ultimate beneficial owner (UBO), director, officer, agent, employee or affiliate of the Company, currently included on the U.S. Treasury Department's List of Specially Designated Nationals (SDN), Sectoral Sanctions Identifications (SSI) List, or otherwise subject to any U.S. sanctions administered by the U.S. Treasury Department's Office of Foreign Assets Control ('OFAC'), the United Nations ('UN') Security Council Resolutions, the European Union ('EU') sanctions, or any similar sanctions programs enforced by other national or other international sanctioning agencies/measure, including sanctions imposed against certain states, organizations and individuals (collectively 'Sanctions')?"
    )
    sanctioned_entity_individual_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, please specify the details in the table below"
    )

    has_sanctioned_entity_dealings_1 = models.BooleanField(
        default=False,
        verbose_name="Does the Company or any of its UBOs, directors, officers, agents, employees or affiliates and its subsidiaries, have any locations, assets, direct or indirect investments, direct or indirect business or financial dealings in, or is organized under the laws of a Sanctioned Country or with any individual or entity subject to Sanctions (e.g. Cuba, Iran, North Korea, Russia and any other OFAC-Designated Territories or Citizens), such a 'Sanctioned Country' or with any individual or entity subject to Sanctions (each a 'Sanctioned Person')?"
    )
    sanctioned_entity_dealings_1_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, please specify the details in the table below"
    )
    has_sanctioned_entity_dealings_2 = models.BooleanField(
        default=False,
        verbose_name="Does the Company or any of its subsidiaries engaged in the direct or indirect financing or facilitating of a loan to, investment in or other transaction involving a Sanctioned Country and/or a Sanctioned Person in the past?"
    )
    sanctioned_entity_dealings_2_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If yes, please describe such activities"
    )
    has_sanctioned_entity_dealings_3 = models.BooleanField(
        default=False,
        verbose_name="Does the Company or any of its directors, officers, agents, employees or affiliates have any business, operations or other direct or indirect dealings involving commodities or services of a Sanctioned Country origin or shipped to, through, or from a Sanctioned Country, or an Sanctioned Country owned or registered vessels or aircraft, or finance or sale or export of the Company’s or any of its subsidiaries products for or with the involvement of any Sanctioned Country company or individual?"
    )
    sanctioned_entity_dealings_3_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, please specify the details in the table below"
    )
    has_sanctioned_entity_dealings_4 = models.BooleanField(
        default=False,
        verbose_name="Does the company have any place policies and procedures to ensure compliance with Sanctions? / to prevent Sanctions violations (including but not limited to, third party screening, sanctions clauses in contracts, employee and third-party training, due diligence processes for transactions, and employee reporting or whistleblowing function, pre-embargoes and export control regulations?"
    )
    sanctioned_entity_dealings_4_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, please specify the details in the table below"
    )
    has_sanctioned_entity_dealings_5 = models.BooleanField(
        default=False,
        verbose_name="Has the Company or any of its shareholders, members of the board, employees, etc. been subject to an investigation regarding Sanctions?"
    )
    sanctioned_entity_dealings_5_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, please specify the details in the table below"
    )

    main_source_revenue_located = models.TextField(
        blank=True,
        null=True,
        verbose_name="Where is the company's main source of revenue located?"
    )
    main_source_revenue_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="Please specify the details in the table below"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investigations_sanctions_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"Investigations & Sanctions Info for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Investigations & Sanctions Information"
        verbose_name_plural = "Investigations & Sanctions Information"
        ordering = ['company__full_company_name']

# 6. Banking Information

class BankingInformation(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='banking_information',
        verbose_name="Associated Company"
    )

    bank_name = models.CharField(max_length=255, verbose_name="Bank Name")
    swift_code = models.CharField(max_length=11, blank=True, null=True, verbose_name="SWIFT")
    account_number_iban = models.CharField(max_length=50, verbose_name="Account Number or IBAN")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='banking_info_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"Banking Information for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Banking Information"
        verbose_name_plural = "Banking Information"
        ordering = ['company__full_company_name']

# 7. Certification

class CertificationInformation(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='certification_information',
        verbose_name="Associated Company"
    )

    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    company_name = models.CharField(max_length=255, verbose_name="Company")
    position = models.CharField(max_length=255, verbose_name="Position")
    date = models.DateField(auto_now_add=True, verbose_name="Date")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certification_created', # related_name ajustado
        verbose_name="Created By User"
    )

    def __str__(self):
        return f"Certification for {self.company.full_company_name} by {self.full_name}"

    class Meta:
        verbose_name = "Certification Information"
        verbose_name_plural = "Certification Information"
        ordering = ['company__full_company_name']

# 8. To Add Docs

DOCUMENT_TYPE_CHOICES = [
    ('COMMERCIAL_REGISTRATION', 'Commercial Registration'),
    ('CERTIFICATE_INCORPORATION', 'Certificate of Incorporation'),
    ('FINANCIAL_STATEMENTS', 'Financial Statements'),
    ('BANK_CERTIFICATE', 'Bank Certificate'),
    ('OWNERSHIP_STRUCTURE', 'Ownership Structure / Corporate Structure'),
    ('COMPLIANCE_POLICIES', 'Compliance Policies and Procedures'),
    ('OTHER', 'Other (Specify below)'),
]

class KYCDocument(models.Model): # Renomeei de 'Document' para 'KYCDocument' para clareza
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='kyc_documents',
        verbose_name="Associated Company"
    )
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
        verbose_name="Document Type"
    )
    file = models.FileField(
        upload_to='kyc_documents/',
        verbose_name="File"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description / Notes"
    )
    is_recommended = models.BooleanField(
        default=False,
        verbose_name="Recommended Document"
    )

    # Metadata
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_docs_uploaded', # related_name ajustado
        verbose_name="Uploaded By User"
    )

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.company.full_company_name}"

    class Meta:
        verbose_name = "KYC Document"
        verbose_name_plural = "KYC Documents"
        ordering = ['company__full_company_name', 'document_type']

# 9. Compliance Analysis

RISK_CHOICES = [
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('VERY_HIGH', 'Very High'),
    ('CRITICAL', 'Critical'),
]

class ComplianceAnalysis(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='compliance_analysis',
        verbose_name="Associated Company"
    )

    qualified = models.BooleanField(
        default=False,
        verbose_name="Qualified 'Yes' or 'No'"
    )

    risk_level = models.CharField(
        max_length=10,
        choices=RISK_CHOICES,
        default='LOW',
        verbose_name="Risk Level"
    )
    risk_comment = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is Very High or Critical, please comment."
    )

    qualified_in = models.DateField(
        blank=True,
        null=True,
        verbose_name="Qualified in (Date)"
    )
    next_qualification_in = models.DateField(
        blank=True,
        null=True,
        verbose_name="Next Qualification in (Date)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_analyses_performed',
        verbose_name="Analysis Performed By"
    )

    def __str__(self):
        return f"Compliance Analysis for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Compliance Analysis"
        verbose_name_plural = "Compliance Analysis"
        ordering = ['company__full_company_name']

# 10. Status Control

class StatusControl(models.Model):
    company = models.OneToOneField(
        'Company',
        on_delete=models.CASCADE,
        related_name='status_control',
        verbose_name="Associated Company"
    )

    trading_qualified = models.BooleanField(
        default=False,
        verbose_name="Trading Qualified?"
    )
    compliance_qualified = models.BooleanField(
        default=False,
        verbose_name="Compliance Qualified?"
    )
    treasury_qualified = models.BooleanField(
        default=False,
        verbose_name="Treasury Qualified?"
    )

    client_request_information = models.BooleanField(
        default=False,
        verbose_name="Client Request Information?"
    )
    client_request_information_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, when did client requested PRIO's information, detail indicating if via e-mail, to compile form or link"
    )

    prio_responded = models.BooleanField(
        default=False,
        verbose_name="PRIO Responded?"
    )
    prio_responded_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, when did PRIO respond, detail indicating if via e-mail, compiled form or link"
    )

    is_pending = models.BooleanField(
        default=False,
        verbose_name="Is anything pending?"
    )
    pending_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="If the answer is yes, what information/action is pending"
    )

    PENDING_OWNER_CHOICES = [
        ('USER', 'Usuário'),
        ('COMPLIANCE', 'Compliance'),
        ('FINANCE', 'Financeiro'),
        ('TRADING', 'Trading'),
        ('NONE', 'Nenhum'),
    ]
    pending_owner = models.CharField(
        max_length=20,
        choices=PENDING_OWNER_CHOICES,
        default='NONE',
        verbose_name="Pendência atribuída a"
    )

    min_requirements_met = models.BooleanField(
        default=False,
        verbose_name="Requisitos mínimos atendidos"
    )

    # Financeiro: em caso de reprovação, armazenar risco apontado
    treasury_risk = models.TextField(
        blank=True,
        null=True,
        verbose_name="Risco apontado pelo Financeiro (se reprovado)"
    )
    trading_reject_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo de reprovação do Trading (se reprovado)"
    )

    client_onboarding_finished = models.BooleanField(
        default=False,
        verbose_name="Did Client Respond with OK / Finishing its Onboarding/KYC?"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='status_control_updates',
        verbose_name="Last Updated By"
    )

    def __str__(self):
        return f"Status Control for {self.company.full_company_name}"

    class Meta:
        verbose_name = "Status Control"
        verbose_name_plural = "Status Control"
        ordering = ['company__full_company_name']


# Reverse Due Diligence (RDD) communication
class ReverseDueDiligence(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Aberto'),
        ('RESPONDED', 'Respondido'),
        ('CLOSED', 'Encerrado'),
    ]

    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='reverse_due_diligences')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rdd_created')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"RDD: {self.subject} ({self.company.full_company_name})"

    def get_absolute_url(self):
        return reverse('customers:rdd_detail', args=[self.pk])

    class Meta:
        verbose_name = 'Reverse Due Diligence'
        verbose_name_plural = 'Reverse Due Diligences'
        ordering = ['-updated_at', '-created_at']


class ReverseDueDiligenceMessage(models.Model):
    thread = models.ForeignKey(ReverseDueDiligence, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rdd_messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Mensagem em {self.thread_id} por {self.author_id}"

    class Meta:
        ordering = ['created_at']


class Notification(models.Model):
    class Audience(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Interno'
        CLIENT = 'CLIENT', 'Cliente'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.INTERNAL)
    # Opcional: vínculo com RDD
    rdd = models.ForeignKey(ReverseDueDiligence, on_delete=models.CASCADE, related_name='notifications', blank=True, null=True)

    def __str__(self):
        return f"Notificação para {self.recipient_id}: {self.message}"

    class Meta:
        ordering = ['-created_at']


class ReverseDueDiligenceAttachment(models.Model):
    message = models.ForeignKey(ReverseDueDiligenceMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='rdd_attachments/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo #{self.id} de msg {self.message_id}"

    class Meta:
        ordering = ['uploaded_at']
