import logging
import threading
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.models import BiopsychosocialProfile
from apps.recommendations.models import Feedback, GeneratedTechnology, RecommendationSession
from ai_engine.service import GenerationCancelled, criar_plano_para_usuario

logger = logging.getLogger(__name__)


def user_can_access_profile(user, profile):
    if not user.is_authenticated:
        return False
    return profile.user_id == user.id or profile.teacher_id == user.id


def get_profile_back_url(profile):
    if profile.teacher_id:
        return reverse('teacher_student_detail', args=[profile.id])
    return reverse('profile_detail')


def get_generation_origin_url(request, profile):
    fallback_url = get_profile_back_url(profile)
    candidate_url = request.GET.get('next') or request.POST.get('next')
    if candidate_url and url_has_allowed_host_and_scheme(
        candidate_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate_url
    return fallback_url


def get_profile_for_generation(request, profile_id=None, for_update=False):
    if profile_id is None:
        if request.user.is_teacher:
            return None
        queryset = BiopsychosocialProfile.objects.filter(
            user=request.user,
            teacher__isnull=True,
        )
        if for_update:
            queryset = queryset.select_for_update()
        return queryset.first()

    if not request.user.is_teacher:
        return None

    queryset = BiopsychosocialProfile.objects.filter(
        teacher=request.user,
        user__isnull=True,
    )
    if for_update:
        queryset = queryset.select_for_update()

    return get_object_or_404(
        queryset,
        id=profile_id,
    )


def get_accessible_session_or_404(request, session_id):
    session = get_object_or_404(
        RecommendationSession.objects.select_related('profile', 'profile__user', 'profile__teacher'),
        id=session_id,
    )
    if not user_can_access_profile(request.user, session.profile):
        raise Http404
    return session


def get_accessible_feedback_or_404(request, feedback_id):
    feedback = get_object_or_404(
        Feedback.objects.select_related('session__profile', 'resource'),
        id=feedback_id,
    )
    if not user_can_access_profile(request.user, feedback.session.profile):
        raise Http404
    return feedback


def get_feedback_history_redirect_url(request, profile=None):
    requested_student_id = request.POST.get('student_id') or request.GET.get('student_id')
    search_query = (request.POST.get('q') or request.GET.get('q') or '').strip()
    query_params = {}
    if (
        profile is not None
        and request.user.is_teacher
        and profile.teacher_id == request.user.id
        and requested_student_id
        and str(profile.id) == str(requested_student_id)
    ):
        query_params['student_id'] = profile.id
    if request.user.is_teacher and search_query:
        query_params['q'] = search_query
    history_url = reverse('feedback_history')
    if query_params:
        return f"{history_url}?{urlencode(query_params)}"
    return history_url


def get_feedback_score_value(raw_score, fallback=None):
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        return fallback

    if 1 <= score <= 5:
        return score
    return fallback


def is_json_request(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def json_generation_response(status, http_status=200, **payload):
    return JsonResponse({'status': status, **payload}, status=http_status)


def get_generation_loading_url(profile):
    if profile.teacher_id:
        return reverse('student_plan_generation_loading', args=[profile.id])
    return reverse('plan_generation_loading')


def get_generation_start_url(profile):
    if profile.teacher_id:
        return reverse('generate_student_plan', args=[profile.id])
    return reverse('generate_plan')


def get_generation_status_url(profile):
    if profile.teacher_id:
        return reverse('student_plan_generation_status', args=[profile.id])
    return reverse('plan_generation_status')


def get_generation_cancel_url(profile):
    if profile.teacher_id:
        return reverse('cancel_student_plan_generation', args=[profile.id])
    return reverse('cancel_plan_generation')


def get_generation_message(profile):
    if profile.teacher_id:
        return f'Gerando recomendacoes personalizadas para {profile.display_name}. Isso pode levar alguns instantes...'
    return 'Gerando recomendacoes personalizadas. Isso pode levar alguns instantes...'


def get_generation_error_message(profile):
    if profile.teacher_id:
        return f'Nao foi possivel gerar as recomendacoes de {profile.display_name} agora. Tente novamente em alguns instantes.'
    return 'Nao foi possivel gerar suas recomendacoes agora. Tente novamente em alguns instantes.'


def get_generation_cancelled_message(profile, is_still_finishing=False):
    if is_still_finishing:
        if profile.teacher_id:
            return (
                f'Geracao cancelada para {profile.display_name}. '
                'A etapa atual sera encerrada assim que possivel.'
            )
        return 'Geracao cancelada. A etapa atual sera encerrada assim que possivel.'

    if profile.teacher_id:
        return f'Geracao cancelada para {profile.display_name}.'
    return 'Geracao cancelada.'


def get_generation_completed_message(profile):
    if profile.teacher_id:
        return f'O plano de {profile.display_name} ja estava pronto e foi preservado.'
    return 'Seu plano ja estava pronto e foi preservado.'


def get_generation_canceling_message(profile):
    if profile.teacher_id:
        return (
            f'Cancelando a geracao de {profile.display_name}. '
            'Aguarde alguns instantes.'
        )
    return 'Cancelando geracao... aguarde alguns instantes.'


def get_cancellation_pending_retry_message(profile):
    if profile.teacher_id:
        return (
            f'O cancelamento de {profile.display_name} ainda esta sendo finalizado. '
            'Aguarde alguns instantes para tentar novamente.'
        )
    return 'O cancelamento ainda esta sendo finalizado. Aguarde alguns instantes para tentar novamente.'


def get_generation_status(profile):
    if profile.is_generating:
        if profile.generation_cancel_requested:
            return 'canceling'
        return 'generating'
    if profile.generation_cancel_requested:
        return 'canceled'
    if profile.last_generated_session_id:
        return 'completed'
    if profile.last_generation_error:
        return 'error'
    return 'idle'


def get_generation_flow_type(profile=None, request=None):
    if profile is not None:
        return 'professor' if profile.teacher_id else 'individual'
    if request is not None and getattr(request.user, 'is_teacher', False):
        return 'professor'
    return 'individual'


def build_generation_log_context(
    request=None,
    profile=None,
    requested_profile_id=None,
    requested_student_id=None,
    requested_url=None,
    status=None,
    error=None,
    **extra,
):
    context = {
        'flow': get_generation_flow_type(profile=profile, request=request),
        'profile_id': getattr(profile, 'id', None) or requested_profile_id,
        'student_id': (
            getattr(profile, 'id', None)
            if getattr(profile, 'teacher_id', None)
            else requested_student_id
        ),
        'teacher_id': getattr(profile, 'teacher_id', None),
        'logged_user_id': request.user.id if request and request.user.is_authenticated else None,
        'logged_user': request.user.username if request and request.user.is_authenticated else None,
        'request_path': request.path if request else None,
        'requested_url': requested_url,
        'status': status,
    }
    if error:
        context['error'] = error
    for key, value in extra.items():
        if value is not None:
            context[key] = value
    return context


def log_generation_event(event, request=None, profile=None, **context):
    logger.warning(
        'generation.%s | %s',
        event,
        build_generation_log_context(request=request, profile=profile, **context),
    )


def reset_generation_markers_for_new_attempt(profile):
    updated_fields = []

    if profile.generation_cancel_requested:
        profile.generation_cancel_requested = False
        updated_fields.append('generation_cancel_requested')

    if profile.last_generated_session_id is not None:
        profile.last_generated_session_id = None
        updated_fields.append('last_generated_session_id')

    if profile.last_generation_error:
        profile.last_generation_error = ''
        updated_fields.append('last_generation_error')

    if updated_fields:
        profile.save(update_fields=updated_fields)

    return updated_fields


def is_generation_request_active(profile_id, request_id):
    return BiopsychosocialProfile.objects.filter(
        id=profile_id,
        generation_request_id=request_id,
        generation_cancel_requested=False,
    ).exists()


def is_generation_request_stale(profile_id, request_id):
    return not is_generation_request_active(profile_id, request_id)


def start_plan_generation(profile, launch_after_commit=False):
    profile.generation_request_id += 1
    profile.is_generating = True
    profile.generation_cancel_requested = False
    profile.last_generated_session_id = None
    profile.last_generation_error = ''
    profile.save(
        update_fields=[
            'generation_request_id',
            'is_generating',
            'generation_cancel_requested',
            'last_generated_session_id',
            'last_generation_error',
        ]
    )
    current_profile_id = profile.id
    current_request_id = profile.generation_request_id
    log_generation_event(
        'started',
        profile=profile,
        requested_profile_id=current_profile_id,
        requested_url=get_generation_start_url(profile),
        status='generating',
        request_id=current_request_id,
    )

    def tarefa_ia():
        current_profile = None
        generated_session = None
        try:
            current_profile = BiopsychosocialProfile.objects.get(id=current_profile_id)
            log_generation_event(
                'worker_started',
                profile=current_profile,
                requested_profile_id=current_profile_id,
                status='generating',
                request_id=current_request_id,
            )
            resultado = criar_plano_para_usuario(
                current_profile,
                should_cancel=lambda: is_generation_request_stale(current_profile_id, current_request_id),
            )
            if resultado:
                generated_session, _prompt = resultado
            current_profile.refresh_from_db(fields=['generation_request_id', 'generation_cancel_requested'])
            if (
                current_profile.generation_request_id != current_request_id
                or current_profile.generation_cancel_requested
            ):
                raise GenerationCancelled
            if not resultado:
                current_profile.refresh_from_db(fields=['generation_cancel_requested'])
                if not current_profile.generation_cancel_requested:
                    current_profile.last_generation_error = get_generation_error_message(current_profile)
                    current_profile.save(update_fields=['last_generation_error'])
                    log_generation_event(
                        'worker_finished_without_result',
                        profile=current_profile,
                        requested_profile_id=current_profile_id,
                        status='error',
                        request_id=current_request_id,
                )
                return

            current_profile.last_generated_session_id = generated_session.id
            current_profile.last_generation_error = ''
            current_profile.save(update_fields=['last_generated_session_id', 'last_generation_error'])
            log_generation_event(
                'worker_completed',
                profile=current_profile,
                requested_profile_id=current_profile_id,
                status='completed',
                session_id=generated_session.id,
                request_id=current_request_id,
            )
        except GenerationCancelled:
            if current_profile is None:
                current_profile = BiopsychosocialProfile.objects.filter(id=current_profile_id).first()
            elif current_profile is not None:
                current_profile.refresh_from_db(fields=['generation_request_id', 'generation_cancel_requested'])
            if (
                generated_session is not None
                and current_profile is not None
                and current_profile.generation_request_id == current_request_id
                and current_profile.generation_cancel_requested
            ):
                generated_session.delete()
                generated_session = None
                current_profile.last_generated_session_id = None
                log_generation_event(
                    'worker_discarded_session_after_cancel',
                    profile=current_profile,
                    requested_profile_id=current_profile_id,
                    status='canceling',
                    request_id=current_request_id,
                )
            if (
                current_profile is not None
                and current_profile.generation_request_id == current_request_id
            ):
                current_profile.last_generation_error = get_generation_cancelled_message(current_profile)
                current_profile.save(update_fields=['last_generation_error'])
                log_generation_event(
                    'worker_cancelled',
                    profile=current_profile,
                    requested_profile_id=current_profile_id,
                    status='canceled',
                    request_id=current_request_id,
                )
        except Exception:
            logger.exception(
                'Erro ao gerar recomendacoes. contexto=%s',
                build_generation_log_context(
                    profile=current_profile,
                    requested_profile_id=current_profile_id,
                    status='error',
                    request_id=current_request_id,
                ),
            )
            if current_profile is None:
                current_profile = BiopsychosocialProfile.objects.filter(id=current_profile_id).first()
            elif current_profile is not None:
                current_profile.refresh_from_db(fields=['generation_request_id', 'generation_cancel_requested'])
            if (
                current_profile is not None
                and current_profile.generation_request_id == current_request_id
            ):
                if current_profile.generation_cancel_requested:
                    current_profile.last_generation_error = get_generation_cancelled_message(current_profile)
                else:
                    current_profile.last_generation_error = get_generation_error_message(current_profile)
                current_profile.save(update_fields=['last_generation_error'])
        finally:
            if current_profile is None:
                current_profile = BiopsychosocialProfile.objects.filter(id=current_profile_id).first()
            elif current_profile is not None:
                current_profile.refresh_from_db(fields=['generation_request_id'])
            if (
                current_profile is not None
                and current_profile.generation_request_id == current_request_id
            ):
                current_profile.is_generating = False
                current_profile.save(update_fields=['is_generating'])
                current_profile.refresh_from_db(fields=[
                    'generation_request_id',
                    'generation_cancel_requested',
                    'last_generated_session_id',
                    'last_generation_error',
                ])
                if (
                    current_profile.generation_cancel_requested
                    and current_profile.last_generated_session_id
                ):
                    discarded_session_id = current_profile.last_generated_session_id
                    RecommendationSession.objects.filter(
                        id=discarded_session_id,
                        profile_id=current_profile_id,
                    ).delete()
                    current_profile.last_generated_session_id = None
                    current_profile.last_generation_error = get_generation_cancelled_message(current_profile)
                    current_profile.save(update_fields=['last_generated_session_id', 'last_generation_error'])
                    current_profile.refresh_from_db(fields=[
                        'last_generated_session_id',
                        'last_generation_error',
                    ])
                    log_generation_event(
                        'worker_discarded_session_on_finalize_after_cancel',
                        profile=current_profile,
                        requested_profile_id=current_profile_id,
                        status='canceled',
                        session_id=discarded_session_id,
                        request_id=current_request_id,
                    )
                final_status = 'completed'
                if current_profile.generation_cancel_requested:
                    final_status = 'canceled'
                elif current_profile.last_generation_error:
                    final_status = 'error'
                log_generation_event(
                    'worker_finalized',
                    profile=current_profile,
                    requested_profile_id=current_profile_id,
                    status=final_status,
                    session_id=current_profile.last_generated_session_id,
                    last_error=current_profile.last_generation_error or None,
                    request_id=current_request_id,
                )
            elif current_profile is not None:
                log_generation_event(
                    'worker_finalized_stale_request',
                    profile=current_profile,
                    requested_profile_id=current_profile_id,
                    status='canceled',
                    request_id=current_request_id,
                    active_request_id=current_profile.generation_request_id,
                )

    def launch_thread():
        threading.Thread(target=tarefa_ia, daemon=True).start()

    if launch_after_commit:
        transaction.on_commit(launch_thread)
        return

    launch_thread()


@login_required
def plan_generation_loading(request, profile_id=None):
    start_requested = request.GET.get('start') == '1'

    if start_requested:
        with transaction.atomic():
            profile = get_profile_for_generation(
                request,
                profile_id=profile_id,
                for_update=True,
            )
            if not profile:
                return redirect('teacher_dashboard' if request.user.is_teacher else 'profile_detail')

            if not profile.is_generating:
                cleared_fields = reset_generation_markers_for_new_attempt(profile)
                if cleared_fields:
                    log_generation_event(
                        'loading_reset_for_new_attempt',
                        request=request,
                        profile=profile,
                        requested_profile_id=profile_id,
                        requested_url=get_generation_start_url(profile),
                        status='ready_for_new_attempt',
                        cleared_fields=','.join(cleared_fields),
                    )
    else:
        profile = get_profile_for_generation(request, profile_id=profile_id)
        if not profile:
            return redirect('teacher_dashboard' if request.user.is_teacher else 'profile_detail')

    origin_url = get_generation_origin_url(request, profile)
    generate_url = get_generation_start_url(profile)
    status_url = get_generation_status_url(profile)
    cancel_url = get_generation_cancel_url(profile)
    log_generation_event(
        'loading_opened',
        request=request,
        profile=profile,
        requested_profile_id=profile_id,
        requested_url=generate_url,
        status='loading',
        status_url=status_url,
        cancel_url=cancel_url,
        start_requested=start_requested,
        origin_url=origin_url,
        generation_status=get_generation_status(profile),
    )

    return render(request, 'recommendations/plan_loading.html', {
        'profile': profile,
        'generate_url': generate_url,
        'status_url': status_url,
        'cancel_url': cancel_url,
        'back_url': origin_url,
        'back_label': 'Voltar' if origin_url != get_profile_back_url(profile) else (
            f'Voltar para {profile.display_name}' if profile.teacher_id else 'Voltar para o painel'
        ),
        'loading_message': get_generation_message(profile),
        'flow_type': get_generation_flow_type(profile=profile),
        'logged_user': request.user.username,
        'student_id': profile.id if profile.teacher_id else '',
        'start_requested': start_requested,
        'origin_url': origin_url,
        'generation_status': get_generation_status(profile),
    })


@login_required
def plan_generation_status(request, profile_id=None):
    profile = get_profile_for_generation(request, profile_id=profile_id)
    if not profile:
        log_generation_event(
            'status_profile_not_found',
            request=request,
            requested_profile_id=profile_id,
            status='error',
        )
        return json_generation_response(
            'error',
            http_status=404,
            message='O perfil solicitado nao foi encontrado.',
        )

    profile.refresh_from_db(fields=[
        'is_generating',
        'generation_cancel_requested',
        'last_generated_session_id',
        'last_generation_error',
    ])

    current_status = get_generation_status(profile)

    if current_status == 'canceling':
        log_generation_event(
            'status_canceling',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            status='canceling',
        )
        return json_generation_response(
            'canceling',
            message=get_generation_canceling_message(profile),
            can_retry=False,
            generation_state='canceling',
        )

    if current_status == 'completed':
        log_generation_event(
            'status_ready',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            status='completed',
            session_id=profile.last_generated_session_id,
        )
        return json_generation_response(
            'success',
            redirect_url=reverse('plan_detail', args=[profile.last_generated_session_id]),
            generation_state='completed',
        )

    if current_status == 'canceled':
        log_generation_event(
            'status_cancelled',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            status='canceled',
        )
        return json_generation_response(
            'cancelled',
            message=get_generation_cancelled_message(profile),
            can_retry=True,
            generation_state='canceled',
        )

    if current_status == 'generating':
        return json_generation_response(
            'processing',
            message=get_generation_message(profile),
            generation_state='generating',
        )

    if current_status == 'error':
        log_generation_event(
            'status_error',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            status='error',
            last_error=profile.last_generation_error,
        )
        return json_generation_response(
            'error',
            message=profile.last_generation_error,
            generation_state='error',
        )

    log_generation_event(
        'status_not_found',
        request=request,
        profile=profile,
        requested_profile_id=profile_id,
        status='error',
    )
    return json_generation_response(
        'error',
        http_status=404,
        message='Nenhuma geracao em andamento foi encontrada. Voce pode tentar novamente.',
    )


@login_required
def cancel_plan_generation(request, profile_id=None):
    if request.method != 'POST':
        if is_json_request(request):
            log_generation_event(
                'cancel_invalid_request',
                request=request,
                requested_profile_id=profile_id,
                status='error',
            )
            return json_generation_response(
                'error',
                http_status=400,
                message='Requisicao invalida para cancelamento.',
            )
        return redirect('teacher_dashboard' if request.user.is_teacher else 'profile_detail')

    requested_student_id = request.POST.get('aluno_id') or None

    with transaction.atomic():
        profile = get_profile_for_generation(
            request,
            profile_id=profile_id,
            for_update=True,
        )
        if not profile:
            if is_json_request(request):
                log_generation_event(
                    'cancel_profile_not_found',
                    request=request,
                    requested_profile_id=profile_id,
                    requested_student_id=requested_student_id,
                    status='error',
                )
                return json_generation_response(
                    'error',
                    http_status=404,
                    message='O perfil solicitado nao foi encontrado.',
                )
            return redirect('teacher_dashboard' if request.user.is_teacher else 'profile_detail')

        origin_url = get_generation_origin_url(request, profile)
        log_generation_event(
            'cancel_requested',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            requested_student_id=requested_student_id,
            requested_url=get_generation_cancel_url(profile),
            status='cancel_requested',
            origin_url=origin_url,
        )

        if profile.is_generating and profile.generation_cancel_requested:
            return json_generation_response(
                'canceling',
                message=get_generation_canceling_message(profile),
                can_retry=False,
                redirect_url=origin_url,
            )

        if profile.is_generating:
            profile.generation_cancel_requested = True
            profile.last_generation_error = get_generation_canceling_message(profile)
            profile.save(update_fields=['generation_cancel_requested', 'last_generation_error'])
            response_payload = {
                'status': 'canceling',
                'message': get_generation_canceling_message(profile),
                'can_retry': False,
                'redirect_url': origin_url,
            }
            log_generation_event(
                'cancel_marked',
                request=request,
                profile=profile,
                requested_profile_id=profile_id,
                requested_student_id=requested_student_id,
                status='canceling',
                can_retry=False,
                request_id=profile.generation_request_id,
                origin_url=origin_url,
            )
            return json_generation_response(**response_payload)

        if profile.last_generated_session_id and not profile.is_generating:
            RecommendationSession.objects.filter(
                id=profile.last_generated_session_id,
                profile=profile,
            ).delete()
            profile.last_generated_session_id = None
            profile.generation_cancel_requested = True
            profile.last_generation_error = get_generation_cancelled_message(profile)
            profile.save(update_fields=[
                'last_generated_session_id',
                'generation_cancel_requested',
                'last_generation_error',
            ])
            log_generation_event(
                'cancel_discarded_completed_plan',
                request=request,
                profile=profile,
                requested_profile_id=profile_id,
                requested_student_id=requested_student_id,
                status='canceled',
                origin_url=origin_url,
            )
            return json_generation_response(
                'cancelled',
                message=get_generation_cancelled_message(profile),
                can_retry=True,
                redirect_url=origin_url,
            )

        if not profile.is_generating and not profile.generation_cancel_requested:
            return json_generation_response(
                'cancelled',
                message=get_generation_cancelled_message(profile),
                can_retry=True,
                redirect_url=origin_url,
            )

        response_payload = {
            'status': 'cancelled',
            'message': get_generation_cancelled_message(profile),
            'can_retry': True,
            'redirect_url': origin_url,
        }
        log_generation_event(
            'cancel_marked',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            requested_student_id=requested_student_id,
            status='canceled',
            can_retry=response_payload['can_retry'],
            request_id=profile.generation_request_id,
            origin_url=origin_url,
        )

    return json_generation_response(**response_payload)


@login_required
def generate_plan(request, profile_id=None):
    if request.method != 'POST':
        if is_json_request(request):
            log_generation_event(
                'generate_invalid_request',
                request=request,
                requested_profile_id=profile_id,
                status='error',
            )
            return json_generation_response(
                'error',
                http_status=400,
                message='Requisicao invalida para geracao da recomendacao.',
            )
        return redirect('teacher_dashboard' if request.user.is_teacher else 'profile_detail')

    requested_student_id = request.POST.get('aluno_id') or None
    retry_requested = request.POST.get('retry') == '1'

    with transaction.atomic():
        profile = get_profile_for_generation(
            request,
            profile_id=profile_id,
            for_update=True,
        )
        if not profile:
            if is_json_request(request):
                log_generation_event(
                    'generate_profile_not_found',
                    request=request,
                    requested_profile_id=profile_id,
                    requested_student_id=requested_student_id,
                    status='error',
                )
                return json_generation_response(
                    'error',
                    http_status=404,
                    message='O perfil solicitado nao foi encontrado.',
                )
            return redirect('teacher_dashboard' if request.user.is_teacher else 'profile_detail')

        start_url = get_generation_start_url(profile)
        log_generation_event(
            'generate_requested',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            requested_student_id=requested_student_id,
            requested_url=start_url,
            status='requested',
            retry_requested=retry_requested,
        )

        if profile.is_generating:
            if profile.generation_cancel_requested:
                log_generation_event(
                    'generate_blocked_cancellation_finishing',
                    request=request,
                    profile=profile,
                    requested_profile_id=profile_id,
                    requested_student_id=requested_student_id,
                    status='canceling',
                )
                return json_generation_response(
                    'canceling',
                    message=get_cancellation_pending_retry_message(profile),
                    can_retry=False,
                )

            log_generation_event(
                'generate_already_processing',
                request=request,
                profile=profile,
                requested_profile_id=profile_id,
                requested_student_id=requested_student_id,
                status='generating',
            )
            if is_json_request(request):
                return json_generation_response(
                    'processing',
                    status_url=get_generation_status_url(profile),
                    message=get_generation_message(profile),
                )
            messages.info(request, get_generation_message(profile))
            return redirect(get_generation_loading_url(profile))

        if profile.generation_cancel_requested and not retry_requested:
            log_generation_event(
                'generate_blocked_by_preemptive_cancel',
                request=request,
                profile=profile,
                requested_profile_id=profile_id,
                requested_student_id=requested_student_id,
                status='canceled',
            )
            return json_generation_response(
                'cancelled',
                message=get_generation_cancelled_message(profile),
                can_retry=True,
            )

        start_plan_generation(profile, launch_after_commit=True)
        log_generation_event(
            'generate_started',
            request=request,
            profile=profile,
            requested_profile_id=profile_id,
            requested_student_id=requested_student_id,
            requested_url=start_url,
            status='generating',
            retry_requested=retry_requested,
        )

    if is_json_request(request):
        return json_generation_response(
            'processing',
            status_url=get_generation_status_url(profile),
            message=get_generation_message(profile),
        )

    messages.info(request, get_generation_message(profile))
    return redirect(get_generation_loading_url(profile))


@login_required
def plan_detail(request, session_id):
    session = get_accessible_session_or_404(request, session_id)
    prompt = request.session.get('last_prompt')
    profile = session.profile

    feedback_by_resource_id = {
        feedback.resource_id: feedback
        for feedback in session.feedbacks.select_related('resource').all()
    }

    llama_techs = list(session.technologies.filter(ai_model='llama3'))
    mistral_techs = list(session.technologies.filter(ai_model='mistral'))
    for tech in llama_techs + mistral_techs:
        tech.current_feedback = feedback_by_resource_id.get(tech.id)

    return render(request, 'recommendations/plan_detail.html', {
        'session': session,
        'prompt': prompt,
        'llama_techs': llama_techs,
        'mistral_techs': mistral_techs,
        'profile_display_name': profile.display_name,
        'back_url': get_profile_back_url(profile),
        'back_label': f'Voltar para {profile.display_name}' if profile.teacher_id else 'Voltar para o Painel',
        'feedback_history_url': (
            f"{reverse('feedback_history')}?student_id={profile.id}"
            if profile.teacher_id
            else reverse('feedback_history')
        ),
    })


@login_required
def technology_detail(request, tech_id):
    tecnologia = get_object_or_404(
        GeneratedTechnology.objects.select_related('session__profile', 'session__profile__user', 'session__profile__teacher'),
        id=tech_id,
    )
    if not user_can_access_profile(request.user, tecnologia.session.profile):
        raise Http404

    return render(request, 'recommendations/technology_detail.html', {
        'tecnologia': tecnologia,
        'back_url': reverse('plan_detail', args=[tecnologia.session_id]),
    })


@login_required
def feedback_create(request, session_id, item_id):
    session = get_accessible_session_or_404(request, session_id)
    item = get_object_or_404(GeneratedTechnology, id=item_id, session=session)
    existing_feedback = Feedback.objects.filter(session=session, resource=item).first()
    initial_score = existing_feedback.score if existing_feedback else 3
    initial_comment = existing_feedback.user_comment if existing_feedback else ''

    if request.method == 'POST':
        nota = get_feedback_score_value(request.POST.get('score'))
        comentario = request.POST.get('user_comment', '')

        if nota is None:
            submitted_score = get_feedback_score_value(
                request.POST.get('score'),
                fallback=initial_score,
            )
            messages.error(request, 'Informe uma nota valida entre 1 e 5.')
            return render(request, 'recommendations/feedback.html', {
                'session': session,
                'item': item,
                'existing_feedback': existing_feedback,
                'cancel_url': reverse('plan_detail', args=[session.id]),
                'initial_score': submitted_score,
                'initial_comment': comentario,
                'profile_display_name': session.profile.display_name,
            })

        feedback, created = Feedback.objects.update_or_create(
            session=session,
            resource=item,
            defaults={'score': nota, 'user_comment': comentario}
        )
        existing_feedback = feedback
        messages.success(
            request,
            'Feedback salvo com sucesso.'
            if created
            else 'Feedback atualizado com sucesso.',
        )
        return redirect('plan_detail', session_id=session.id)

    return render(request, 'recommendations/feedback.html', {
        'session': session,
        'item': item,
        'existing_feedback': existing_feedback,
        'cancel_url': reverse('plan_detail', args=[session.id]),
        'initial_score': initial_score,
        'initial_comment': initial_comment,
        'profile_display_name': session.profile.display_name,
    })


@login_required
def feedback_history(request):
    feedbacks = (
        Feedback.objects.filter(
            Q(session__profile__user=request.user) | Q(session__profile__teacher=request.user)
        )
        .select_related('resource', 'session__profile', 'session__profile__teacher', 'session__profile__user')
        .order_by('-created_at')
    )
    student_profile = None
    requested_student_id = request.GET.get('student_id')
    search_query = (request.GET.get('q') or '').strip()

    if request.user.is_teacher and requested_student_id:
        student_profile = get_object_or_404(
            BiopsychosocialProfile,
            id=requested_student_id,
            teacher=request.user,
            user__isnull=True,
        )
        feedbacks = feedbacks.filter(session__profile=student_profile)

    if request.user.is_teacher and search_query:
        feedbacks = feedbacks.filter(
            Q(session__profile__student_name__icontains=search_query)
            | Q(session__profile__user__username__icontains=search_query)
            | Q(session__profile__user__first_name__icontains=search_query)
            | Q(session__profile__user__last_name__icontains=search_query)
        )

    history_query = urlencode({
        key: value
        for key, value in {
            'student_id': student_profile.id if student_profile else '',
            'q': search_query if request.user.is_teacher else '',
        }.items()
        if value
    })

    clear_search_url = (
        f"{reverse('feedback_history')}?student_id={student_profile.id}"
        if student_profile
        else reverse('feedback_history')
    )

    return render(request, 'recommendations/feedback_history.html', {
        'feedbacks': feedbacks,
        'student_profile': student_profile,
        'search_query': search_query,
        'history_query': history_query,
        'feedback_count': feedbacks.count(),
        'show_teacher_search': request.user.is_teacher and not student_profile,
        'clear_search_url': clear_search_url,
        'page_title': (
            f'Historico de avaliacoes de {student_profile.display_name}'
            if student_profile
            else 'Historico de Avaliacoes'
        ),
        'page_subtitle': (
            'Veja as avaliacoes registradas para este aluno.'
            if student_profile
            else 'Veja o que voce achou das tecnologias sugeridas.'
        ),
        'back_url': (
            reverse('teacher_student_detail', args=[student_profile.id])
            if student_profile
            else (reverse('teacher_dashboard') if request.user.is_teacher else reverse('profile_detail'))
        ),
    })


@login_required
def feedback_delete(request, feedback_id):
    feedback = get_accessible_feedback_or_404(request, feedback_id)
    if request.method == 'POST':
        feedback.delete()
        messages.success(request, 'Feedback excluido com sucesso.')
    return redirect(get_feedback_history_redirect_url(request, feedback.session.profile))


@login_required
def feedback_edit(request, feedback_id):
    feedback = get_accessible_feedback_or_404(request, feedback_id)
    student_id = None
    requested_student_id = request.POST.get('student_id') or request.GET.get('student_id')
    search_query = (request.POST.get('q') or request.GET.get('q') or '').strip()
    if (
        request.user.is_teacher
        and requested_student_id
        and str(feedback.session.profile_id) == str(requested_student_id)
    ):
        student_id = str(feedback.session.profile_id)

    if request.method == 'POST':
        score = get_feedback_score_value(request.POST.get('score'))
        if score is None:
            messages.error(request, 'Informe uma nota valida entre 1 e 5.')
            return render(request, 'recommendations/feedback_edit.html', {
                'feedback': feedback,
                'student_id': student_id,
                'search_query': search_query,
                'cancel_url': get_feedback_history_redirect_url(request, feedback.session.profile),
            })
        feedback.score = score
        feedback.user_comment = request.POST.get('user_comment', '')
        feedback.save()
        messages.success(request, 'Feedback atualizado com sucesso!')
        return redirect(get_feedback_history_redirect_url(request, feedback.session.profile))

    return render(request, 'recommendations/feedback_edit.html', {
        'feedback': feedback,
        'student_id': student_id,
        'search_query': search_query,
        'cancel_url': get_feedback_history_redirect_url(request, feedback.session.profile),
    })
