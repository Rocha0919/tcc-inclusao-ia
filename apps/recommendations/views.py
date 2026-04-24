from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.recommendations.models import GeneratedTechnology, RecommendationSession, Feedback
from ai_engine.service import criar_plano_para_usuario
import threading

@login_required
def generate_plan(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or request.method != 'POST':
        return redirect('profile_detail')

    if profile.is_generating:
        return redirect('profile_detail')

    profile.is_generating = True
    profile.save()

    # Limpamos qualquer ID antigo da sessão de mensagens para evitar conflitos
    request.session['pending_plan_id'] = None 

    def tarefa_ia():
        try:
            # Sua função criar_plano_para_usuario deve retornar a 'session' criada
            resultado = criar_plano_para_usuario(profile)
            if resultado:
                session, prompt = resultado
                # Guardamos o ID no banco/perfil para o front-end saber que acabou
                profile.last_generated_session_id = session.id
        except Exception as e:
            print(f"Erro na IA: {e}")
        finally:
            profile.is_generating = False
            profile.save()

    threading.Thread(target=tarefa_ia).start()
    
    messages.info(request, 'Processando seu plano personalizado...')
    return redirect('profile_detail')

@login_required
def plan_detail(request, session_id):
    session = get_object_or_404(RecommendationSession, id=session_id, profile__user=request.user)
    prompt = request.session.get('last_prompt')
    
    # Separa as tecnologias geradas por modelo
    llama_techs = session.technologies.filter(ai_model='llama3')
    mistral_techs = session.technologies.filter(ai_model='mistral')
    
    return render(request, 'recommendations/plan_detail.html', {
        'session': session,
        'prompt': prompt,
        'llama_techs': llama_techs,
        'mistral_techs': mistral_techs
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