import streamlit as st
import pandas as pd
import google.generativeai as genai
import time

# --- [ETAPA 1: IMPORTAR NOSSOS MÓDULOS] ---
# (Sem alterações)
try:
    from config import (
        GEMINI_API_KEY, 
        SEU_NOME_DE_USUARIO, 
        SUA_SENHA
    )
    from mongodb_utils import (
        init_connection, 
        save_posts_to_mongodb,
        fetch_instagram_data, 
        update_post_classification
    )
    from teste_coletar import login_instagram, coletar_posts_instagram
    from classificador_post import classificar_posts_gemini
except ImportError as e:
    st.error(f"Erro ao importar módulos: {e}")
    st.error("Verifique se os arquivos 'app_config.py', 'mongodb_utils.py', 'coletor_insta.py', e 'classificar.py' estão na mesma pasta.")
    st.stop()

# --- Configuração da Página ---
# (Sem alterações)
st.set_page_config(
    layout="wide",
    page_title="Agente de Relatoria",
    page_icon="📊"
)

# --- [NOVO - ETAPA 1.5: FUNÇÃO DE PROCESSAMENTO REUTILIZÁVEL] ---

def processar_perfil(mongo_client, insta_client, nome_perfil, qtd_posts):
    """
    Executa o pipeline completo de coleta, salvamento, classificação e 
    busca de dados para um único perfil de Instagram.
    Retorna um DataFrame classificado ou None em caso de falha.
    """
    try:
        perfil_alvo = nome_perfil.replace('@', '')
        
        # 1. Coletar do Instagram
        with st.spinner(f"Coletando {qtd_posts} posts de @{perfil_alvo}..."):
            df_novos_posts = coletar_posts_instagram(insta_client, perfil_alvo, qtd_posts)
        
        # 2. Salvar no Mongo
        with st.spinner(f"Salvando {len(df_novos_posts)} posts de @{perfil_alvo} no banco..."):
            if df_novos_posts is not None and not df_novos_posts.empty:
                save_posts_to_mongodb(mongo_client, df_novos_posts, perfil_alvo)
            else:
                st.info(f"Nenhum post novo encontrado para @{perfil_alvo} na coleta.")

        # 3. Buscar TODOS os dados (incluindo os novos)
        with st.spinner(f"Buscando histórico completo de @{perfil_alvo} no banco..."):
            df_todos_posts = fetch_instagram_data(mongo_client, perfil_alvo, limit=qtd_posts)
            if df_todos_posts is None:
                st.error(f"Nenhum dado encontrado para @{perfil_alvo} no banco.")
                return None
        
        # 4. Classificar o que for necessário
        with st.spinner(f"Verificando posts de @{perfil_alvo} para classificar com IA..."):
            df_todos_posts['tipo'] = df_todos_posts['tipo'].fillna('')
            df_para_classificar = df_todos_posts[
                (df_todos_posts['tipo'].str.strip() == '') | 
                (df_todos_posts['tipo'] == 'Erro na Classificação')
            ]
            
            if not df_para_classificar.empty:
                st.write(f"Enviando {len(df_para_classificar)} posts de @{perfil_alvo} para classificação...")
                classificacoes = classificar_posts_gemini(df_para_classificar, GEMINI_API_KEY)
                update_post_classification(mongo_client, classificacoes)
            else:
                st.info(f"Todos os posts de @{perfil_alvo} já estavam classificados.")
        limit_analise_final = qtd_posts if st.session_state.get('fonte_dados') != "Analisar perfil (Coleta + Banco de Dados)" else 0        

        # 5. Buscar os dados finais e prontos para análise
        with st.spinner(f"Buscando dados finais de @{perfil_alvo} classificados..."):
            df_final = fetch_instagram_data(mongo_client, perfil_alvo, limit=limit_analise_final)
            # Garante que a coluna se chame 'categoria'
            if 'tipo' in df_final.columns:
                df_final = df_final.rename(columns={'tipo': 'categoria'})
            
            # [NOVO] Adiciona o nome do perfil ao DF para referência futura
            df_final['perfil'] = perfil_alvo
            
            return df_final

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o perfil @{perfil_alvo}: {e}")
        return None

