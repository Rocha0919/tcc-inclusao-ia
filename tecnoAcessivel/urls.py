from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Rota para as páginas principais e contas
    path('', include('apps.accounts.urls')),
    
    # Rota para a inteligência artificial e recomendações
    path('recomendacoes/', include('apps.recommendations.urls')),
    
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)