import streamlit as st
import pandas as pd
import google.generativeai as genai
import time

# --- [ETAPA 1: IMPORTAR NOSSOS MÓDULOS] ---
# Importa todas as ferramentas que construímos
try:
    from config import (
        GEMINI_API_KEY, 
        SEU_NOME_DE_USUARIO, 
        SUA_SENHA
    )
    from supabase_utils import (
        init_connection, 
        save_posts_to_supabase,
        fetch_instagram_data, 
        update_post_classification
    )
    from teste_coletar import login_instagram, coletar_posts_instagram
    from classificador_post import classificar_posts_gemini
except ImportError as e:
    st.error(f"Erro ao importar módulos: {e}")
    st.error("Verifique se os arquivos 'app_config.py', 'supabase_utils.py', 'coletor_insta.py', e 'classificar.py' estão na mesma pasta.")
    st.stop()

# --- Configuração da Página ---
st.set_page_config(
    layout="wide",
    page_title="Analisador de Engajamento do Instagram",
    page_icon="📊"
)

# --- [ETAPA 2: FUNÇÕES DE ANÁLISE (INSIGHTS)] ---
# Estas são as funções do seu app original que geram o relatório final
# (Um pouco limpas e corrigidas)

def gerar_insights_com_gemini(df_posts):
    """Usa a IA para gerar um relatório completo com base nos dados."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') # Modelo estável
        
        # Garante que a coluna 'categoria' exista
        if 'categoria' not in df_posts.columns and 'tipo' in df_posts.columns:
             df_posts = df_posts.rename(columns={'tipo': 'categoria'})
        elif 'categoria' not in df_posts.columns:
            st.error("O DataFrame precisa ter uma coluna 'categoria' ou 'tipo'.")
            return None

        dados_posts_md = df_posts.to_markdown(index=False)
        
        prompt = f"""
        **Você é um especialista em análise de marketing digital e redes sociais.**
        Sua tarefa é analisar os dados de um perfil do Instagram e fornecer um relatório estratégico. Baseie TODA a sua análise exclusivamente nos dados do arquivo fornecido abaixo.

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
        - Com base em TODA a análise, forneça **3 recomendações práticas e acionáveis** para o criador de conteúdo. As dicas devem ser diretas, objetivas e focadas em otimizar o engajamento com base no que funciona melhor para este perfil.

        Formate sua resposta usando Markdown para uma boa apresentação.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Ocorreu um erro ao chamar a API do Gemini (Insights): {e}")
        return None

