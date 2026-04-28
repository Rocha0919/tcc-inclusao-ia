import time

from django.db import transaction

from apps.recommendations.models import GeneratedTechnology, RecommendationSession
from ai_engine.llm_client import LLMClient
from ai_engine.prompt_builder import PromptBuilder


class GenerationCancelled(Exception):
    pass


def ensure_not_cancelled(should_cancel):
    if should_cancel and should_cancel():
        raise GenerationCancelled


def cancellable_sleep(seconds, should_cancel):
    for _ in range(seconds * 10):
        ensure_not_cancelled(should_cancel)
        time.sleep(0.1)


def criar_plano_para_usuario(profile, should_cancel=None):
    prompt = PromptBuilder.build_final_prompt(profile)

    resposta_llama = None
    resposta_mistral = None

    try:
        ensure_not_cancelled(should_cancel)
        resposta_llama = LLMClient.gerar_recomendacao(prompt, model_name="llama3")

        ensure_not_cancelled(should_cancel)
        cancellable_sleep(3, should_cancel)
        ensure_not_cancelled(should_cancel)

        resposta_mistral = LLMClient.gerar_recomendacao(prompt, model_name="mistral")
        ensure_not_cancelled(should_cancel)
    except GenerationCancelled:
        raise
    except Exception as error:
        print(f"Erro durante a geracao: {error}")

    if not resposta_llama and not resposta_mistral:
        return None

    just_llama = (
        resposta_llama.get("justificativa_geral", "Sem retorno.")
        if resposta_llama
        else "Llama 3 indisponivel no momento."
    )
    just_mistral = (
        resposta_mistral.get("justificativa_geral", "Sem retorno.")
        if resposta_mistral
        else "Mistral indisponivel no momento."
    )
    justificativa_combinada = (
        f"### Analise Llama 3\n{just_llama}\n\n### Analise Mistral\n{just_mistral}"
    )

    def salvar_tecnologias(session, resposta, modelo_id):
        if resposta and "tecnologias" in resposta:
            for tech in resposta["tecnologias"]:
                ensure_not_cancelled(should_cancel)
                GeneratedTechnology.objects.create(
                    session=session,
                    ai_model=modelo_id,
                    name=tech.get("nome", "Tecnologia sugerida"),
                    what_is_it=tech.get("o_que_e", ""),
                    purpose=tech.get("para_que_serve", ""),
                    justification=tech.get("justificativa_usuario", ""),
                    video_search_term=tech.get("termo_youtube", ""),
                )

    with transaction.atomic():
        ensure_not_cancelled(should_cancel)
        session = RecommendationSession.objects.create(
            profile=profile,
            justificativa_geral=justificativa_combinada,
        )
        salvar_tecnologias(session, resposta_llama, "llama3")
        salvar_tecnologias(session, resposta_mistral, "mistral")

    return session, prompt
