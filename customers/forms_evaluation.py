from django import forms
from .models import Company


class CompanyEvaluationForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['evaluation_periodicity', 'last_evaluation_date', 'next_evaluation_date']
        widgets = {
            'last_evaluation_date': forms.DateInput(attrs={'type': 'date'}),
            'next_evaluation_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'evaluation_periodicity': 'Periodicidade de Avaliação',
            'last_evaluation_date': 'Última Avaliação',
            'next_evaluation_date': 'Próxima Avaliação',
        }

