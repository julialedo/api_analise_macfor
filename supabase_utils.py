# supabase_utils.py

import streamlit as st

import pandas as pd

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY # Importando do config.py



@st.cache_resource

def init_connection() -> Client:

    # Usando as variáveis importadas do config.py

    return create_client(SUPABASE_URL, SUPABASE_KEY)



def fetch_instagram_data(supabase_client: Client, target_username: str):

    """

    Busca os dados da tabela especificada no Supabase e retorna como um DataFrame.



    Args:

        supabase_client (Client): O cliente de conexão do Supabase.

        target_username (str): O nome de usuário do Instagram a ser buscado.

    Returns:

        pd.DataFrame or None: Retorna um DataFrame com os dados se for bem-sucedido,

                              ou None se a tabela estiver vazia ou ocorrer um erro.

    """

    try:

        print(f"🔍 Buscando dados para o perfil '{target_username}' no Supabase...")

        # A sintaxe é: cliente.table('nome_da_tabela').select('*').execute()

        #procura filtrando pelo username (PODE SER TROCADO)

        response = (

            supabase_client.table("posts")

            .select("*")

            .eq("username", target_username)

            .order("published_at", desc=True)  # Ordena pelos mais recentes

            .execute()

        )

       

        # A resposta da API contém os dados dentro de um atributo 'data'

        dados = response.data

        if not dados:

            st.warning(f"Nenhum dado encontrado na tabela '{target_username}'.")

            return None

       

        # Converte a lista de dicionários em um DataFrame do Pandas

        df = pd.DataFrame(dados)



        # --- TRADUÇÃO DAS COLUNAS (Passo Crucial) ---

        # Renomeia as colunas do banco para os nomes que o app Streamlit espera

        mapeamento_colunas = {

            'published_at': 'data',

            'media_num': 'num',

            'like_count': 'curtidas',

            'comment_count': 'comentarios',

            'caption': 'legenda',

            'media_url': 'link',

            'post_pk': 'id'

            # A coluna 'tipo' já tem o nome correto

        }

        df_traduzido = df.rename(columns=mapeamento_colunas)



        print(f"✅ {len(df_traduzido)} registros encontrados e prontos para análise.")

        return df_traduzido



    except Exception as e:

        st.error(f"❌ Erro ao buscar dados do Supabase: {e}")

        return None







# -----------------------------------------------------------------------------

# 2. FERRAMENTA PARA SALVAR DADOS (USADA PELO SCRIPT DE COLETA)

# -----------------------------------------------------------------------------

def save_posts_to_supabase(supabase_client: Client, df: pd.DataFrame, target_username: str):

    """Prepara e salva um DataFrame de posts na tabela do Supabase."""

    if df.empty:

        print("ℹ️ DataFrame vazio, nada para salvar no Supabase.")

        return



    df['username'] = target_username

   

    mapeamento_colunas = {

        'data': 'published_at',

        'num': 'media_num',

        'curtidas': 'like_count',

        'comentarios': 'comment_count',

        'legenda': 'caption',

        'link': 'media_url',

        'id': 'post_pk',

    }

    df_renomeado = df.rename(columns=mapeamento_colunas)

    df_renomeado['tipo'] = None



    colunas_da_tabela = [

        'username', 'post_pk', 'published_at', 'media_num', 'like_count',

        'comment_count', 'caption', 'media_url', 'tipo'

    ]

    # Filtra apenas pelas colunas que existem no DataFrame para evitar erros

    colunas_existentes = [col for col in colunas_da_tabela if col in df_renomeado.columns]

    df_final = df_renomeado[colunas_existentes]



    dados_para_salvar = df_final.to_dict(orient='records')

   

    try:

        print(f"📦 Enviando {len(dados_para_salvar)} registros para o Supabase...")

        response = supabase_client.table("posts").upsert(

            dados_para_salvar,

            on_conflict="post_pk"

        ).execute()

       

        print("✅ Dados salvos com sucesso no Supabase!")

    except Exception as e:

        print(f"❌ Erro ao salvar no Supabase: {e}")