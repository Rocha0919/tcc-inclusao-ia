from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Q

class User(AbstractUser):
    ROLE_STUDENT = 'student'
    ROLE_TEACHER = 'teacher'
    ROLE_CHOICES = [
        (ROLE_STUDENT, 'Aluno/Usuário comum'),
        (ROLE_TEACHER, 'Professor'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STUDENT,
        help_text="Define se a conta é de aluno/usuário comum ou professor"
    )
    is_pcd = models.BooleanField(
        default=True, 
        help_text="Indica se o usuário é uma Pessoa com Deficiência (PcD)"
    )

    @property
    def is_teacher(self):
        return self.role == self.ROLE_TEACHER

    @property
    def is_student(self):
        return self.role == self.ROLE_STUDENT

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
        related_name='profile',
        null=True,
        blank=True
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='student_profiles',
        null=True,
        blank=True
    )
    student_name = models.CharField(
        max_length=255,
        default='',
        blank=True,
        help_text="Nome do aluno quando o perfil for gerenciado por um professor"
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
    generation_cancel_requested = models.BooleanField(default=False)
    generation_request_id = models.PositiveBigIntegerField(default=0)
    last_generated_session_id = models.PositiveBigIntegerField(null=True, blank=True)
    last_generation_error = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, teacher__isnull=True)
                    | Q(user__isnull=True, teacher__isnull=False)
                ),
                name='accounts_profile_user_xor_teacher',
            ),
        ]

    @property
    def display_name(self):
        if self.student_name:
            return self.student_name
        if self.user:
            full_name = self.user.get_full_name().strip()
            return full_name or self.user.username
        return "Perfil sem nome"

    @property
    def is_teacher_managed(self):
        return self.teacher_id is not None

    def __str__(self):
        return f"Perfil de {self.display_name} ({self.primary_disability_category})"
