import re
import time
import unicodedata

from django.db import transaction

from apps.recommendations.models import GeneratedTechnology, RecommendationSession
from ai_engine.llm_client import LLMClient
from ai_engine.prompt_builder import PromptBuilder

MAX_TECHNOLOGIES_PER_MODEL = 3


class GenerationCancelled(Exception):
    pass


def ensure_not_cancelled(should_cancel):
    if should_cancel and should_cancel():
        raise GenerationCancelled


def cancellable_sleep(seconds, should_cancel):
    for _ in range(seconds * 10):
        ensure_not_cancelled(should_cancel)
        time.sleep(0.1)


def normalize_technology_name(name):
    if not isinstance(name, str):
        return ''

    normalized = unicodedata.normalize('NFKD', name)
    normalized = ''.join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = normalized.lower()
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


def clean_response_text(value, fallback=''):
    if value is None:
        return fallback

    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or fallback


def get_reference_lookup(category):
    reference_lookup = set()

    for technology_name in PromptBuilder.get_filtered_technologies(category):
        normalized_name = normalize_technology_name(technology_name)
        if normalized_name:
            reference_lookup.add(normalized_name)

    return reference_lookup


def normalize_recommendation_response(response, category):
    if not isinstance(response, dict):
        return None

    normalized_response = {
        'justificativa_geral': clean_response_text(
            response.get('justificativa_geral'),
            'Sem retorno.',
        ),
        'tecnologias': [],
    }

    raw_technologies = response.get('tecnologias')
    if not isinstance(raw_technologies, list):
        return normalized_response

    seen_names = set()
    reference_lookup = get_reference_lookup(category)

    for technology in raw_technologies:
        if not isinstance(technology, dict):
            continue

        technology_name = clean_response_text(technology.get('nome'))
        normalized_name = normalize_technology_name(technology_name)

        if not normalized_name or normalized_name in seen_names:
            continue

        seen_names.add(normalized_name)
        normalized_response['tecnologias'].append({
            'nome': technology_name,
            'o_que_e': clean_response_text(technology.get('o_que_e')),
            'para_que_serve': clean_response_text(technology.get('para_que_serve')),
            'justificativa_usuario': clean_response_text(technology.get('justificativa_usuario')),
            'termo_youtube': clean_response_text(
                technology.get('termo_youtube'),
                technology_name,
            ),
            'origem_recomendacao': (
                GeneratedTechnology.SOURCE_JSON_REFERENCE
                if normalized_name in reference_lookup
                else GeneratedTechnology.SOURCE_AI_SUGGESTED
            ),
        })

        if len(normalized_response['tecnologias']) >= MAX_TECHNOLOGIES_PER_MODEL:
            break

    return normalized_response


def criar_plano_para_usuario(profile, should_cancel=None):
    prompt = PromptBuilder.build_final_prompt(profile)

    resposta_llama = None
    resposta_mistral = None
    category = profile.primary_disability_category

    try:
        ensure_not_cancelled(should_cancel)
        resposta_llama = normalize_recommendation_response(
            LLMClient.gerar_recomendacao(prompt, model_name="llama3"),
            category,
        )

        ensure_not_cancelled(should_cancel)
        cancellable_sleep(3, should_cancel)
        ensure_not_cancelled(should_cancel)

        resposta_mistral = normalize_recommendation_response(
            LLMClient.gerar_recomendacao(prompt, model_name="mistral"),
            category,
        )
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
            for technology in resposta["tecnologias"]:
                ensure_not_cancelled(should_cancel)
                GeneratedTechnology.objects.create(
                    session=session,
                    ai_model=modelo_id,
                    name=technology.get("nome", "Tecnologia sugerida"),
                    what_is_it=technology.get("o_que_e", ""),
                    purpose=technology.get("para_que_serve", ""),
                    justification=technology.get("justificativa_usuario", ""),
                    video_search_term=technology.get("termo_youtube", ""),
                    recommendation_source=technology.get(
                        "origem_recomendacao",
                        GeneratedTechnology.SOURCE_UNKNOWN,
                    ),
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
