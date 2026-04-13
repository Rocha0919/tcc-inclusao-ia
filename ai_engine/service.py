from apps.recommendations.models import RecommendationSession, GeneratedTechnology
from ai_engine.prompt_builder import PromptBuilder
from ai_engine.llm_client import LLMClient


def criar_plano_para_usuario(profile):
    prompt = PromptBuilder.build_final_prompt(profile)
    resposta_ia = LLMClient.gerar_recomendacao(prompt)
    
    if not resposta_ia:
        return None
        
    justificativa_geral = resposta_ia.get("justificativa_geral", "")
    tecnologias = resposta_ia.get("tecnologias", [])
    
    # Cria a sessão
    session = RecommendationSession.objects.create(
        profile=profile,
        justificativa_geral=justificativa_geral
    )
    
    # Salva cada tecnologia gerada pela IA
    for tech in tecnologias:
        GeneratedTechnology.objects.create(
            session=session,
            name=tech.get("nome", "Tecnologia sugerida"),
            what_is_it=tech.get("o_que_e", ""),
            purpose=tech.get("para_que_serve", ""),
            justification=tech.get("justificativa_usuario", ""),
            video_search_term=tech.get("termo_youtube", "")
        )
            
    return session, prompt