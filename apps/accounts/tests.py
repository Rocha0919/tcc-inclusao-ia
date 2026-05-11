from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import BiopsychosocialProfile


class TeacherStudentCreationTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.teacher = self.user_model.objects.create_user(
            username='professor_teste',
            password='senha-segura-123',
            role=self.user_model.ROLE_TEACHER,
        )
        self.client.force_login(self.teacher)

    def test_teacher_can_create_student_with_safe_generation_defaults(self):
        response = self.client.post(
            reverse('teacher_student_create'),
            {
                'student_name': 'Aluno Novo',
                'primary_disability_category': 'Visual',
                'grau_severidade': 'Moderado',
                'limitacoes_especificas': 'Nenhuma declarada',
                'estilo_aprendizado': 'Visual',
                'barreiras_cognitivas': 'Nenhuma declarada',
                'objetivo_principal': 'Ler materiais digitais',
                'barreiras': 'Dificuldade com contraste',
                'orcamento': 'gratuito',
                'dispositivos': 'Notebook',
                'nivel_tecnologico': 'Intermediario',
                'ferramentas_previas': 'Leitor de tela',
            },
        )

        student_profile = BiopsychosocialProfile.objects.get(
            teacher=self.teacher,
            student_name='Aluno Novo',
        )

        self.assertRedirects(
            response,
            reverse('teacher_student_detail', args=[student_profile.id]),
        )
        self.assertFalse(student_profile.is_generating)
        self.assertFalse(student_profile.generation_cancel_requested)
        self.assertIsNone(student_profile.last_generated_session_id)
        self.assertEqual(student_profile.last_generation_error, '')

    def test_teacher_dashboard_can_search_student_by_name(self):
        BiopsychosocialProfile.objects.create(
            teacher=self.teacher,
            student_name='Eduarda Silva',
            primary_disability_category='Visual',
            dynamic_data={},
        )
        BiopsychosocialProfile.objects.create(
            teacher=self.teacher,
            student_name='Fabio Costa',
            primary_disability_category='Auditiva',
            dynamic_data={},
        )

        response = self.client.get(
            reverse('teacher_dashboard'),
            {'q': 'Edu'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eduarda Silva')
        self.assertNotContains(response, 'Fabio Costa')
