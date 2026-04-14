from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from apps.accounts.models import BiopsychosocialProfile
from .forms import CustomUserCreationForm

def home(request):
    return render(request, 'home.html')

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST) 
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('profile_create')
    else:
        form = CustomUserCreationForm() 
        
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def profile_create(request):
    if request.method == 'POST':
        categoria_principal = request.POST.get('primary_disability_category')
        
        mapeamento_json = {
            "biologico": {
                "limitacoes_especificas": request.POST.get('limitacoes_especificas', 'Nenhuma declarada')
            },
            "perfil_uso": {
                "objetivo_principal": request.POST.get('objetivo_principal'),
                "barreiras_dia_a_dia": request.POST.get('barreiras')
            },
            "tecnologico": {
                "nivel_tecnologico": request.POST.get('nivel_tecnologico'),
                "ferramentas_previas": request.POST.get('ferramentas_previas')
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

@login_required
def profile_detail(request):
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
        'perfil_uso': dados.get('perfil_uso', {}),
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
        
        # 2. Reconstrói o JSON com as informações atualizadas
        profile.dynamic_data = {
            "biologico": {
                "limitacoes_especificas": request.POST.get('limitacoes_especificas', '')
            },
            "perfil_uso": {
                "objetivo_principal": request.POST.get('objetivo_principal', ''),
                "barreiras_dia_a_dia": request.POST.get('barreiras', '')
            },
            "tecnologico": {
                "nivel_tecnologico": request.POST.get('nivel_tecnologico', ''),
                "ferramentas_previas": request.POST.get('ferramentas_previas', '')
            }
        }
        profile.save()
        
        # Redireciona para o painel principal ou página de sucesso após salvar
        return redirect('profile_view') # Mude para o nome da url da sua página principal
        
    # Se for GET, extraímos os dados do JSON para preencher o formulário
    dados = profile.dynamic_data or {}
    
    context = {
        'categoria_atual': profile.primary_disability_category,
        'biologico': dados.get('biologico', {}),
        'perfil_uso': dados.get('perfil_uso', {}),
        'tecnologico': dados.get('tecnologico', {})
    }
    
    return render(request, 'accounts/profile_edit.html', context)
