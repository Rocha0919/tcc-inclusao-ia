from apps.recommendations.models import RecommendationSession, GeneratedTechnology
from ai_engine.prompt_builder import PromptBuilder
from ai_engine.llm_client import LLMClient
import requests
import re

def buscar_video_youtube(termo):
    # Codifica o termo para evitar erros de caracteres especiais (espaços, acentos)
    from urllib.parse import quote
    termo_encoded = quote(termo)
    
    url = f"https://www.youtube.com/results?search_query={termo_encoded}"
    
    # Headers mais completos para parecer um navegador real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Erro HTTP {response.status_code}")
            return None

        # O regex precisa ser flexível, as vezes o YouTube usa aspas simples ou espaços
        matches = re.findall(r'"videoId"\s*:\s*"(.*?)"', response.text)

        if matches:
            # Pegamos o primeiro resultado que não seja de anúncio (geralmente os primeiros)
            video_id = matches[0]
            return f"https://www.youtube.com/embed/{video_id}"
            
    except Exception as e:
        print(f"Erro na busca: {e}")
        return None

    return None

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
            video_id = buscar_video_youtube(tech.get("termo_youtube", ""))

            GeneratedTechnology.objects.create(
                session=session,
                ai_model="llama3", # Identificador
                name=tech.get("nome", "Tecnologia sugerida"),
                what_is_it=tech.get("o_que_e", ""),
                purpose=tech.get("para_que_serve", ""),
                justification=tech.get("justificativa_usuario", ""),
                video_search_term=tech.get("termo_youtube", ""),
                video_id=video_id  
            )
            
    # Salva as tecnologias do Mistral
    if resposta_mistral:
        for tech in resposta_mistral.get("tecnologias", []):
            video_id = buscar_video_youtube(tech.get("termo_youtube", ""))

            GeneratedTechnology.objects.create(
                session=session,
                ai_model="mistral", # Identificador
                name=tech.get("nome", "Tecnologia sugerida"),
                what_is_it=tech.get("o_que_e", ""),
                purpose=tech.get("para_que_serve", ""),
                justification=tech.get("justificativa_usuario", ""),
                video_search_term=tech.get("termo_youtube", ""),
                video_id=video_id  
            )
            
    return session, prompt