def chatbot_analise_instagram(df_posts, pergunta_usuario):
    """Função do chatbot para responder perguntas sobre os dados."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') # Modelo estável
        
        if 'categoria' not in df_posts.columns and 'tipo' in df_posts.columns:
             df_posts = df_posts.rename(columns={'tipo': 'categoria'})
        elif 'categoria' not in df_posts.columns:
            return "❌ Erro: Não foi encontrada coluna de categoria nos dados."
            
        # Prepara resumo dos dados para contexto
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
        return response.text
        
    except Exception as e:
        return f"❌ Erro ao processar: {str(e)}"

# --- [ETAPA 3: INTERFACE DA APLICAÇÃO] ---

st.title("📊 Analisador de Engajamento do Instagram")
st.markdown("Colete dados, classifique com IA e gere insights do seu perfil.")

# Inicializar session state
if 'df_posts' not in st.session_state:
    st.session_state.df_posts = None
if 'insights' not in st.session_state:
    st.session_state.insights = None

# --- BARRA LATERAL (SIDEBAR) COM OPÇÕES ---
with st.sidebar:
    st.header("⚙️ Fonte dos Dados")
    
    fonte_dados = st.radio(
        "Selecione como obter os dados:",
        ("Analisar perfil (Coleta + Banco de Dados)", "Carregar arquivo CSV"),
        key="fonte_dados"
    )
    
    st.markdown("---")
    
    df_pronto = None # DataFrame final para análise
    
    if fonte_dados == "Analisar perfil (Coleta + Banco de Dados)":
        st.subheader("Análise via Banco de Dados")
        perfil_instagram = st.text_input("Nome do Perfil", "@orbia.ag")
        
        st.info("Esta opção irá coletar os posts recentes, salvar no banco, classificar com IA e então exibir os insights.")
        
        # Quantidade de posts para coletar
        # (Coloquei um limite de 50 para o app não demorar muito)
        QUANTIDADE_DE_POSTS = st.number_input("Qtd. de posts recentes a coletar:", 10, 100, 30)
        
        botao_analisar = st.button("Coletar e Analisar Perfil", type="primary", use_container_width=True)

    else: # "Carregar arquivo CSV"
        st.subheader("Análise via CSV")
        arquivo_dados = st.file_uploader(
            "Carregue seu arquivo de dados (.csv)",
            type=['csv']
        )
        st.info("O CSV deve ter as colunas: `data`, `tipo` (ou `categoria`), `curtidas`, `comentarios`, `legenda`.")
        
        botao_analisar = st.button("Analisar Arquivo CSV", type="primary", use_container_width=True)

# --- [ETAPA 4: LÓGICA PRINCIPAL] ---

if botao_analisar:
    # Reseta os dados antigos
    st.session_state.df_posts = None
    st.session_state.insights = None
    
    # --- ROTA 1: Análise via Coleta + Banco ---
    if fonte_dados == "Analisar perfil (Coleta + Banco de Dados)":
        if not perfil_instagram:
            st.error("Por favor, insira um nome de perfil para analisar.")
            st.stop()
            
        perfil_alvo = perfil_instagram.replace('@', '')
        
        try:
            # 1. Conectar ao Supabase
            with st.spinner("Conectando ao Supabase..."):
                supabase = init_connection()
            
            # 2. Conectar e Coletar do Instagram
            with st.spinner(f"Conectando ao Instagram e coletando {QUANTIDADE_DE_POSTS} posts de @{perfil_alvo}..."):
                cl_insta = login_instagram()
                if not cl_insta:
                    st.error("Falha no login do Instagram. Verifique as credenciais em 'app_config.py'")
                    st.stop()
                df_novos_posts = coletar_posts_instagram(cl_insta, perfil_alvo, QUANTIDADE_DE_POSTS)
            
            # 3. Salvar no Supabase
            with st.spinner(f"Salvando {len(df_novos_posts)} posts no banco de dados..."):
                if not df_novos_posts.empty:
                    save_posts_to_supabase(supabase, df_novos_posts, perfil_alvo)
                else:
                    st.info("Nenhum post novo encontrado na coleta.")

            # 4. Buscar TODOS os dados (incluindo os novos)
            with st.spinner(f"Buscando histórico completo de @{perfil_alvo} no banco..."):
                df_todos_posts = fetch_instagram_data(supabase, perfil_alvo)
                if df_todos_posts is None:
                    st.error(f"Nenhum dado encontrado para @{perfil_alvo} no banco.")
                    st.stop()
            
            # 5. Classificar o que for necessário
            with st.spinner("Verificando posts para classificar com IA..."):
                df_para_classificar = df_todos_posts[
                    (df_todos_posts['tipo'].isnull()) | 
                    (df_todos_posts['tipo'] == 'Erro na Classificação')
                ]
                
                if not df_para_classificar.empty:
                    st.write(f"Enviando {len(df_para_classificar)} posts para classificação (pode levar alguns minutos)...")
                    classificacoes = classificar_posts_gemini(df_para_classificar, GEMINI_API_KEY)
                    update_post_classification(supabase, classificacoes)
                else:
                    st.info("Todos os posts já estavam classificados.")

            # 6. Buscar os dados finais e prontos para análise
            with st.spinner("Buscando dados finais classificados..."):
                df_pronto = fetch_instagram_data(supabase, perfil_alvo)
                # Garante que a coluna se chame 'categoria'
                if 'tipo' in df_pronto.columns:
                    df_pronto = df_pronto.rename(columns={'tipo': 'categoria'})

        except Exception as e:
            st.error(f"Ocorreu um erro durante o processo: {e}")
            st.stop()

    # --- ROTA 2: Análise via CSV ---
    else: # fonte_dados == "Carregar arquivo CSV"
        if not arquivo_dados:
            st.error("Por favor, carregue um arquivo .csv para analisar.")
            st.stop()
        
        with st.spinner('Lendo os dados e preparando a análise...'):
            df_pronto = pd.read_csv(arquivo_dados)
            # Garante que a coluna se chame 'categoria'
            if 'tipo' in df_pronto.columns:
                df_pronto = df_pronto.rename(columns={'tipo': 'categoria'})
            elif 'categoria' not in df_pronto.columns:
                st.error("O CSV deve ter uma coluna 'tipo' ou 'categoria'.")
                st.stop()

    # --- [ETAPA 5: GERAR INSIGHTS E MOSTRAR RESULTADOS] ---
    # Esta parte é comum para as duas rotas
    
    if df_pronto is not None and not df_pronto.empty:
        with st.spinner('A IA está gerando o relatório completo... Isso pode levar um momento. 🧠'):
            insights = gerar_insights_com_gemini(df_pronto.copy())

        if insights:
            st.session_state.df_posts = df_pronto
            st.session_state.insights = insights
            st.success("Análise concluída!")
        else:
            st.error("Não foi possível gerar os insights pela IA.")

    else:
        st.error("Nenhum dado foi carregado para análise.")


# --- [ETAPA 6: EXIBIÇÃO DAS ABAS (TABS)] ---
# Esta parte do seu código original não muda

if st.session_state.df_posts is not None:
    
    # Garante que a coluna 'categoria' existe e não é 'tipo'
    if 'categoria' not in st.session_state.df_posts.columns and 'tipo' in st.session_state.df_posts.columns:
        st.session_state.df_posts = st.session_state.df_posts.rename(columns={'tipo': 'categoria'})
    
    tab_visao_geral, tab_analise_categoria, tab_insights_ia, tab_chatbot = st.tabs([
        "Visão Geral 📈", 
        "Análise por Categoria 📚", 
        "Insights da IA 💡",
        "Converse com o Chatbot 💬"
    ])

    with tab_visao_geral:
        st.subheader("Dados dos Posts Analisados")
        st.dataframe(st.session_state.df_posts, use_container_width=True)

    with tab_analise_categoria:
        st.subheader("Desempenho Médio por Categoria de Conteúdo")
        
        # Verifica se a coluna 'categoria' existe antes de agrupar
        if 'categoria' in st.session_state.df_posts.columns:
            # Garante que curtidas e comentários são numéricos
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
    # Tela inicial
    st.info("👈 Configure a fonte dos dados na barra lateral e clique em 'Analisar'.")