from apps.catalog.models import ResourceItem
from apps.recommendations.models import Feedback

class PromptBuilder:
    @staticmethod
    def get_user_context(profile):
        """
        Transforma os dados biopsicossociais e o histórico de feedbacks em texto otimizado para a IA.
        """
        deficiencia = profile.primary_disability_category
        dados = profile.dynamic_data or {}
        
        # 1. Extraindo os dados do novo modelo Biopsicossocial
        biologico = dados.get('biologico', {})
        perfil = dados.get('perfil_uso', {})
        tec = dados.get('tecnologico', {})
        
        objetivo = perfil.get('objetivo_principal', 'Não especificado')
        barreiras = perfil.get('barreiras_dia_a_dia', 'Não detalhado')
        limitacoes = biologico.get('limitacoes_especificas', 'Não detalhado')
        nivel_tec = tec.get('nivel_tecnologico', 'Não detalhado')
        
        # 2. Processando Feedbacks (O "Cérebro" do Aprendizado)
        # Buscamos todos os feedbacks deste usuário
        feedbacks = Feedback.objects.filter(session__profile=profile).select_related('resource')
        
        feedbacks_negativos = [f for f in feedbacks if f.score <= 2] # Notas 1 e 2
        feedbacks_positivos = [f for f in feedbacks if f.score >= 4] # Notas 4 e 5
        
        # 2.1 Mapeando rejeições e os motivos (comentários)
        itens_rejeitados = [f.resource.name for f in feedbacks_negativos]
        comentarios_rejeicao = [f"- Sobre {f.resource.name}: {f.user_comment}" for f in feedbacks_negativos if f.user_comment]
        
        # 2.2 Mapeando acertos
        itens_aprovados = [f.resource.name for f in feedbacks_positivos]

        # 3. Construindo o texto para a IA
        contexto = f"Deficiência Principal: {deficiencia}.\n"
        contexto += f"Objetivo Principal do Usuário: {objetivo.upper()}.\n"
        contexto += f"Limitações Físicas/Sensoriais: {limitacoes}.\n"
        contexto += f"Barreiras enfrentadas no dia a dia: {barreiras}.\n"
        contexto += f"Nível de Familiaridade com Tecnologia: {nivel_tec}.\n"
        
        # Adicionando instruções de Feedbacks Positivos
        if feedbacks_positivos:
            contexto += f"\n[HISTÓRICO DE ACERTOS]\n"
            contexto += f"O usuário JÁ AVALIOU POSITIVAMENTE os seguintes itens no passado: {', '.join(itens_aprovados)}.\n"
            contexto += "Se esses itens estiverem disponíveis na lista, RECOMENDE-OS NOVAMENTE, ou priorize itens com funcionamento muito semelhante.\n"
            
        # Adicionando instruções de Feedbacks Negativos e Comentários
        if feedbacks_negativos:
            contexto += f"\n[HISTÓRICO DE ERROS - REGRAS RÍGIDAS]\n"
            contexto += f"NÃO RECOMENDE os seguintes itens (o usuário já testou e não gostou): {', '.join(itens_rejeitados)}.\n"
            
            if comentarios_rejeicao:
                contexto += "ALÉM DISSO, o usuário deixou os seguintes comentários sobre o que não funcionou para ele:\n"
                contexto += "\n".join(comentarios_rejeicao) + "\n"
                contexto += "=> REGRA: Analise esses comentários e NÃO recomende nenhum outro recurso que possua a mesma característica que incomodou o usuário.\n"
        
        # Retornamos o contexto e o objetivo separadamente para usar no prompt
        return contexto, objetivo

    @staticmethod
    def get_catalog_options(profile):
        tag = profile.primary_disability_category
        itens_filtrados = ResourceItem.objects.filter(metadata_tags__contains=[tag])
        
        opcoes = {"TA": [], "MDA": []}
        LIMITE_POR_CATEGORIA = 15 
        
        for item in itens_filtrados:
            if item.category in opcoes and len(opcoes[item.category]) < LIMITE_POR_CATEGORIA:
                descricao = item.description if item.description.strip() else "Sem descrição"
                texto_item = f"- ID {item.id}: {item.name} ({descricao})"
                opcoes[item.category].append(texto_item)
                
        return opcoes

    @classmethod
    def build_final_prompt(cls, profile):
        contexto_usuario, objetivo = cls.get_user_context(profile)
        opcoes_catalogo = cls.get_catalog_options(profile)
        
        prompt = f"""
    Você é um consultor especialista em Acessibilidade, Inclusão e Tecnologias Assistivas.

    Sua tarefa é selecionar EXATAMENTE 6 recursos (3 TA + 3 MDA) com base no perfil do usuário.

    ---

    ### CONTEXTO DO USUÁRIO
    {contexto_usuario}

    ---

    ### OPÇÕES DISPONÍVEIS

    [Tecnologias Assistivas - TA]
    {chr(10).join(opcoes_catalogo['TA']) or "Nenhuma disponível."}

    [Materiais Didáticos Adaptados - MDA]
    {chr(10).join(opcoes_catalogo['MDA']) or "Nenhuma disponível."}

    ---

    ### REGRAS OBRIGATÓRIAS (NÃO PODE VIOLAR)

    - Você DEVE selecionar:
    ✔ 3 itens da categoria TA
    ✔ 3 itens da categoria MDA
    - Total obrigatório: **6 itens**
    - NÃO é permitido retornar menos ou mais que 6 itens
    - NÃO repita itens
    - NÃO invente IDs
    - NÃO ignore categorias

    ---

    ### CRITÉRIOS DE ESCOLHA

    - Priorize resolver as barreiras principais
    - Respeite o nível tecnológico (iniciante → soluções simples)
    - Respeite histórico de feedbacks (NÃO recomendar rejeitados)
    - Priorize autonomia

    ---

    ### JUSTIFICATIVAS (OBRIGATÓRIO)

    Cada justificativa deve seguir:

    [Problema do usuário] + [Como o recurso resolve] + [Benefício prático]

    Máximo: 2 linhas

    ---

    ### FORMATO DE SAÍDA (OBRIGATÓRIO)

    Retorne APENAS JSON válido.

    {{
        "justificativa_geral": "Resumo focado no objetivo {objetivo.upper()}",
        "itens_selecionados": [
            {{"id": X, "categoria": "TA", "justificativa": "..."}},
            {{"id": X, "categoria": "TA", "justificativa": "..."}},
            {{"id": X, "categoria": "TA", "justificativa": "..."}},
            {{"id": X, "categoria": "MDA", "justificativa": "..."}},
            {{"id": X, "categoria": "MDA", "justificativa": "..."}},
            {{"id": X, "categoria": "MDA", "justificativa": "..."}}
        ]
    }}

    ---

    ### VALIDAÇÃO FINAL (CRÍTICO)

    Antes de responder, verifique:

    - Existem exatamente 6 itens?
    - Existem exatamente 3 "TA" e 3 "MDA"?
    - Todos os IDs existem na lista?
    - Nenhum item foi rejeitado anteriormente?

    Se NÃO estiver correto, corrija antes de responder.
    """
        return prompt