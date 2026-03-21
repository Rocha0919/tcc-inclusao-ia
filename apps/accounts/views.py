from django.shortcuts import render, redirect
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
        
    sessoes_passadas = profile.recommendation_sessions.all().order_by('-created_at')
    return render(request, 'accounts/profile_detail.html', {
        'profile': profile,
        'sessoes': sessoes_passadas
    })
