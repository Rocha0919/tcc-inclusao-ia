from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ai_engine.prompt_builder import PromptBuilder
from ai_engine.service import GenerationCancelled, criar_plano_para_usuario
from apps.accounts.models import BiopsychosocialProfile
from apps.recommendations.models import Feedback, GeneratedTechnology, RecommendationSession


class RecommendationGenerationFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def create_student_user(self, username='aluno'):
        return self.user_model.objects.create_user(
            username=username,
            password='senha-segura-123',
        )

    def create_teacher_user(self, username='professor'):
        return self.user_model.objects.create_user(
            username=username,
            password='senha-segura-123',
            role=self.user_model.ROLE_TEACHER,
        )

    def create_individual_profile(self, user):
        return BiopsychosocialProfile.objects.create(
            user=user,
            primary_disability_category='Visual',
            dynamic_data={},
        )

    def create_teacher_managed_profile(self, teacher, student_name='Ana'):
        return BiopsychosocialProfile.objects.create(
            teacher=teacher,
            student_name=student_name,
            primary_disability_category='Visual',
            dynamic_data={},
        )

    def test_loading_page_renders_for_individual_user(self):
        user = self.create_student_user()
        self.create_individual_profile(user)
        self.client.force_login(user)

        response = self.client.get(reverse('plan_generation_loading'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gerando recomendacao')
        self.assertContains(response, reverse('generate_plan'))
        self.assertContains(response, reverse('cancel_plan_generation'))

    @patch('apps.recommendations.views.start_plan_generation')
    def test_generate_plan_ajax_returns_processing_json_for_individual_user(self, start_mock):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        self.client.force_login(user)

        response = self.client.post(
            reverse('generate_plan'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'processing')
        self.assertEqual(response.json()['status_url'], reverse('plan_generation_status'))
        start_mock.assert_called_once_with(profile, launch_after_commit=True)

    @patch('apps.recommendations.views.start_plan_generation')
    def test_generate_plan_post_redirects_to_loading_page(self, start_mock):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        self.client.force_login(user)

        response = self.client.post(reverse('generate_plan'))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('plan_generation_loading'))
        start_mock.assert_called_once_with(profile, launch_after_commit=True)

    def test_generation_status_returns_redirect_when_session_is_ready(self):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        session = RecommendationSession.objects.create(
            profile=profile,
            justificativa_geral='Resumo',
        )
        profile.last_generated_session_id = session.id
        profile.save(update_fields=['last_generated_session_id'])
        self.client.force_login(user)

        response = self.client.get(
            reverse('plan_generation_status'),
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['generation_state'], 'completed')
        self.assertEqual(response.json()['redirect_url'], reverse('plan_detail', args=[session.id]))

    def test_generation_status_returns_canceling_when_flag_is_set_during_generation(self):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        profile.is_generating = True
        profile.generation_cancel_requested = True
        profile.last_generation_error = 'Geracao cancelada.'
        profile.save(update_fields=['is_generating', 'generation_cancel_requested', 'last_generation_error'])
        self.client.force_login(user)

        response = self.client.get(
            reverse('plan_generation_status'),
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'canceling')
        self.assertEqual(response.json()['generation_state'], 'canceling')
        self.assertFalse(response.json()['can_retry'])

    def test_cancel_generation_marks_profile_as_cancelled(self):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        profile.is_generating = True
        profile.generation_request_id = 4
        profile.save(update_fields=['is_generating', 'generation_request_id'])
        self.client.force_login(user)

        response = self.client.post(
            reverse('cancel_plan_generation'),
            {'next': reverse('profile_detail')},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'canceling')
        self.assertEqual(response.json()['redirect_url'], reverse('profile_detail'))
        self.assertTrue(profile.generation_cancel_requested)
        self.assertTrue(profile.is_generating)
        self.assertEqual(profile.generation_request_id, 4)

    def test_cancel_generation_returns_completed_when_plan_is_already_ready(self):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        session = RecommendationSession.objects.create(
            profile=profile,
            justificativa_geral='Resumo',
        )
        profile.last_generated_session_id = session.id
        profile.save(update_fields=['last_generated_session_id'])
        self.client.force_login(user)

        response = self.client.post(
            reverse('cancel_plan_generation'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'cancelled')
        self.assertEqual(response.json()['redirect_url'], reverse('profile_detail'))
        self.assertFalse(
            RecommendationSession.objects.filter(id=session.id).exists()
        )
        self.assertIsNone(profile.last_generated_session_id)
        self.assertTrue(profile.generation_cancel_requested)

    def test_generate_plan_returns_cancelled_while_cancellation_is_finishing(self):
        user = self.create_student_user()
        profile = self.create_individual_profile(user)
        profile.is_generating = True
        profile.generation_cancel_requested = True
        profile.save(update_fields=['is_generating', 'generation_cancel_requested'])
        self.client.force_login(user)

        response = self.client.post(
            reverse('generate_plan'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'canceling')
        self.assertFalse(response.json()['can_retry'])

    def test_generation_status_returns_cancelled_after_cancellation_finishes(self):
        user = self.create_student_user('aluno_cancelado_final')
        profile = self.create_individual_profile(user)
        profile.generation_cancel_requested = True
        profile.last_generation_error = 'Geracao cancelada.'
        profile.save(update_fields=['generation_cancel_requested', 'last_generation_error'])
        self.client.force_login(user)

        response = self.client.get(
            reverse('plan_generation_status'),
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'cancelled')
        self.assertEqual(response.json()['generation_state'], 'canceled')
        self.assertTrue(response.json()['can_retry'])

    def test_generation_status_returns_processing_generation_state(self):
        user = self.create_student_user('aluno_processando')
        profile = self.create_individual_profile(user)
        profile.is_generating = True
        profile.save(update_fields=['is_generating'])
        self.client.force_login(user)

        response = self.client.get(
            reverse('plan_generation_status'),
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'processing')
        self.assertEqual(response.json()['generation_state'], 'generating')

    def test_teacher_loading_page_renders_for_student_profile(self):
        teacher = self.create_teacher_user()
        student_profile = self.create_teacher_managed_profile(teacher)
        self.client.force_login(teacher)

        response = self.client.get(
            reverse('student_plan_generation_loading', args=[student_profile.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student_profile.display_name)
        self.assertContains(response, reverse('generate_student_plan', args=[student_profile.id]))
        self.assertContains(response, reverse('cancel_student_plan_generation', args=[student_profile.id]))

    @patch('apps.recommendations.views.start_plan_generation')
    def test_teacher_generate_plan_ajax_returns_processing_json(self, start_mock):
        teacher = self.create_teacher_user()
        student_profile = self.create_teacher_managed_profile(teacher)
        self.client.force_login(teacher)

        response = self.client.post(
            reverse('generate_student_plan', args=[student_profile.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'processing')
        self.assertEqual(
            response.json()['status_url'],
            reverse('student_plan_generation_status', args=[student_profile.id]),
        )
        start_mock.assert_called_once_with(student_profile, launch_after_commit=True)

    def test_teacher_cannot_cancel_generation_for_other_teacher_student(self):
        owner_teacher = self.create_teacher_user('professor_a')
        other_teacher = self.create_teacher_user('professor_b')
        student_profile = self.create_teacher_managed_profile(owner_teacher)
        self.client.force_login(other_teacher)

        response = self.client.post(
            reverse('cancel_student_plan_generation', args=[student_profile.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 404)

    def test_loading_page_uses_origin_url_when_next_is_provided(self):
        teacher = self.create_teacher_user('professor_origem')
        student_profile = self.create_teacher_managed_profile(teacher)
        self.client.force_login(teacher)

        response = self.client.get(
            reverse('student_plan_generation_loading', args=[student_profile.id]),
            {'next': reverse('teacher_dashboard')},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('teacher_dashboard'))

    def test_profile_detail_renders_generation_status_watcher_for_active_profile(self):
        user = self.create_student_user('aluno_watcher')
        profile = self.create_individual_profile(user)
        profile.is_generating = True
        profile.save(update_fields=['is_generating'])
        self.client.force_login(user)

        response = self.client.get(reverse('profile_detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-generation-watcher="true"')
        self.assertContains(response, reverse('plan_generation_status'))
        self.assertContains(response, 'data-current-state="generating"')

    def test_teacher_cancel_generation_marks_canceling_and_returns_origin(self):
        teacher = self.create_teacher_user('professor_cancela')
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Clara')
        student_profile.is_generating = True
        student_profile.generation_request_id = 9
        student_profile.save(update_fields=['is_generating', 'generation_request_id'])
        self.client.force_login(teacher)

        response = self.client.post(
            reverse('cancel_student_plan_generation', args=[student_profile.id]),
            {
                'aluno_id': str(student_profile.id),
                'next': reverse('teacher_dashboard'),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        student_profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'canceling')
        self.assertEqual(response.json()['redirect_url'], reverse('teacher_dashboard'))
        self.assertTrue(student_profile.is_generating)
        self.assertTrue(student_profile.generation_cancel_requested)
        self.assertEqual(student_profile.generation_request_id, 9)

    def test_teacher_student_detail_renders_status_watcher_for_canceling_student(self):
        teacher = self.create_teacher_user('professor_watcher_aluno')
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Paula')
        student_profile.is_generating = True
        student_profile.generation_cancel_requested = True
        student_profile.save(update_fields=['is_generating', 'generation_cancel_requested'])
        self.client.force_login(teacher)

        response = self.client.get(
            reverse('teacher_student_detail', args=[student_profile.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('student_plan_generation_status', args=[student_profile.id]))
        self.assertContains(response, 'data-current-state="canceling"')

    def test_teacher_dashboard_renders_watchers_for_active_students(self):
        teacher = self.create_teacher_user('professor_dashboard_watcher')
        active_student = self.create_teacher_managed_profile(teacher, student_name='Davi')
        active_student.is_generating = True
        active_student.save(update_fields=['is_generating'])
        self.create_teacher_managed_profile(teacher, student_name='Lia')
        self.client.force_login(teacher)

        response = self.client.get(reverse('teacher_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('student_plan_generation_status', args=[active_student.id]))
        self.assertContains(response, 'data-current-state="generating"')

    def test_profile_can_have_multiple_recommendation_sessions(self):
        teacher = self.create_teacher_user('professor_historico')
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Ana Clara')

        RecommendationSession.objects.create(
            profile=student_profile,
            justificativa_geral='Primeiro plano',
        )
        RecommendationSession.objects.create(
            profile=student_profile,
            justificativa_geral='Segundo plano',
        )

        self.assertEqual(
            RecommendationSession.objects.filter(profile=student_profile).count(),
            2,
        )

    def test_teacher_loading_page_with_start_query_clears_only_transient_generation_markers(self):
        teacher = self.create_teacher_user('professor_regeracao')
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Bianca')
        old_session = RecommendationSession.objects.create(
            profile=student_profile,
            justificativa_geral='Plano anterior',
        )
        student_profile.last_generated_session_id = old_session.id
        student_profile.generation_cancel_requested = True
        student_profile.last_generation_error = 'Geracao cancelada.'
        student_profile.save(update_fields=[
            'last_generated_session_id',
            'generation_cancel_requested',
            'last_generation_error',
        ])
        self.client.force_login(teacher)

        response = self.client.get(
            reverse('student_plan_generation_loading', args=[student_profile.id]),
            {'start': '1'},
        )

        student_profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(student_profile.last_generated_session_id)
        self.assertFalse(student_profile.generation_cancel_requested)
        self.assertEqual(student_profile.last_generation_error, '')
        self.assertEqual(
            RecommendationSession.objects.filter(profile=student_profile).count(),
            1,
        )

    def test_individual_loading_page_with_start_query_clears_only_transient_generation_markers(self):
        user = self.create_student_user('aluno_regeracao')
        profile = self.create_individual_profile(user)
        old_session = RecommendationSession.objects.create(
            profile=profile,
            justificativa_geral='Plano anterior',
        )
        profile.last_generated_session_id = old_session.id
        profile.generation_cancel_requested = True
        profile.last_generation_error = 'Geracao cancelada.'
        profile.save(update_fields=[
            'last_generated_session_id',
            'generation_cancel_requested',
            'last_generation_error',
        ])
        self.client.force_login(user)

        response = self.client.get(
            reverse('plan_generation_loading'),
            {'start': '1'},
        )

        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(profile.last_generated_session_id)
        self.assertFalse(profile.generation_cancel_requested)
        self.assertEqual(profile.last_generation_error, '')
        self.assertEqual(
            RecommendationSession.objects.filter(profile=profile).count(),
            1,
        )

    def test_cancel_generation_returns_cancelled_without_changing_profile_when_nothing_is_running(self):
        user = self.create_student_user('aluno_cancelamento_precoce')
        profile = self.create_individual_profile(user)
        self.client.force_login(user)

        response = self.client.post(
            reverse('cancel_plan_generation'),
            {'next': reverse('profile_detail')},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'cancelled')
        self.assertTrue(response.json()['can_retry'])
        self.assertEqual(response.json()['redirect_url'], reverse('profile_detail'))
        self.assertFalse(profile.generation_cancel_requested)
        self.assertFalse(profile.is_generating)

    @patch('apps.recommendations.views.start_plan_generation')
    def test_generate_plan_does_not_start_when_cancel_flag_exists_without_retry(self, start_mock):
        user = self.create_student_user('aluno_cancelado')
        profile = self.create_individual_profile(user)
        profile.generation_cancel_requested = True
        profile.last_generation_error = 'Geracao cancelada.'
        profile.save(update_fields=['generation_cancel_requested', 'last_generation_error'])
        self.client.force_login(user)

        response = self.client.post(
            reverse('generate_plan'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'cancelled')
        self.assertTrue(response.json()['can_retry'])
        start_mock.assert_not_called()

    @patch('apps.recommendations.views.start_plan_generation')
    def test_generate_plan_allows_retry_after_cancellation(self, start_mock):
        user = self.create_student_user('aluno_retry')
        profile = self.create_individual_profile(user)
        profile.generation_cancel_requested = True
        profile.last_generation_error = 'Geracao cancelada.'
        profile.save(update_fields=['generation_cancel_requested', 'last_generation_error'])
        self.client.force_login(user)

        response = self.client.post(
            reverse('generate_plan'),
            {'retry': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'processing')
        start_mock.assert_called_once_with(profile, launch_after_commit=True)

    def test_teacher_cancel_generation_marks_the_correct_student_profile(self):
        teacher = self.create_teacher_user('professor_cancelamento')
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Bruna')
        student_profile.is_generating = True
        student_profile.generation_request_id = 2
        student_profile.save(update_fields=['is_generating', 'generation_request_id'])
        self.client.force_login(teacher)

        response = self.client.post(
            reverse('cancel_student_plan_generation', args=[student_profile.id]),
            {
                'aluno_id': str(student_profile.id),
                'next': reverse('teacher_student_detail', args=[student_profile.id]),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        student_profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'canceling')
        self.assertTrue(student_profile.generation_cancel_requested)
        self.assertTrue(student_profile.is_generating)


class RecommendationGenerationServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='aluno_servico',
            password='senha-segura-123',
        )
        self.profile = BiopsychosocialProfile.objects.create(
            user=self.user,
            primary_disability_category='Visual',
            dynamic_data={},
        )

    def test_prompt_builder_uses_reference_list_without_limiting_recommendations(self):
        prompt = PromptBuilder.build_final_prompt(self.profile)

        self.assertIn(
            'Use as tecnologias fornecidas como referencia, nao como limitacao.',
            prompt,
        )
        self.assertIn(
            'Voce pode recomendar tecnologias alem das listadas abaixo, se forem mais adequadas ao perfil.',
            prompt,
        )
        self.assertIn(
            'O campo "nome" nao precisa corresponder exatamente a um item da lista de referencia',
            prompt,
        )
        self.assertNotIn('Nome exato conforme a lista fornecida', prompt)

    @patch('ai_engine.service.LLMClient.gerar_recomendacao')
    def test_cancelled_generation_does_not_persist_incomplete_session(self, llm_mock):
        llm_mock.return_value = {
            'justificativa_geral': 'Resumo',
            'tecnologias': [
                {
                    'nome': 'Leitor de Tela',
                    'o_que_e': 'Descricao',
                    'para_que_serve': 'Finalidade',
                    'justificativa_usuario': 'Justificativa',
                    'termo_youtube': 'busca',
                }
            ],
        }

        call_state = {'count': 0}

        def should_cancel():
            call_state['count'] += 1
            return call_state['count'] >= 3

        with self.assertRaises(GenerationCancelled):
            criar_plano_para_usuario(self.profile, should_cancel=should_cancel)

        self.assertEqual(RecommendationSession.objects.count(), 0)

    @patch('ai_engine.service.cancellable_sleep', return_value=None)
    @patch('ai_engine.service.LLMClient.gerar_recomendacao')
    def test_generation_accepts_free_suggestions_and_deduplicates_names(self, llm_mock, _sleep_mock):
        llm_mock.side_effect = [
            {
                'justificativa_geral': 'Resumo tecnico do perfil.',
                'tecnologias': [
                    {
                        'nome': 'Leitores de tela (ex: NVDA, VoiceOver)',
                        'o_que_e': 'Software que converte interface em audio.',
                        'para_que_serve': 'Apoia leitura e navegacao.',
                        'justificativa_usuario': 'Atende a barreira principal de leitura visual.',
                        'termo_youtube': 'nvda voiceover acessibilidade',
                    },
                    {
                        'nome': '  leitores de tela (ex: nvda, voiceover)  ',
                        'o_que_e': 'Descricao duplicada.',
                        'para_que_serve': 'Duplicado.',
                        'justificativa_usuario': 'Duplicado.',
                        'termo_youtube': 'duplicado',
                    },
                    {
                        'nome': 'Be My Eyes',
                        'o_que_e': 'Aplicativo de assistencia visual remota.',
                        'para_que_serve': 'Conecta o usuario a voluntarios ou especialistas.',
                        'justificativa_usuario': 'Ajuda em tarefas visuais pontuais do cotidiano.',
                        'termo_youtube': 'be my eyes acessibilidade',
                    },
                    {
                        'nome': 'Seeing AI',
                        'o_que_e': 'Aplicativo com leitura de texto e descricao de ambiente.',
                        'para_que_serve': 'Auxilia reconhecimento de documentos e objetos.',
                        'justificativa_usuario': 'Apoia autonomia em leitura e identificacao de itens.',
                        'termo_youtube': 'seeing ai acessibilidade',
                    },
                ],
            },
            None,
        ]

        session, _prompt = criar_plano_para_usuario(self.profile)

        technologies = list(session.technologies.order_by('id'))

        self.assertEqual(len(technologies), 3)
        self.assertEqual(
            [technology.name for technology in technologies],
            [
                'Leitores de tela (ex: NVDA, VoiceOver)',
                'Be My Eyes',
                'Seeing AI',
            ],
        )
        self.assertEqual(
            technologies[0].recommendation_source,
            GeneratedTechnology.SOURCE_JSON_REFERENCE,
        )
        self.assertEqual(
            technologies[1].recommendation_source,
            GeneratedTechnology.SOURCE_AI_SUGGESTED,
        )
        self.assertEqual(
            technologies[2].recommendation_source,
            GeneratedTechnology.SOURCE_AI_SUGGESTED,
        )
        self.assertEqual(
            technologies[1].video_search_term,
            'be my eyes acessibilidade',
        )


class RecommendationFeedbackFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def create_student_user(self, username='aluno_feedback'):
        return self.user_model.objects.create_user(
            username=username,
            password='senha-segura-123',
        )

    def create_teacher_user(self, username='professor_feedback'):
        return self.user_model.objects.create_user(
            username=username,
            password='senha-segura-123',
            role=self.user_model.ROLE_TEACHER,
        )

    def create_individual_profile(self, user):
        return BiopsychosocialProfile.objects.create(
            user=user,
            primary_disability_category='Visual',
            dynamic_data={},
        )

    def create_teacher_managed_profile(self, teacher, student_name='Ana'):
        return BiopsychosocialProfile.objects.create(
            teacher=teacher,
            student_name=student_name,
            primary_disability_category='Visual',
            dynamic_data={},
        )

    def create_session_with_technology(self, profile, tech_name='Leitor de Tela'):
        session = RecommendationSession.objects.create(
            profile=profile,
            justificativa_geral='Resumo',
        )
        technology = GeneratedTechnology.objects.create(
            session=session,
            ai_model='llama3',
            name=tech_name,
            what_is_it='Descricao',
            purpose='Finalidade',
            justification='Justificativa',
            video_search_term='busca',
        )
        return session, technology

    def test_teacher_can_create_and_update_feedback_for_own_student_plan(self):
        teacher = self.create_teacher_user()
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Bruna')
        session, technology = self.create_session_with_technology(student_profile)
        self.client.force_login(teacher)

        create_response = self.client.post(
            reverse('feedback_create', args=[session.id, technology.id]),
            {
                'score': '5',
                'user_comment': 'Muito util para a aluna.',
            },
        )

        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(Feedback.objects.filter(session=session, resource=technology).count(), 1)
        feedback = Feedback.objects.get(session=session, resource=technology)
        self.assertEqual(feedback.score, 5)
        self.assertEqual(feedback.user_comment, 'Muito util para a aluna.')

        update_response = self.client.post(
            reverse('feedback_create', args=[session.id, technology.id]),
            {
                'score': '4',
                'user_comment': 'A recomendacao continua boa.',
            },
        )

        feedback.refresh_from_db()
        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(Feedback.objects.filter(session=session, resource=technology).count(), 1)
        self.assertEqual(feedback.score, 4)
        self.assertEqual(feedback.user_comment, 'A recomendacao continua boa.')

    def test_teacher_cannot_create_feedback_for_other_teacher_student(self):
        owner_teacher = self.create_teacher_user('professora_dona')
        other_teacher = self.create_teacher_user('professor_intruso')
        student_profile = self.create_teacher_managed_profile(owner_teacher, student_name='Carla')
        session, technology = self.create_session_with_technology(student_profile)
        self.client.force_login(other_teacher)

        response = self.client.post(
            reverse('feedback_create', args=[session.id, technology.id]),
            {
                'score': '5',
                'user_comment': 'Nao deveria salvar.',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Feedback.objects.count(), 0)

    def test_plan_detail_shows_saved_feedback_for_teacher(self):
        teacher = self.create_teacher_user('professor_plano_feedback')
        student_profile = self.create_teacher_managed_profile(teacher, student_name='Daniela')
        session, technology = self.create_session_with_technology(student_profile, tech_name='Ampliador')
        Feedback.objects.create(
            session=session,
            resource=technology,
            score=5,
            user_comment='Funcionou muito bem em sala.',
        )
        self.client.force_login(teacher)

        response = self.client.get(reverse('plan_detail', args=[session.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Avaliacao salva')
        self.assertContains(response, 'Funcionou muito bem em sala.')
        self.assertContains(response, 'Editar avaliacao')

    def test_teacher_feedback_history_can_be_filtered_by_student(self):
        teacher = self.create_teacher_user('professor_historico_feedback')
        student_one = self.create_teacher_managed_profile(teacher, student_name='Eduarda')
        student_two = self.create_teacher_managed_profile(teacher, student_name='Fabio')
        session_one, technology_one = self.create_session_with_technology(student_one, tech_name='Leitor A')
        session_two, technology_two = self.create_session_with_technology(student_two, tech_name='Leitor B')
        Feedback.objects.create(session=session_one, resource=technology_one, score=4, user_comment='Bom para Eduarda.')
        Feedback.objects.create(session=session_two, resource=technology_two, score=3, user_comment='Bom para Fabio.')
        self.client.force_login(teacher)

        response = self.client.get(
            reverse('feedback_history'),
            {'student_id': student_one.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Historico de avaliacoes de Eduarda')
        self.assertContains(response, 'Leitor A')
        self.assertNotContains(response, 'Leitor B')
        self.assertContains(response, reverse('teacher_student_detail', args=[student_one.id]))

    def test_teacher_cannot_filter_feedback_history_for_other_teacher_student(self):
        owner_teacher = self.create_teacher_user('professor_hist_dono')
        intruder_teacher = self.create_teacher_user('professor_hist_intruso')
        student_profile = self.create_teacher_managed_profile(owner_teacher, student_name='Gabriela')
        self.client.force_login(intruder_teacher)

        response = self.client.get(
            reverse('feedback_history'),
            {'student_id': student_profile.id},
        )

        self.assertEqual(response.status_code, 404)
