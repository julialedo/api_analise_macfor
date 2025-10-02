import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
import os

# --- Configuração da Página ---
st.set_page_config(
    layout="wide",
    page_title="Analisador de Engajamento do Instagram",
    page_icon="📊"
)

# --- Chave da API ---
# A chave da API é definida diretamente no código.
# Para maior segurança em projetos públicos, o ideal seria usar st.secrets.
GEMINI_API_KEY = "AIzaSyAb_-ri-6VHMIw9da8G_bDm1TwRIEIuPaM"

# --- Função da API Gemini para Análise (RAG) ---
def gerar_insights_com_gemini(df_posts):
    """
    Usa a IA para gerar um relatório completo com base nos dados do arquivo CSV.
    """
    try:
        # Configura a API com a chave definida no código
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')

        # Renomeia a coluna 'tipo' para 'categoria' para padronização interna.
        if 'tipo' in df_posts.columns:
            df_posts = df_posts.rename(columns={'tipo': 'categoria'})

        # Prepara os dados para o prompt (RAG)
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

# --- Interface da Aplicação ---

st.title("📊 Analisador de Engajamento do Instagram")
st.markdown("Faça o upload dos seus dados e receba insights gerados por IA para otimizar sua estratégia de conteúdo.")

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
    st.info("O CSV deve ter as colunas: `data`, `legenda`, `curtidas`, `comentarios`, `tipo`.")
    botao_analisar = st.button("Analisar Perfil", type="primary", use_container_width=True)

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
                st.success("Análise concluída!")

                # Exibição dos resultados nas abas
                tab_visao_geral, tab_analise_categoria, tab_insights_ia = st.tabs([
                    "Visão Geral 📈", 
                    "Análise por Categoria 📚", 
                    "Insights da IA 💡"
                ])

                with tab_visao_geral:
                    st.subheader("Dados dos Posts Analisados")
                    st.dataframe(df_posts, use_container_width=True)

                with tab_analise_categoria:
                    st.subheader("Desempenho Médio por Categoria de Conteúdo")
                    analise_categoria = df_posts_renomeado.groupby('categoria')[['curtidas', 'comentarios']].mean().sort_values(by='curtidas', ascending=False)
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
                    st.markdown(insights)

        except Exception as e:
            st.error(f"Ocorreu um erro inesperado durante a análise: {e}")
else:
    st.info("Configure as opções na barra lateral, carregue seu arquivo e clique em 'Analisar Perfil'.")