# --- [ETAPA 2: FUNÇÕES DE ANÁLISE (INSIGHTS)] ---
# (Sem alterações, apenas corrigi nomes de modelos que não existem para um que funciona)
def gerar_insights_com_gemini(df_posts):
    """Usa a IA para gerar um relatório completo com base nos dados."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        # (Restante da função sem alterações)
        if 'categoria' not in df_posts.columns and 'tipo' in df_posts.columns:
             df_posts = df_posts.rename(columns={'tipo': 'categoria'})
        elif 'categoria' not in df_posts.columns:
            st.error("O DataFrame precisa ter uma coluna 'categoria' ou 'tipo'.")
            return None
        dados_posts_md = df_posts.to_markdown(index=False)
        prompt = f"""
        **Você é um especialista em análise de marketing digital e redes sociais.**
        Sua tarefa é analisar os dados de um perfil do Instagram e fornecer um relatório estratégico. Baseie TODA a sua análise exclusivamente nos dados do arquivo fo
        **Dados dos Posts Analisados:**
        {dados_posts_md}
        **Por favor, elabore um relatório claro e objetivo com a seguinte estrutura:**
        ### 1. Análise de Performance por Categoria
        - Qual categoria de conteúdo (`categoria`) teve a melhor média de **curtidas**?
        - Qual categoria teve a melhor média de **comentários**?
        - Compare o desempenho e explique qual tipo de conteúdo parece gerar mais engajamento geral no perfil.
        ### 2. Posts de Maior Destaque
        - Identifique o **post individual com o maior número de curtidas**. Mencione a data, a legenda e a categoria.
        - Identifique o **post individual com o maior número de comentários**. Mencione a data, a legenda e a categoria.
        ### 3. Plano de Ação Estratégico
        - Com base em TODA a análise, forneça **3 recomendações práticas e acionáveis** para o criador de conteúdo. As dicas devem ser diretas, objetivas e focadas em
        Formate sua resposta usando Markdown para uma boa apresentação.
        """
        response = model.generate_content(prompt)
        print("REQUISIÇÃO DO INSIGHT")
        return response.text
    except Exception as e:
        st.error(f"Ocorreu um erro ao chamar a API do Gemini (Insights): {e}")
        return None

def chatbot_analise_instagram(df_posts, pergunta_usuario):
    """Função do chatbot para responder perguntas sobre os dados."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        if 'categoria' not in df_posts.columns and 'tipo' in df_posts.columns:
             df_posts = df_posts.rename(columns={'tipo': 'categoria'})
        elif 'categoria' not in df_posts.columns:
            return "❌ Erro: Não foi encontrada coluna de categoria nos dados."
        dados_resumo = {
            'total_posts': len(df_posts),
            'periodo': f"{df_posts['data'].min()} a {df_posts['data'].max()}",
            'categoria_conteudo': df_posts['categoria'].value_counts().to_dict(),
            'media_curtidas': df_posts['curtidas'].mean(),
            'media_comentarios': df_posts['comentarios'].mean(),
        }
        prompt = f"""
        Você é um especialista em análise de mídias sociais e marketing digital. 
        Analise os dados do Instagram fornecidos e responda à pergunta do usuário.
        **DADOS DO PERFIL ANALISADO:**
        - Total de posts: {dados_resumo['total_posts']}
        - Período: {dados_resumo['periodo']}
        - Tipos de conteúdo: {dados_resumo['categoria_conteudo']}
        - Média de curtidas: {dados_resumo['media_curtidas']:.1f}
        - Média de comentários: {dados_resumo['media_comentarios']:.1f}
        **PERGUNTA ATUAL:**
        {pergunta_usuario}
        **INSTRUÇÕES:**
        - Baseie sua resposta NOS DADOS FORNECIDOS
        - Seja prático e objetivo
        - Use markdown para formatação
        - Mantenha em português
        **RESPONDA:**
        """
        response = model.generate_content(prompt)
        print("REQUISIÇÃO DO CHATBOT")
        return response.text
    except Exception as e:
        return f"❌ Erro ao processar: {str(e)}"




