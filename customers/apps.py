# PORTALCLIENTES/customers/apps.py
from django.apps import AppConfig

class CustomersConfig(AppConfig): # Renomeie a classe também
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customers' 
    verbose_name = "Customers" 

    def ready(self):
        # Conecta sinais de atualização de requisitos mínimos e notificações
        from . import signals  # noqa: F401
