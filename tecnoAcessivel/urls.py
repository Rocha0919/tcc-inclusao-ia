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
    
]

if settings.DEBUG:
    static_dir = settings.STATICFILES_DIRS[0] if getattr(settings, 'STATICFILES_DIRS', None) else settings.STATIC_ROOT
    urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
