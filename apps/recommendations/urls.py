from django.urls import path
from . import views

urlpatterns = [
    path('gerar/', views.generate_plan, name='generate_plan'),
    path('plano/<int:session_id>/', views.plan_detail, name='plan_detail'),
    path('plano/<int:session_id>/feedback/<int:item_id>/', views.feedback_create, name='feedback_create'),
    path('tecnologia/<int:tech_id>/', views.technology_detail, name='technology_detail'),
    path('meus-feedbacks/', views.feedback_history, name='feedback_history'),
    path('meus-feedbacks/<int:feedback_id>/editar/', views.feedback_edit, name='feedback_edit'),
    path('meus-feedbacks/<int:feedback_id>/excluir/', views.feedback_delete, name='feedback_delete'),
]