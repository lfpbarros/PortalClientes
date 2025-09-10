from django.contrib import admin
from .models import (
    Company,
    IndividualContact,
    BusinessInformation,
    OwnershipManagementInfo,
    ComplianceInformation,
    InvestigationsSanctionsInfo,
    BankingInformation,
    CertificationInformation,
    KYCDocument,
    ComplianceAnalysis,
    StatusControl,
    EvaluationRecord,
)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("full_company_name", "registered_business_address", "evaluation_periodicity", "next_evaluation_date", "created_by", "created_at")
    search_fields = ("full_company_name", "registered_business_address", "email", "phone")
    list_filter = ("created_at", "evaluation_periodicity",)


@admin.register(IndividualContact)
class IndividualContactAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "company", "direct_corporate_email", "is_active")
    search_fields = ("first_name", "last_name", "direct_corporate_email", "company__full_company_name")
    list_filter = ("is_active",)


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ("company", "document_type", "uploaded_by", "uploaded_at")
    search_fields = ("company__full_company_name", "description")
    list_filter = ("document_type", "uploaded_at")


@admin.register(StatusControl)
class StatusControlAdmin(admin.ModelAdmin):
    list_display = ("company", "trading_qualified", "compliance_qualified", "treasury_qualified", "is_pending", "client_onboarding_finished")
    list_filter = ("trading_qualified", "compliance_qualified", "treasury_qualified", "is_pending", "client_onboarding_finished")
    search_fields = ("company__full_company_name",)


@admin.register(ComplianceAnalysis)
class ComplianceAnalysisAdmin(admin.ModelAdmin):
    list_display = ("company", "qualified", "risk_level", "performed_by", "created_at")
    list_filter = ("qualified", "risk_level")
    search_fields = ("company__full_company_name",)


@admin.register(BusinessInformation)
class BusinessInformationAdmin(admin.ModelAdmin):
    list_display = ("company", "created_by", "created_at")
    search_fields = ("company__full_company_name",)


@admin.register(OwnershipManagementInfo)
class OwnershipManagementInfoAdmin(admin.ModelAdmin):
    list_display = ("company", "created_by", "created_at")
    search_fields = ("company__full_company_name",)


@admin.register(ComplianceInformation)
class ComplianceInformationAdmin(admin.ModelAdmin):
    list_display = ("company", "created_by", "created_at")
    search_fields = ("company__full_company_name",)


@admin.register(InvestigationsSanctionsInfo)
class InvestigationsSanctionsInfoAdmin(admin.ModelAdmin):
    list_display = ("company", "created_by", "created_at")
    search_fields = ("company__full_company_name",)


@admin.register(BankingInformation)
class BankingInformationAdmin(admin.ModelAdmin):
    list_display = ("company", "bank_name", "created_by", "created_at")
    search_fields = ("company__full_company_name", "bank_name")


@admin.register(CertificationInformation)
class CertificationInformationAdmin(admin.ModelAdmin):
    list_display = ("company", "full_name", "position", "date")
    search_fields = ("company__full_company_name", "full_name")


@admin.register(EvaluationRecord)
class EvaluationRecordAdmin(admin.ModelAdmin):
    list_display = ("company", "evaluation_date", "created_by", "created_at")
    search_fields = ("company__full_company_name", "notes")
    list_filter = ("evaluation_date", "created_at")
