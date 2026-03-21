from apps.recommendations.models import RecommendationSession, RecommendedItem
from apps.catalog.models import ResourceItem
from ai_engine.prompt_builder import PromptBuilder
from ai_engine.llm_client import LLMClient

def criar_plano_para_usuario(profile):
    prompt = PromptBuilder.build_final_prompt(profile)
    resposta_ia = LLMClient.gerar_recomendacao(prompt)
    
    if not resposta_ia:
        return None
        
    justificativa_geral = resposta_ia.get("justificativa_geral", "")
    itens_selecionados = resposta_ia.get("itens_selecionados", [])
    
    session = RecommendationSession.objects.create(
        profile=profile,
        ai_rationale=justificativa_geral,
        context_snapshot=profile.dynamic_data
    )
    
    # Salva cada item junto com sua justificativa
    for item_ia in itens_selecionados:
        try:
            recurso = ResourceItem.objects.get(id=item_ia.get("id"))
            RecommendedItem.objects.create(
                session=session,
                resource=recurso,
                ai_justification=item_ia.get("justificativa", "Recomendado pela IA.")
            )
        except ResourceItem.DoesNotExist:
            continue # Ignora se a IA inventar um ID que não existe
            
    return session