from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from customers.views import LogoutNotifyView
from customers.views import (
    custom_permission_denied_view,
    custom_page_not_found_view,
    custom_server_error_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Login e Logout
    # Esta linha deve vir ANTES do include para 'customers/'
    # se você quer que o login seja a página inicial do site.
    path('', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', LogoutNotifyView.as_view(), name='logout'),

    # URLs do app customers - AGORA COM O PREFIXO 'customers/'
    # Esta é a mudança CRÍTICA para que a URL /customers/ seja reconhecida
    path('customers/', include('customers.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Handler global de 403
handler403 = custom_permission_denied_view
handler404 = custom_page_not_found_view
handler500 = custom_server_error_view
