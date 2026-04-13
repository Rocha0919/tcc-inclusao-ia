from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.recommendations.models import GeneratedTechnology, RecommendationSession, Feedback
from ai_engine.service import criar_plano_para_usuario

@login_required
def generate_plan(request):
    profile = getattr(request.user, 'profile', None)
    
    if not profile:
        messages.warning(request, 'Crie seu perfil antes de gerar um plano.')
        return redirect('profile_create')
    
    resultado = criar_plano_para_usuario(profile)

    if not resultado:
        messages.error(request, 'Erro ao gerar o plano. O servidor de IA está offline?')
        return redirect('profile_detail')
    
    session, prompt = resultado

    request.session['last_prompt'] = prompt

    messages.success(request, 'Plano de Acessibilidade gerado com sucesso pela IA!')
    
    return redirect('plan_detail', session_id=session.id)

@login_required
def plan_detail(request, session_id):
    session = get_object_or_404(RecommendationSession, id=session_id, profile__user=request.user)
    
    prompt = request.session.get('last_prompt')
    
    return render(request, 'recommendations/plan_detail.html', {
        'session': session,
        'prompt': prompt
    })

def technology_detail(request, tech_id):
    # Busca a tecnologia ou retorna 404 se não existir
    tecnologia = get_object_or_404(GeneratedTechnology, id=tech_id)
    
    return render(request, 'recommendations/technology_detail.html', {
        'tecnologia': tecnologia
    })

@login_required
def feedback_create(request, session_id, item_id):
    session = get_object_or_404(RecommendationSession, id=session_id, profile__user=request.user)
    item = get_object_or_404(GeneratedTechnology, id=item_id)
    
    if request.method == 'POST':
        nota = request.POST.get('score')
        comentario = request.POST.get('user_comment', '')
        
        Feedback.objects.update_or_create(
            session=session,
            resource=item,
            defaults={'score': nota, 'user_comment': comentario}
        )
        messages.success(request, 'Obrigado pelo feedback! Isso ajuda a IA a melhorar.')
        return redirect('plan_detail', session_id=session.id)
        
    return render(request, 'recommendations/feedback.html', {'session': session, 'item': item})

@login_required
def feedback_history(request):
    feedbacks = Feedback.objects.filter(session__profile__user=request.user).order_by('-created_at')
    return render(request, 'recommendations/feedback_history.html', {'feedbacks': feedbacks})

@login_required
def feedback_delete(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id, session__profile__user=request.user)
    if request.method == 'POST':
        feedback.delete()
        messages.success(request, 'Feedback excluído com sucesso.')
    return redirect('feedback_history')

@login_required
def feedback_edit(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id, session__profile__user=request.user)
    if request.method == 'POST':
        feedback.score = request.POST.get('score')
        feedback.user_comment = request.POST.get('user_comment', '')
        feedback.save()
        messages.success(request, 'Feedback atualizado com sucesso!')
        return redirect('feedback_history')
        
    return render(request, 'recommendations/feedback_edit.html', {'feedback': feedback})