# --- [FUNÇÃO DE ANÁLISE DE CONCORRÊNCIA - COM PROMPT ATUALIZADO] ---
def gerar_insights_concorrencia(df_posts_comparativo):
    """Usa a IA para gerar um relatório de comparação entre perfis, focando nas diferenças de conteúdo."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        if 'categoria' not in df_posts_comparativo.columns or 'perfil' not in df_posts_comparativo.columns:
            st.error("O DataFrame de comparação precisa ter as colunas 'categoria' e 'perfil'.")
            return None
            
        dados_comparacao_md = df_posts_comparativo.to_markdown(index=False)
        
        # Geração de resumos estatísticos básicos para incluir no prompt
        resumo_perfis = df_posts_comparativo.groupby('perfil').agg(
            total_posts=('link', 'count'),
            media_curtidas=('curtidas', 'mean'),
            media_comentarios=('comentarios', 'mean')
        ).reset_index()
        
        # Análise das categorias mais usadas
        analise_categorias = df_posts_comparativo.groupby(['perfil', 'categoria']).size().reset_index(name='Contagem')
        
        resumo_md = resumo_perfis.to_markdown(index=False, floatfmt=".1f")
        categorias_md = analise_categorias.to_markdown(index=False)

        prompt = f"""
        **Você é um Estrategista de Marketing Digital especializado em Benchmarking de Mídias Sociais.**
        Sua tarefa é analisar os dados fornecidos dos perfis do Instagram e fornecer um relatório estratégico de Análise de Concorrência. O foco deve ser na **estraté

        **1. ESTATÍSTICAS GERAIS:**
        {resumo_md}
        
        **2. DISTRIBUIÇÃO DE CONTEÚDO POR CATEGORIA:**
        {categorias_md}
        
        **3. DADOS DETALHADOS (Para análise de legenda):**
        {dados_comparacao_md}

        **Por favor, elabore um relatório claro e objetivo com a seguinte estrutura:**
        ### 1. Ponto Forte da Concorrência
        - Qual perfil (o principal ou o concorrente) demonstrou o **melhor engajamento médio** e qual é o seu **PONTO FORTE** primário (ex: alta média de comentários 
        
        ### 2. Análise Estratégica de Conteúdo
        - Compare a **diferença** dos conteúdos dos dois perfis com base na coluna `categoria` e nas legendas.
        - Com base nas legendas, identifique as **maiores diferenças** no **tipo de conteúdo** que cada perfil utiliza. (Ex: um foca em 'Dicas', outro em 'Bastidores'
        
        ### 3. Oportunidades e Plano de Ação
        - Pensando nos resultados da concorrência, quais **possíveis acertos e erros** você consegue inferir na estratégia do concorrente?
        - Forneça **3 recomendações práticas e acionáveis** para o perfil principal aprender com o concorrente ou se diferenciar. As dicas devem ser focadas em replic
        
        Formate sua resposta usando Markdown para uma boa apresentação.
        """
        response = model.generate_content(prompt)
        print("REQUISIÇÃO DA CONCORRENCIA")
        return response.text
    except Exception as e:
        st.error(f"Ocorreu um erro ao chamar a API do Gemini (Concorrência): {e}")
        return None
    
# --- [ETAPA 3: INTERFACE DA APLICAÇÃO] ---
# (Sem alterações)
st.title("📊 Agente de Relatoria")
st.markdown("Colete dados, classifique com IA e gere insights do seu perfil.")

# Inicializar session state
if 'df_posts' not in st.session_state:
    st.session_state.df_posts = None
if 'insights' not in st.session_state:
    st.session_state.insights = None

if 'insights_concorrencia' not in st.session_state:
    st.session_state.insights_concorrencia = None

# --- BARRA LATERAL (SIDEBAR) COM OPÇÕES ---
# (Sem alterações)
with st.sidebar:
    st.header("⚙️ Fonte dos Dados")
    fonte_dados = st.radio(
        "Selecione como obter os dados:",
        ("Analisar perfil (Coleta + Banco de Dados)", "Análise de Concorrência (Coleta + Banco de Dados)", "Carregar arquivo CSV"),
        key="fonte_dados"
    )
    st.markdown("---")
    df_pronto = None 
    if fonte_dados == "Analisar perfil (Coleta + Banco de Dados)":
        st.subheader("Análise via Banco de Dados")
        perfil_instagram = st.text_input("Nome do Perfil", "@orbia.ag")
        st.info("Esta opção irá coletar os posts recentes, salvar no banco, classificar com IA e então exibir os insights.")
        QUANTIDADE_DE_POSTS = st.number_input("Qtd. de posts recentes a coletar:", 1, 100, 40)
        botao_analisar = st.button("Coletar e Analisar Perfil", type="primary", use_container_width=True)
    
    elif fonte_dados == "Análise de Concorrência (Coleta + Banco de Dados)":
        st.subheader("Análise de Concorrência (Opcional)")
        perfil_principal = st.text_input("Seu Perfil Principal", "@orbia.ag")
        perfil_concorrente = st.text_input("Perfil do Concorrente (Opcional)", "") # Campo opcional
        
        if perfil_concorrente:
            st.info(f"Serão coletados e comparados os dados de {perfil_principal} e {perfil_concorrente}.")
            texto_botao = "Coletar e Comparar Perfis"
        else:
            st.info(f"O campo do concorrente está vazio. Será realizada uma **análise de perfil único** de @{perfil_principal}.")
            texto_botao = "Coletar e Analisar Perfil"
            
        QUANTIDADE_DE_POSTS = st.number_input("Qtd. de posts por perfil a coletar:", 1, 100, 30, key="qtd_concorrencia")
        
        botao_analisar = st.button(texto_botao, type="primary", use_container_width=True)
        # Inicializa as variáveis se a opção for Concorrência
        perfil_instagram = None
    
    
    else: 
        st.subheader("Análise via CSV")
        arquivo_dados = st.file_uploader(
            "Carregue seu arquivo de dados (.csv)",
            type=['csv']
        )
        st.info("O CSV deve ter as colunas: `data`, `tipo` (ou `categoria`), `curtidas`, `comentarios`, `legenda`.")
        botao_analisar = st.button("Analisar Arquivo CSV", type="primary", use_container_width=True)

# --- [ALTERADO - ETAPA 4: LÓGICA PRINCIPAL] ---
# Esta etapa agora ficou muito mais limpa!

if botao_analisar:
    # Reseta os dados antigos
    st.session_state.df_posts = None
    st.session_state.insights = None
    st.session_state.insights_concorrencia = None
    
    # --- ROTA 1: Análise via Coleta + Banco ---
    if fonte_dados == "Analisar perfil (Coleta + Banco de Dados)":
        if not perfil_instagram:
            st.error("Por favor, insira um nome de perfil para analisar.")
            st.stop()
            
        # [ALTERADO] Todo o bloco try/except antigo foi substituído por isto:
        try:
            # 1. Conectar ao Supabase
            with st.spinner("Conectando ao Supabase..."):
                mongo = init_connection()
            
            # 2. Conectar ao Instagram
            with st.spinner(f"Conectando ao Instagram..."):
                cl_insta = login_instagram()
                if not cl_insta:
                    st.error("Falha no login do Instagram. Verifique as credenciais em 'app_config.py'")
                    st.stop()
            
            # 3. [NOVO] Chamar a função de processamento
            st.markdown("---")
            st.subheader(f"Processando Perfil: {perfil_instagram}")
            df_pronto = processar_perfil(mongo, cl_insta, perfil_instagram, QUANTIDADE_DE_POSTS)

        except Exception as e:
            st.error(f"Ocorreu um erro durante o processo: {e}")
            st.stop()

    
    elif fonte_dados == "Análise de Concorrência (Coleta + Banco de Dados)":
        if not perfil_principal:
            st.error("Por favor, insira o nome do Perfil Principal.")
            st.stop()
        
        # 1. Definir os perfis a processar
        perfis_a_analisar = [perfil_principal]
        # Adiciona o concorrente apenas se ele foi preenchido e é diferente do principal
        if perfil_concorrente and perfil_concorrente.replace('@', '') != perfil_principal.replace('@', ''):
            perfis_a_analisar.append(perfil_concorrente)
        
        try:
            with st.spinner("Conectando aos serviços (Mongo e Instagram)..."):
                mongo = init_connection()
                cl_insta = login_instagram()
                if not cl_insta:
                    st.error("Falha no login do Instagram.")
                    st.stop()

            todos_dfs = []
            for i, perfil in enumerate(perfis_a_analisar):
                st.markdown("---")
                st.subheader(f"Processando Perfil {i+1}/{len(perfis_a_analisar)}: {perfil}")
                df_perfil = processar_perfil(mongo, cl_insta, perfil, QUANTIDADE_DE_POSTS)
                if df_perfil is not None:
                    todos_dfs.append(df_perfil)
            
            if todos_dfs:
                df_pronto = pd.concat(todos_dfs, ignore_index=True)
                st.session_state.df_posts = df_pronto 
            else:
                st.error("Nenhum dado foi coletado para análise.")
                st.stop()

        except Exception as e:
            st.error(f"Ocorreu um erro durante o processamento: {e}")
            st.stop()    



    # --- ROTA 2: Análise via CSV ---
    else: 
        if not arquivo_dados:
            st.error("Por favor, carregue um arquivo .csv para analisar.")
            st.stop()
        
        with st.spinner('Lendo os dados e preparando a análise...'):
            df_pronto = pd.read_csv(arquivo_dados)
            if 'tipo' in df_pronto.columns:
                df_pronto = df_pronto.rename(columns={'tipo': 'categoria'})
            elif 'categoria' not in df_pronto.columns:
                st.error("O CSV deve ter uma coluna 'tipo' ou 'categoria'.")
                st.stop()
            
            # [NOVO] Adiciona coluna de perfil para consistência com a Rota 1
            df_pronto['perfil'] = "perfil_csv"

    # --- [ETAPA 5: GERAR INSIGHTS E MOSTRAR RESULTADOS] ---
    # (Sem alterações)
    if df_pronto is not None and not df_pronto.empty:
        
        # 1. Determina o modo de análise (Perfil Único ou Concorrência)
        num_perfis = len(df_pronto['perfil'].unique())
        
        if num_perfis > 1:
            # Modo Concorrência: Ativa o prompt de comparação
            with st.spinner('A IA está gerando o relatório de **COMPARAÇÃO**... 🧠'):
                insights_concorrencia = gerar_insights_concorrencia(df_pronto.copy())
            
            if insights_concorrencia:
                st.session_state.df_posts = df_pronto
                st.session_state.insights_concorrencia = insights_concorrencia
                st.success("Análise de concorrência concluída!")
            else:
                st.error("Não foi possível gerar os insights de concorrência.")
        else: 
            # Modo Perfil Único (Rota 1, Rota 2 sem concorrente, ou CSV)
            with st.spinner('A IA está gerando o relatório completo... Isso pode levar um momento. 🧠'):
                insights = gerar_insights_com_gemini(df_pronto.copy())

            if insights:
                st.session_state.df_posts = df_pronto
                st.session_state.insights = insights
                st.success("Análise de perfil único concluída!")
            else:
                st.error("Não foi possível gerar os insights pela IA.")
    elif botao_analisar:
        st.error("Nenhum dado foi carregado para análise.")

# --- [ALTERADO - ETAPA 6: EXIBIÇÃO DAS ABAS (TABS)] ---
# (Pequena melhoria para usar o nome do perfil no título)

if st.session_state.df_posts is not None:
    
    # 1. Ajuste e detecção do modo de análise
    if 'categoria' not in st.session_state.df_posts.columns and 'tipo' in st.session_state.df_posts.columns:
        st.session_state.df_posts = st.session_state.df_posts.rename(columns={'tipo': 'categoria'})
    
    # Verifica se há mais de um perfil no DataFrame para ativar o modo Concorrência
    perfis_analisados = st.session_state.df_posts['perfil'].unique()
    modo_concorrencia = len(perfis_analisados) > 1

    # 2. Definição das Abas
    if modo_concorrencia:
        # Modo Concorrência: Foco na comparação
        tab_visao_geral, tab_analise_concorrencia = st.tabs([
            "Dados Comparativos 📊", 
            "Análise de Concorrência da IA ⚔️"
        ])
    else:
        # Modo Perfil Único/CSV: Abas originais
        tab_visao_geral, tab_analise_categoria, tab_insights_ia, tab_chatbot = st.tabs([
            "Visão Geral 📈", 
            "Análise por Categoria 📚", 
            "Insights da IA 💡",
            "Converse com o Chatbot 💬"
        ])

    with tab_visao_geral:
        # [ALTERADO] Adapta a subheader para mostrar os perfis ou o único perfil
        if modo_concorrencia:
            st.subheader(f"Dados dos Posts Comparados: {', '.join([f'@{p}' for p in perfis_analisados])}")
        else:
            nome_perfil = perfis_analisados[0]
            st.subheader(f"Dados dos Posts Analisados: @{nome_perfil}")
        
        st.dataframe(st.session_state.df_posts, use_container_width=True)
        
    # 3. Conteúdo da Nova Aba de Concorrência
    if modo_concorrencia:
        with tab_analise_concorrencia:
            if st.session_state.get('insights_concorrencia'):
                st.markdown(st.session_state.insights_concorrencia)
            else:
                st.info("Aguardando a análise da IA de concorrência. Clique no botão na barra lateral para iniciar.")
        
        # [OPCIONAL] Mostrar análise por categoria agrupada, mesmo no modo concorrência
        st.subheader("Desempenho Médio por Perfil e Categoria")
        if 'categoria' in st.session_state.df_posts.columns:
            df_analise = st.session_state.df_posts.copy()
            df_analise['curtidas'] = pd.to_numeric(df_analise['curtidas'], errors='coerce').fillna(0)
            df_analise['comentarios'] = pd.to_numeric(df_analise['comentarios'], errors='coerce').fillna(0)
            
            # Agrupa por PERFIL e depois por CATEGORIA
            analise_combinada = df_analise.groupby(['perfil', 'categoria'])[['curtidas', 'comentarios']].mean().reset_index()
            
            for perfil in sorted(perfis_analisados):
                st.markdown(f"#### @{perfil}")
                df_perfil = analise_combinada[analise_combinada['perfil'] == perfil]
                if not df_perfil.empty:
                    df_perfil = df_perfil.set_index('categoria').drop(columns=['perfil']).sort_values(by='curtidas', ascending=False)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("##### Média de Curtidas")
                        st.bar_chart(df_perfil['curtidas'])
                    with col2:
                        st.markdown("##### Média de Comentários")
                        st.bar_chart(df_perfil['comentarios'])
                    st.dataframe(df_perfil, use_container_width=True)
                else:
                    st.warning(f"Nenhum dado classificado para @{perfil} para mostrar a análise detalhada.")


    # 4. Conteúdo das Abas Antigas (Apenas se não for modo concorrência)
    else: # Modo Perfil Único/CSV
        with tab_analise_categoria:
            nome_perfil = perfis_analisados[0]
            st.subheader(f"Desempenho Médio por Categoria: @{nome_perfil}")
            
            if 'categoria' in st.session_state.df_posts.columns:
                df_analise = st.session_state.df_posts.copy()
                df_analise['curtidas'] = pd.to_numeric(df_analise['curtidas'], errors='coerce').fillna(0)
                df_analise['comentarios'] = pd.to_numeric(df_analise['comentarios'], errors='coerce').fillna(0)
                analise_categoria = df_analise.groupby('categoria')[['curtidas', 'comentarios']].mean().sort_values(by='curtidas', ascending=False)
                analise_categoria['curtidas'] = analise_categoria['curtidas'].astype(int)
                analise_categoria['comentarios'] = analise_categoria['comentarios'].astype(int)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Média de Curtidas")
                    st.bar_chart(analise_categoria['curtidas'])
                with col2:
                    st.markdown("#### Média de Comentários")
                    st.bar_chart(analise_categoria['comentarios'])
                st.dataframe(analise_categoria, use_container_width=True)
            else:
                st.error("Coluna 'categoria' não encontrada para análise.")
        
        with tab_insights_ia:
            st.markdown(st.session_state.insights)

        with tab_chatbot:
            st.subheader("💬 Converse com o Chatbot Especialista")
            pergunta_usuario = st.chat_input("Faça uma pergunta sobre seus dados do Instagram...")
            if pergunta_usuario:
                with st.chat_message("user"):
                    st.markdown(pergunta_usuario)
                with st.spinner("Analisando seus dados..."):
                    resposta = chatbot_analise_instagram(st.session_state.df_posts, pergunta_usuario)
                with st.chat_message("assistant"):
                    st.markdown(resposta)
else:
    st.info("👈 Configure a fonte dos dados na barra lateral e clique em 'Analisar'.")
