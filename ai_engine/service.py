from apps.recommendations.models import RecommendationSession, GeneratedTechnology
from ai_engine.prompt_builder import PromptBuilder
from ai_engine.llm_client import LLMClient

def criar_plano_para_usuario(profile):
    prompt = PromptBuilder.build_final_prompt(profile)
    
    # Dispara a requisição para as duas IAs
    resposta_llama = LLMClient.gerar_recomendacao(prompt, model_name="llama3")
    resposta_mistral = LLMClient.gerar_recomendacao(prompt, model_name="mistral")
    
    if not resposta_llama and not resposta_mistral:
        return None # Falhou em ambas
        
    # Combina a justificativa geral das duas IAs
    just_llama = resposta_llama.get("justificativa_geral", "Sem justificativa.") if resposta_llama else "Llama falhou."
    just_mistral = resposta_mistral.get("justificativa_geral", "Sem justificativa.") if resposta_mistral else "Mistral falhou."
    
    justificativa_combinada = f"**Análise Llama 3:**\n{just_llama}\n\n**Análise Mistral:**\n{just_mistral}"
    
    # Cria a sessão
    session = RecommendationSession.objects.create(
        profile=profile,
        justificativa_geral=justificativa_combinada
    )
    
    # Salva as tecnologias do Llama 3
    if resposta_llama:
        for tech in resposta_llama.get("tecnologias", []):
            GeneratedTechnology.objects.create(
                session=session,
                ai_model="llama3", # Identificador
                name=tech.get("nome", "Tecnologia sugerida"),
                what_is_it=tech.get("o_que_e", ""),
                purpose=tech.get("para_que_serve", ""),
                justification=tech.get("justificativa_usuario", ""),
                video_search_term=tech.get("termo_youtube", "")
            )
            
    # Salva as tecnologias do Mistral
    if resposta_mistral:
        for tech in resposta_mistral.get("tecnologias", []):
            GeneratedTechnology.objects.create(
                session=session,
                ai_model="mistral", # Identificador
                name=tech.get("nome", "Tecnologia sugerida"),
                what_is_it=tech.get("o_que_e", ""),
                purpose=tech.get("para_que_serve", ""),
                justification=tech.get("justificativa_usuario", ""),
                video_search_term=tech.get("termo_youtube", "")
            )
            
    return session, prompt