import json
import os

from django.conf import settings

from apps.recommendations.models import Feedback


class PromptBuilder:

    @staticmethod
    def get_filtered_technologies(category):
        path = os.path.join(settings.BASE_DIR, 'data', 'tecnologias.json')
        try:
            with open(path, 'r', encoding='utf-8') as file:
                full_data = json.load(file)
                return full_data.get(category, [])
        except Exception as error:
            print("Erro ao ler JSON:", error)
            return []

    @staticmethod
    def get_user_context(profile):
        dados = profile.dynamic_data or {}
        biologico = dados.get('biologico', {})
        psicologico = dados.get('psicologico', {})
        social = dados.get('social', {})
        tecnologico = dados.get('tecnologico', {})

        feedbacks = Feedback.objects.filter(session__profile=profile)

        negativos = [
            f"{feedback.resource.name}: {feedback.user_comment}"
            for feedback in feedbacks
            if feedback.score <= 2 and feedback.resource
        ]
        positivos = [
            f"{feedback.resource.name}: {feedback.user_comment}"
            for feedback in feedbacks
            if feedback.score >= 3 and feedback.resource
        ]

        contexto = "--- PERFIL BIOPSICOSSOCIAL DO USUARIO ---\n"
        contexto += (
            f"[Condicao Biologica]\n"
            f"- Limitacoes Fisicas: {biologico.get('limitacoes_especificas', 'Nao informado')}\n"
            f"- Severidade: {biologico.get('grau_severidade', 'Nao informado')}\n\n"
        )
        contexto += (
            f"[Perfil Psicologico/Cognitivo]\n"
            f"- Estilo de Aprendizado: {psicologico.get('estilo_aprendizado', 'Nao informado')}\n"
            f"- Desafios Cognitivos: {psicologico.get('barreiras_cognitivas', 'Nao informado')}\n\n"
        )
        contexto += (
            f"[Contexto Social e Objetivos]\n"
            f"- Objetivo Atual: {social.get('objetivo_principal', 'Nao informado')}\n"
            f"- Barreiras no Dia a Dia: {social.get('barreiras_dia_a_dia', 'Nao informado')}\n"
            f"- Capacidade Financeira: {social.get('orcamento', 'Nao informado')} "
            f"(priorizar tecnologias que respeitem este orcamento)\n\n"
        )
        contexto += (
            f"[Ambiente Tecnologico]\n"
            f"- Nivel de Proficiencia: {tecnologico.get('nivel_tecnologico', 'Nao informado')} "
            f"(recomendar interfaces compativeis com esta curva de aprendizado)\n"
            f"- Dispositivos Utilizados: {tecnologico.get('dispositivos_disponiveis', 'Nao informado')}\n"
            f"- Ferramentas Previas: {tecnologico.get('ferramentas_previas', 'Nenhuma')}\n\n"
        )

        if negativos:
            contexto += (
                "ATENCAO - Historico Negativo (evitar similares): "
                f"{', '.join(negativos)}.\n"
            )

        if positivos:
            contexto += (
                "Historico Positivo (priorizar similares): "
                f"{', '.join(positivos)}.\n"
            )

        return contexto

    @staticmethod
    def build_reference_block(options):
        if not options:
            return "[]"
        return json.dumps(options, ensure_ascii=False, indent=2)

    @classmethod
    def build_final_prompt(cls, profile):
        categoria = profile.primary_disability_category
        opcoes = cls.get_filtered_technologies(categoria)
        referencias = cls.build_reference_block(opcoes)
        contexto = cls.get_user_context(profile)

        prompt = f"""
Voce e um Motor de Recomendacao Especializado em Tecnologia Assistiva.

### DIRETRIZES DE COMPORTAMENTO:
1. PERSONA: Atue como um analista tecnico imparcial.
2. VOZ: Use estritamente a TERCEIRA PESSOA. Proibido usar "eu", "meu", "acredito" ou "sugiro".
3. FOCO: Priorize as necessidades funcionais, o contexto de acessibilidade, os dispositivos, o orcamento e a curva de aprendizado do perfil.
4. OBJETIVIDADE: Evite adjetivos vagos. Seja especifico sobre funcionalidade tecnica, barreira atendida e criterio de adequacao.
5. FLEXIBILIDADE CONTROLADA: Use as tecnologias fornecidas como referencia, nao como limitacao.
6. EXPANSAO RESPONSAVEL: Voce pode recomendar tecnologias alem das listadas abaixo, se forem mais adequadas ao perfil.
7. QUALIDADE: Evite recomendacoes genericas, repetidas, redundantes ou semanticamente equivalentes.
8. CONFIABILIDADE: Recomende apenas tecnologias reais, categorias reais de tecnologia assistiva ou ferramentas amplamente reconhecidas. Nao invente nomes inexistentes.

### DADOS DE ENTRADA:
- CATEGORIA ANALISADA: {categoria.upper()}
- TECNOLOGIAS DE REFERENCIA (BASE CONFIAVEL, NAO LISTA FECHADA): {referencias}
- PERFIL DO USUARIO (CONTEXTO): {contexto}

### COMO USAR A BASE DE REFERENCIA:
- Considere a lista como exemplos confiaveis ja mapeados para a categoria.
- Priorize a relevancia para o perfil antes de priorizar a semelhanca com a lista.
- Se houver uma opcao fora da lista que atenda melhor ao usuario, ela pode e deve ser recomendada.
- Quando recomendar algo fora da lista, use um nome real e reconhecivel e explique tecnicamente por que a escolha faz sentido.
- Nao repita a mesma tecnologia com nomes levemente diferentes.

### TAREFA:
Selecione as 3 tecnologias mais aderentes ao contexto do usuario. As recomendacoes podem misturar:
1. Tecnologias da base de referencia.
2. Tecnologias fora da base, desde que sejam reais e coerentes com o perfil.

Para cada tecnologia, gere:
1. Definicao tecnica (O que e).
2. Aplicabilidade pratica (Para que serve).
3. Nexo causal: justificativa tecnica de como o recurso reduz uma barreira especifica do contexto.
4. Query de busca otimizada para YouTube.

### REQUISITOS DO OUTPUT (JSON):
- Retorne APENAS o objeto JSON, sem textos introdutorios ou conclusivos.
- O campo "justificativa_geral" deve resumir o quadro funcional do usuario sob a otica da tecnologia assistiva.
- O campo "nome" nao precisa corresponder exatamente a um item da lista de referencia, mas precisa identificar uma tecnologia real e pertinente.
- Certifique-se de que todas as strings estejam devidamente escapadas.

### ESTRUTURA DO JSON:
{{
    "justificativa_geral": "Analise tecnica do perfil do usuario em terceira pessoa...",
    "tecnologias": [
        {{
            "nome": "Nome real e especifico da tecnologia recomendada",
            "o_que_e": "Definicao concisa",
            "para_que_serve": "Utilidade principal",
            "justificativa_usuario": "Explicacao tecnica de como esta ferramenta mitiga as limitacoes descritas no contexto, em terceira pessoa.",
            "termo_youtube": "Busca recomendada"
        }}
    ]
}}
"""
        print("Tamanho do prompt:", len(prompt))
        return prompt
