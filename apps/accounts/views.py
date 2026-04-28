from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import BiopsychosocialProfile

from .forms import CustomUserCreationForm


def build_profile_dynamic_data(source):
    return {
        "biologico": {
            "limitacoes_especificas": source.get('limitacoes_especificas', 'Nenhuma declarada'),
            "grau_severidade": source.get('grau_severidade', 'Não informado')
        },
        "psicologico": {
            "estilo_aprendizado": source.get('estilo_aprendizado', 'Não informado'),
            "barreiras_cognitivas": source.get('barreiras_cognitivas', 'Nenhuma declarada')
        },
        "social": {
            "objetivo_principal": source.get('objetivo_principal', ''),
            "barreiras_dia_a_dia": source.get('barreiras', ''),
            "orcamento": source.get('orcamento', 'gratuito')
        },
        "tecnologico": {
            "dispositivos_disponiveis": source.get('dispositivos', 'Não informado'),
            "nivel_tecnologico": source.get('nivel_tecnologico', ''),
            "ferramentas_previas": source.get('ferramentas_previas', 'Nenhuma')
        }
    }


def build_profile_sections(profile):
    dados = profile.dynamic_data or {}
    return {
        'categoria_atual': profile.primary_disability_category,
        'biologico': dados.get('biologico', {}),
        'psicologico': dados.get('psicologico', {}),
        'social': dados.get('social', {}),
        'tecnologico': dados.get('tecnologico', {})
    }


def build_profile_form_values(source=None, profile=None):
    if profile is not None:
        dados = profile.dynamic_data or {}
        biologico = dados.get('biologico', {})
        psicologico = dados.get('psicologico', {})
        social = dados.get('social', {})
        tecnologico = dados.get('tecnologico', {})
        return {
            'student_name': profile.student_name,
            'primary_disability_category': profile.primary_disability_category,
            'grau_severidade': biologico.get('grau_severidade', ''),
            'limitacoes_especificas': biologico.get('limitacoes_especificas', ''),
            'estilo_aprendizado': psicologico.get('estilo_aprendizado', ''),
            'barreiras_cognitivas': psicologico.get('barreiras_cognitivas', ''),
            'objetivo_principal': social.get('objetivo_principal', ''),
            'barreiras': social.get('barreiras_dia_a_dia', ''),
            'orcamento': social.get('orcamento', 'gratuito'),
            'dispositivos': tecnologico.get('dispositivos_disponiveis', ''),
            'nivel_tecnologico': tecnologico.get('nivel_tecnologico', ''),
            'ferramentas_previas': tecnologico.get('ferramentas_previas', ''),
        }

    source = source or {}
    return {
        'student_name': source.get('student_name', ''),
        'primary_disability_category': source.get('primary_disability_category', source.get('categoria_deficiencia', '')),
        'grau_severidade': source.get('grau_severidade', ''),
        'limitacoes_especificas': source.get('limitacoes_especificas', ''),
        'estilo_aprendizado': source.get('estilo_aprendizado', ''),
        'barreiras_cognitivas': source.get('barreiras_cognitivas', ''),
        'objetivo_principal': source.get('objetivo_principal', ''),
        'barreiras': source.get('barreiras', ''),
        'orcamento': source.get('orcamento', 'gratuito'),
        'dispositivos': source.get('dispositivos', ''),
        'nivel_tecnologico': source.get('nivel_tecnologico', ''),
        'ferramentas_previas': source.get('ferramentas_previas', ''),
    }


def get_dashboard_redirect_name(user):
    return 'teacher_dashboard' if user.is_teacher else 'profile_detail'


def teacher_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_teacher:
            messages.error(request, 'Apenas professores podem acessar o painel de alunos.')
            return redirect('profile_detail')
        return view_func(request, *args, **kwargs)

    return wrapped


def get_teacher_student_or_404(request, student_id):
    if not request.user.is_teacher:
        raise Http404
    return get_object_or_404(
        BiopsychosocialProfile,
        id=student_id,
        teacher=request.user,
        user__isnull=True,
    )

def home(request):
    return render(request, 'home.html')

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST) 
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(get_dashboard_redirect_name(user))
    else:
        form = CustomUserCreationForm() 
        
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def profile_create(request):
    if request.method == 'POST':
        categoria_principal = request.POST.get('primary_disability_category')
        
        # Estruturando o Mapeamento Biopsicossocial Completo
        mapeamento_json = {
            "biologico": {
                "limitacoes_especificas": request.POST.get('limitacoes_especificas', 'Nenhuma declarada'),
                "grau_severidade": request.POST.get('grau_severidade', 'Não informado')
            },
            "psicologico": {
                "estilo_aprendizado": request.POST.get('estilo_aprendizado', 'Não informado'),
                "barreiras_cognitivas": request.POST.get('barreiras_cognitivas', 'Nenhuma declarada')
            },
            "social": {
                "objetivo_principal": request.POST.get('objetivo_principal'),
                "barreiras_dia_a_dia": request.POST.get('barreiras'),
                "orcamento": request.POST.get('orcamento', 'gratuito')
            },
            "tecnologico": {
                "dispositivos_disponiveis": request.POST.get('dispositivos', 'Não informado'),
                "nivel_tecnologico": request.POST.get('nivel_tecnologico'),
                "ferramentas_previas": request.POST.get('ferramentas_previas', 'Nenhuma')
            }
        }

        perfil, created = BiopsychosocialProfile.objects.update_or_create(
            user=request.user,
            defaults={
                'primary_disability_category': categoria_principal,
                'dynamic_data': mapeamento_json
            }
        )

        messages.success(request, 'Seu perfil biopsicossocial foi mapeado com sucesso!')
        return redirect('profile_detail')

    categorias = BiopsychosocialProfile.DISABILITY_CHOICES
    return render(request, 'accounts/profile_create.html', {'categorias': categorias})

