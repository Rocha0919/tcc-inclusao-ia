import time
from apps.recommendations.models import RecommendationSession, GeneratedTechnology
from ai_engine.prompt_builder import PromptBuilder
from ai_engine.llm_client import LLMClient
import requests
import re

def criar_plano_para_usuario(profile):
    prompt = PromptBuilder.build_final_prompt(profile)
    
    # Inicializamos como None
    resposta_llama = None
    resposta_mistral = None

    try:
        # 1. Chama Llama 3
        resposta_llama = LLMClient.gerar_recomendacao(prompt, model_name="llama3")
        
        # 2. Pequena pausa para o Ollama descarregar o Llama 3 e preparar o Mistral
        time.sleep(3) 
        
        # 3. Chama Mistral
        resposta_mistral = LLMClient.gerar_recomendacao(prompt, model_name="mistral")
    except Exception as e:
        print(f"❌ Erro durante a geração: {e}")

    # Só prossegue se ao menos UM deles funcionou
    if not resposta_llama and not resposta_mistral:
        return None

    # Ajuste na justificativa para evitar erros de None.get()
    just_llama = resposta_llama.get("justificativa_geral", "Sem retorno.") if resposta_llama else "Llama 3 indisponível no momento."
    just_mistral = resposta_mistral.get("justificativa_geral", "Sem retorno.") if resposta_mistral else "Mistral indisponível no momento."
    
    justificativa_combinada = f"### Análise Llama 3\n{just_llama}\n\n### Análise Mistral\n{just_mistral}"
    
    session = RecommendationSession.objects.create(
        profile=profile,
        justificativa_geral=justificativa_combinada
    )

    # Função auxiliar para evitar repetição de código
    def salvar_tecnologias(resposta, modelo_id):
        if resposta and "tecnologias" in resposta:
            for tech in resposta["tecnologias"]:
                GeneratedTechnology.objects.create(
                    session=session,
                    ai_model=modelo_id,
                    name=tech.get("nome", "Tecnologia sugerida"),
                    what_is_it=tech.get("o_que_e", ""),
                    purpose=tech.get("para_que_serve", ""),
                    justification=tech.get("justificativa_usuario", ""),
                    video_search_term=tech.get("termo_youtube", ""),
                )

    salvar_tecnologias(resposta_llama, "llama3")
    salvar_tecnologias(resposta_mistral, "mistral")
            
    return session, prompt