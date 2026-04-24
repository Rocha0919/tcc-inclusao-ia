from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    is_pcd = models.BooleanField(
        default=True, 
        help_text="Indica se o usuário é uma Pessoa com Deficiência (PcD)"
    )

    def __str__(self):
        return self.username

class BiopsychosocialProfile(models.Model):
    DISABILITY_CHOICES = [
        ('Física', 'Física'),
        ('TEA', 'TEA (Transtorno do Espectro Autista)'),
        ('Altas Habilidades', 'Altas Habilidades'),
        ('TDAH', 'TDAH'),
        ('Visual', 'Visual'),
        ('Múltipla', 'Múltipla'),
        ('Intelectual', 'Intelectual'),
        ('Auditiva', 'Auditiva'),
    ]

    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    primary_disability_category = models.CharField(
        max_length=100,
        choices=DISABILITY_CHOICES,
        help_text="Categoria principal para filtragem inicial de recursos"
    )
    
    dynamic_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Respostas do formulário (Ex: escolaridade, barreiras específicas)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_generating = models.BooleanField(default=False)

    def __str__(self):
        return f"Perfil de {self.user.username} ({self.primary_disability_category})"