import json
import os
from django.conf import settings
from apps.recommendations.models import Feedback

class PromptBuilder:

    @staticmethod
    def get_filtered_technologies(category):
        path = os.path.join(settings.BASE_DIR, 'data', 'tecnologias.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                full_data = json.load(f)
                return full_data.get(category, [])
        except Exception as e:
            print("Erro ao ler JSON:", e)
            return []

    @staticmethod
    def get_user_context(profile):
        dados = profile.dynamic_data or {}
        biologico = dados.get('biologico', {})
        psicologico = dados.get('psicologico', {})
        social = dados.get('social', {})
        tecnologico = dados.get('tecnologico', {})

        feedbacks = Feedback.objects.filter(session__profile=profile)

        negativos = [f"{f.resource.name}: {f.user_comment}" for f in feedbacks if f.score <= 2 and f.resource]
        positivos = [f"{f.resource.name}: {f.user_comment}" for f in feedbacks if f.score >= 3 and f.resource]

        # Montando o contexto detalhado para a IA
        contexto = "--- PERFIL BIOPSICOSSOCIAL DO USUÁRIO ---\n"
        contexto += f"[Condição Biológica]\n- Limitações Físicas: {biologico.get('limitacoes_especificas', 'Não informado')}\n- Severidade: {biologico.get('grau_severidade', 'Não informado')}\n\n"
        
        contexto += f"[Perfil Psicológico/Cognitivo]\n- Estilo de Aprendizado: {psicologico.get('estilo_aprendizado', 'Não informado')}\n- Desafios Cognitivos: {psicologico.get('barreiras_cognitivas', 'Não informado')}\n\n"
        
        contexto += f"[Contexto Social e Objetivos]\n- Objetivo Atual: {social.get('objetivo_principal', 'Não informado')}\n- Barreiras no Dia a Dia: {social.get('barreiras_dia_a_dia', 'Não informado')}\n- Capacidade Financeira: {social.get('orcamento', 'Não informado')} (priorizar tecnologias que respeitem este orçamento)\n\n"
        
        contexto += f"[Ambiente Tecnológico]\n- Nível de Proficiência: {tecnologico.get('nivel_tecnologico', 'Não informado')} (recomendar interfaces compatíveis com esta curva de aprendizado)\n- Dispositivos Utilizados: {tecnologico.get('dispositivos_disponiveis', 'Não informado')}\n- Ferramentas Prévias: {tecnologico.get('ferramentas_previas', 'Nenhuma')}\n\n"

        if negativos:
            contexto += f"⚠️ ATENÇÃO - Histórico Negativo (Evitar similares): {', '.join(negativos)}.\n"
        
        if positivos:
            contexto += f"✅ Histórico Positivo (Priorizar similares): {', '.join(positivos)}.\n"

        return contexto

    @classmethod
    def build_final_prompt(cls, profile):
        categoria = profile.primary_disability_category
        opcoes = cls.get_filtered_technologies(categoria)
        contexto = cls.get_user_context(profile)

        prompt = f"""
Você é um Motor de Recomendação Especializado em Tecnologia Assistiva.

### DIRETRIZES DE COMPORTAMENTO:
1. PERSONA: Atue como um analista técnico imparcial.
2. VOZ: Use estritamente a TERCEIRA PESSOA. Proibido usar "eu", "meu", "acredito" ou "sugiro".
3. FOCO: Analise as necessidades do perfil fornecido e correlacione com as opções disponíveis.
4. OBJETIVIDADE: Evite adjetivos vagos. Seja específico sobre a funcionalidade técnica.

### DADOS DE ENTRADA:
- CATEGORIA ANALISADA: {categoria.upper()}
- OPÇÕES DISPONÍVEIS: {json.dumps(opcoes, ensure_ascii=False)}
- PERFIL DO USUÁRIO (CONTEXTO): {contexto}

### TAREFA:
Selecione as 3 tecnologias mais aderentes ao contexto do usuário. Para cada uma, gere:
1. Definição técnica (O que é).
2. Aplicabilidade prática (Para que serve).
3. Nexo Causal: Justificativa técnica de como o recurso resolve uma barreira específica identificada no contexto do usuário.
4. Query de busca otimizada para YouTube.

### REQUISITOS DO OUTPUT (JSON):
- Retorne APENAS o objeto JSON, sem textos introdutórios ou conclusivos.
- O campo "justificativa_geral" deve resumir o quadro clínico/funcional do usuário sob a ótica da tecnologia assistiva.
- Certifique-se de que todas as strings estejam devidamente escapadas.

### ESTRUTURA DO JSON:
{{
    "justificativa_geral": "Análise técnica do perfil do usuário em terceira pessoa...",
    "tecnologias": [
        {{
            "nome": "Nome exato conforme a lista fornecida",
            "o_que_e": "Definição concisa",
            "para_que_serve": "Utilidade principal",
            "justificativa_usuario": "Explicação de como esta ferramenta mitiga as limitações descritas no contexto (em terceira pessoa).",
            "termo_youtube": "Busca recomendada"
        }}
    ]
}}
"""
        print("Tamanho do prompt:", len(prompt))
        return prompt