import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai

# --- Configuração da Página ---
st.set_page_config(
    layout="wide",
    page_title="Analisador de Engajamento do Instagram",
    page_icon="📊"
)

# --- Chave da API ---
GEMINI_API_KEY = "AIzaSyAb_-ri-6VHMIw9da8G_bDm1TwRIEIuPaM"

# --- Função da API Gemini para Análise (RAG) ---
def gerar_insights_com_gemini(df_posts):
    """Usa a IA para gerar um relatório completo com base nos dados do arquivo CSV."""
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')
        # Usar 'tipo' como categoria para análise
        if 'tipo' in df_posts.columns:
            df_analise = df_posts.rename(columns={'tipo': 'categoria'})
        elif 'tipo' in df_posts.columns:
            coluna_categoria = 'tipo'
            df_posts = df_posts.rename(columns={'tipo': 'categoria'})
        else:
            st.error("O arquivo CSV precisa ter uma coluna chamada 'categoria' ou 'tipo'.")
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
        st.error(f"Ocorreu um erro ao chamar a API do Gemini: {e}")
        return None

# --- Função do Chatbot ---
def chatbot_analise_instagram(df_posts, pergunta_usuario):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
                # Verificar qual coluna usar para categoria
        if 'categoria' in df_posts.columns:
            coluna_categoria = 'categoria'
        elif 'tipo' in df_posts.columns:
            coluna_categoria = 'tipo'
            df_posts = df_posts.rename(columns={'tipo': 'categoria'})
        else:
            return "❌ Erro: Não foi encontrada coluna de categoria nos dados."
            
        # Prepara resumo dos dados para contexto
        dados_resumo = {
            'total_posts': len(df_posts),
            'periodo': f"{df_posts['data'].min()} a {df_posts['data'].max()}",
            'categoria_conteudo': df_posts['categoria'].value_counts().to_dict(),
            'media_curtidas': df_posts['curtidas'].mean(),
            'media_comentarios': df_posts['comentarios'].mean(),
            'top_curtidas': df_posts.nlargest(1, 'curtidas')[['data', 'curtidas', 'comentarios', 'legenda']].to_dict('records')[0] if len(df_posts) > 0 else {},
            'top_comentarios': df_posts.nlargest(1, 'comentarios')[['data', 'curtidas', 'comentarios', 'legenda']].to_dict('records')[0] if len(df_posts) > 0 else {}
        }
        
        prompt = f"""
        Você é um especialista em análise de mídias sociais e marketing digital. 
        Analise os dados do Instagram fornecidos e responda à pergunta do usuário.

        **DADOS DO PERFIL ANALISADO:**
        - Total de posts: {dados_resumo['total_posts']}
        - Período: {dados_resumo['periodo']}
        - Tipos de conteúdo: {dados_resumo['tipos_conteudo']}
        - Média de curtidas: {dados_resumo['media_curtidas']:.1f}
        - Média de comentários: {dados_resumo['media_comentarios']:.1f}

        **PERGUNTA ATUAL:**
        {pergunta_usuario}

        **INSTRUÇÕES:**
        - Baseie sua resposta NOS DADOS FORNECIDOS
        - Seja prático e objetivo
        - Use markdown para formatação
        - Se não tiver dados para responder, explique educadamente
        - Mantenha em português

        **RESPONDA:**
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ Erro ao processar: {str(e)}"

# --- Interface da Aplicação ---

st.title("📊 Analisador de Engajamento do Instagram")
st.markdown("Faça o upload dos seus dados e receba insights gerados por IA e converse com o chatbot.")

with st.sidebar:
    st.header("⚙️ Configurações da Análise")
    perfil_instagram = st.text_input("Perfil do Instagram", "@seu_usuario")
    
    hoje = datetime.date.today()
    data_inicio_padrao = hoje - datetime.timedelta(days=90)
    periodo_analise = st.date_input(
        "Selecione o Período de Análise",
        (data_inicio_padrao, hoje),
        format="DD/MM/YYYY"
    )
    arquivo_dados = st.file_uploader(
        "Carregue seu arquivo de dados (.csv)",
        type=['csv']
    )
    st.info("O CSV deve ter as colunas: `data`, `tipo`, `curtidas`, `comentarios`, `legenda`,`link`,`id`, `lote`, .")
    botao_analisar = st.button("Analisar Perfil", type="primary", use_container_width=True)

# Inicializar session state para os dados
if 'df_posts' not in st.session_state:
    st.session_state.df_posts = None
if 'insights' not in st.session_state:
    st.session_state.insights = None

# Processar análise quando o botão for clicado
if botao_analisar:
    if not arquivo_dados:
        st.error("Por favor, carregue um arquivo .csv para analisar.")
    else:
        try:
            with st.spinner('Lendo os dados e preparando a análise...'):
                df_posts = pd.read_csv(arquivo_dados)
                if 'tipo' not in df_posts.columns:
                    st.error("O arquivo CSV precisa ter uma coluna chamada 'tipo'.")
                    st.stop()
                
                df_posts_renomeado = df_posts.rename(columns={'tipo': 'categoria'})

            with st.spinner('A IA está gerando o relatório completo... Isso pode levar um momento. 🧠'):
                insights = gerar_insights_com_gemini(df_posts.copy())

            if insights:
                # Salvar dados no session state
                st.session_state.df_posts = df_posts
                st.session_state.insights = insights
                st.session_state.df_posts_renomeado = df_posts_renomeado
                st.success("Análise concluída!")

        except Exception as e:
            st.error(f"Ocorreu um erro inesperado durante a análise: {e}")

# Exibir resultados se os dados estiverem carregados
if st.session_state.df_posts is not None:
    # Exibição dos resultados nas abas
    tab_visao_geral, tab_analise_categoria, tab_insights_ia, tab_chatbot = st.tabs([
        "Visão Geral 📈", 
        "Análise por Categoria 📚", 
        "Insights da IA 💡",
        "Converse com o Chatbot"
    ])

    with tab_visao_geral:
        st.subheader("Dados dos Posts Analisados")
        st.dataframe(st.session_state.df_posts, use_container_width=True)

    with tab_analise_categoria:
        st.subheader("Desempenho Médio por Categoria de Conteúdo")
        analise_categoria = st.session_state.df_posts_renomeado.groupby('categoria')[['curtidas', 'comentarios']].mean().sort_values(by='curtidas', ascending=False)
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

    with tab_insights_ia:
        st.markdown(st.session_state.insights)

    with tab_chatbot:
        st.subheader("💬 Converse com o Chatbot Especialista")
        
        # Input do usuário - versão simples sem histórico
        pergunta_usuario = st.chat_input("Faça uma pergunta sobre seus dados do Instagram...")
        
        if pergunta_usuario:
            # Exibir pergunta do usuário
            with st.chat_message("user"):
                st.markdown(pergunta_usuario)
            
            # Gerar resposta do chatbot
            with st.spinner("Analisando seus dados..."):
                resposta = chatbot_analise_instagram(st.session_state.df_posts, pergunta_usuario)
            
            # Exibir resposta
            with st.chat_message("assistant"):
                st.markdown(resposta)

else:
    st.info("Configure as opções na barra lateral, carregue seu arquivo e clique em 'Analisar Perfil'.")