def profile_detail(request):
    # Se NÃO estiver logado, mostra a tela de convite (landing page)
    if not request.user.is_authenticated:
        return render(request, 'accounts/recomendações_anonimo.html')

    # Se estiver logado, segue a lógica normal
    profile = getattr(request.user, 'profile', None)
    if not profile:
        return redirect('profile_create')
        
    sessoes_passadas = profile.recommendationsession_set.all().order_by('-created_at')
    return render(request, 'accounts/profile_detail.html', {
        'profile': profile,
        'sessoes': sessoes_passadas
    })

@login_required
def profile_view(request):
    try:
        profile = BiopsychosocialProfile.objects.get(user=request.user)
    except BiopsychosocialProfile.DoesNotExist:
        # Se não existe perfil, manda configurar primeiro
        return redirect('profile_create')
    
    dados = profile.dynamic_data or {}
    context = {
        'usuario': request.user,
        'categoria_atual': profile.primary_disability_category,
        'biologico': dados.get('biologico', {}),
        'psicologico': dados.get('psicologico', {}), # Adicionado
        'social': dados.get('social', {}),           # Adicionado (substitui o antigo perfil_uso)
        'tecnologico': dados.get('tecnologico', {})
    }
    return render(request, 'accounts/profile_view.html', context)

@login_required
def profile_edit(request):
    # Pega o perfil do usuário logado (ou cria um vazio se por algum motivo não existir)
    profile, created = BiopsychosocialProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # 1. Atualiza a deficiência principal
        profile.primary_disability_category = request.POST.get('categoria_deficiencia')
        
        # 2. Reconstrói o JSON com as informações atualizadas do Mapeamento Biopsicossocial Completo
        profile.dynamic_data = {
            "biologico": {
                "limitacoes_especificas": request.POST.get('limitacoes_especificas', ''),
                "grau_severidade": request.POST.get('grau_severidade', 'Não informado')
            },
            "psicologico": {
                "estilo_aprendizado": request.POST.get('estilo_aprendizado', 'Não informado'),
                "barreiras_cognitivas": request.POST.get('barreiras_cognitivas', 'Nenhuma declarada')
            },
            "social": {
                "objetivo_principal": request.POST.get('objetivo_principal', ''),
                "barreiras_dia_a_dia": request.POST.get('barreiras', ''),
                "orcamento": request.POST.get('orcamento', 'gratuito')
            },
            "tecnologico": {
                "dispositivos_disponiveis": request.POST.get('dispositivos', 'Não informado'),
                "nivel_tecnologico": request.POST.get('nivel_tecnologico', ''),
                "ferramentas_previas": request.POST.get('ferramentas_previas', '')
            }
        }
        profile.save()
        
        # Redireciona para o painel principal ou página de sucesso após salvar
        return redirect('profile_view') 
        
    # Se for GET, extraímos os dados do JSON para preencher o formulário
    dados = profile.dynamic_data or {}
    
    context = {
        'categoria_atual': profile.primary_disability_category,
        'biologico': dados.get('biologico', {}),
        'psicologico': dados.get('psicologico', {}), # Adicionado
        'social': dados.get('social', {}),           # Adicionado
        'tecnologico': dados.get('tecnologico', {})
    }
    
    return render(request, 'accounts/profile_edit.html', context)


@login_required
def profile_create(request):
    if request.user.is_teacher:
        return redirect('teacher_dashboard')

    if request.method == 'POST':
        categoria_principal = request.POST.get('primary_disability_category')

        BiopsychosocialProfile.objects.update_or_create(
            user=request.user,
            defaults={
                'teacher': None,
                'student_name': '',
                'primary_disability_category': categoria_principal,
                'dynamic_data': build_profile_dynamic_data(request.POST),
            }
        )

        messages.success(request, 'Seu perfil biopsicossocial foi mapeado com sucesso!')
        return redirect('profile_detail')

    categorias = BiopsychosocialProfile.DISABILITY_CHOICES
    return render(request, 'accounts/profile_create.html', {'categorias': categorias})


def profile_detail(request):
    if not request.user.is_authenticated:
        return render(request, 'accounts/recomendações_anonimo.html')

    if request.user.is_teacher:
        return redirect('teacher_dashboard')

    profile = getattr(request.user, 'profile', None)
    if not profile:
        return redirect('profile_create')

    sessoes_passadas = profile.recommendationsession_set.all().order_by('-created_at')
    return render(request, 'accounts/profile_detail.html', {
        'profile': profile,
        'sessoes': sessoes_passadas
    })


@login_required
def profile_view(request):
    if request.user.is_teacher:
        return redirect('teacher_dashboard')

    try:
        profile = BiopsychosocialProfile.objects.get(user=request.user)
    except BiopsychosocialProfile.DoesNotExist:
        return redirect('profile_create')

    context = build_profile_sections(profile)
    context['usuario'] = request.user
    return render(request, 'accounts/profile_view.html', context)


@login_required
def profile_edit(request):
    if request.user.is_teacher:
        return redirect('teacher_dashboard')

    profile, _ = BiopsychosocialProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile.primary_disability_category = request.POST.get('categoria_deficiencia')
        profile.teacher = None
        profile.student_name = ''
        profile.dynamic_data = build_profile_dynamic_data(request.POST)
        profile.save()
        return redirect('profile_view')

    context = build_profile_sections(profile)
    return render(request, 'accounts/profile_edit.html', context)


@login_required
@teacher_required
def teacher_dashboard(request):
    students = (
        BiopsychosocialProfile.objects.filter(teacher=request.user, user__isnull=True)
        .annotate(
            total_sessions=Count('recommendationsession'),
            last_session_at=Max('recommendationsession__created_at'),
        )
        .order_by('student_name', 'created_at')
    )
    return render(request, 'accounts/teacher_dashboard.html', {'students': students})


@login_required
@teacher_required
def teacher_student_create(request):
    form_values = build_profile_form_values()

    if request.method == 'POST':
        form_values = build_profile_form_values(request.POST)
        student_name = request.POST.get('student_name', '').strip()
        categoria_principal = request.POST.get('primary_disability_category')

        if not student_name:
            messages.error(request, 'Informe o nome do aluno para continuar.')
        elif not categoria_principal:
            messages.error(request, 'Selecione a categoria principal do aluno.')
        else:
            student_profile = BiopsychosocialProfile.objects.create(
                teacher=request.user,
                student_name=student_name,
                primary_disability_category=categoria_principal,
                dynamic_data=build_profile_dynamic_data(request.POST),
                is_generating=False,
                generation_cancel_requested=False,
                last_generated_session_id=None,
                last_generation_error='',
            )
            messages.success(request, 'Aluno cadastrado com sucesso.')
            return redirect('teacher_student_detail', student_id=student_profile.id)

    return render(request, 'accounts/teacher_student_form.html', {
        'categorias': BiopsychosocialProfile.DISABILITY_CHOICES,
        'form_values': form_values,
        'page_title': 'Cadastrar aluno',
        'submit_label': 'Salvar aluno',
        'is_editing': False,
    })


@login_required
@teacher_required
def teacher_student_detail(request, student_id):
    student_profile = get_teacher_student_or_404(request, student_id)
    context = build_profile_sections(student_profile)
    context.update({
        'student_profile': student_profile,
        'sessoes': student_profile.recommendationsession_set.all().order_by('-created_at'),
    })
    return render(request, 'accounts/teacher_student_detail.html', context)


@login_required
@teacher_required
def teacher_student_edit(request, student_id):
    student_profile = get_teacher_student_or_404(request, student_id)
    form_values = build_profile_form_values(profile=student_profile)

    if request.method == 'POST':
        form_values = build_profile_form_values(request.POST)
        student_name = request.POST.get('student_name', '').strip()
        categoria_principal = request.POST.get('primary_disability_category')

        if not student_name:
            messages.error(request, 'Informe o nome do aluno para continuar.')
        elif not categoria_principal:
            messages.error(request, 'Selecione a categoria principal do aluno.')
        else:
            student_profile.student_name = student_name
            student_profile.primary_disability_category = categoria_principal
            student_profile.dynamic_data = build_profile_dynamic_data(request.POST)
            student_profile.save()
            messages.success(request, 'Perfil do aluno atualizado com sucesso.')
            return redirect('teacher_student_detail', student_id=student_profile.id)

    return render(request, 'accounts/teacher_student_form.html', {
        'categorias': BiopsychosocialProfile.DISABILITY_CHOICES,
        'form_values': form_values,
        'student_profile': student_profile,
        'page_title': f'Editar {student_profile.display_name}',
        'submit_label': 'Salvar alterações',
        'is_editing': True,
    })


@login_required
@teacher_required
def teacher_student_delete(request, student_id):
    student_profile = get_teacher_student_or_404(request, student_id)

    if request.method == 'POST':
        student_name = student_profile.display_name
        student_profile.delete()
        messages.success(request, f'Aluno "{student_name}" removido com sucesso.')
        return redirect('teacher_dashboard')

    return render(request, 'accounts/teacher_student_confirm_delete.html', {
        'student_profile': student_profile,
    })
