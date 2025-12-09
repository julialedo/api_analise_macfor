import pandas as pd
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
import os
import sys

# Importa as funções do Supabase
try:
    from supabase_utils import init_connection, save_posts_to_supabase
except ImportError:
    # Se rodado sozinho, estas funções não são críticas, mas avisa
    print("AVISO: Rodando em modo standalone. Funções do Supabase não encontradas.")
    init_connection = None
    save_posts_to_supabase = None

# Importa as credenciais (assume config.py ou app_config.py)
try:
    from config import SEU_NOME_DE_USUARIO, SUA_SENHA
except ImportError:
    try:
        from config import SEU_NOME_DE_USUARIO, SUA_SENHA
    except ImportError:
        print("ERRO CRÍTICO: Não foi possível encontrar as credenciais do Instagram (SEU_NOME_DE_USUARIO, SUA_SENHA) no arquivo de configuração.
        # Define valores padrão para evitar que o import falhe no Streamlit
        SEU_NOME_DE_USUARIO = "placeholder_user"
        SUA_SENHA = "placeholder_password"


ARQUIVO_SESSAO = "sessao_instagrapi.json"

# --- FUNÇÃO 1: Login ---
def login_instagram():
    """
    Realiza o login no Instagram usando credenciais e sessão.
    Retorna o objeto 'Client' logado ou None em caso de erro.
    """
    print("Iniciando login no Instagram...")
    cl = Client()
    cl.delay_range = [2, 5]

    try:
        if os.path.exists(ARQUIVO_SESSAO):
            cl.load_settings(ARQUIVO_SESSAO)
            print("Sessão do Instagram carregada.")
            cl.login(SEU_NOME_DE_USUARIO, SUA_SENHA)
            # cl.get_timeline_feed() # Desativado temporariamente para acelerar testes
            print("Login via sessão bem-sucedido.")
        else:
            raise FileNotFoundError # Força o login padrão

    except (FileNotFoundError, LoginRequired, Exception) as e: # Captura erros mais genéricos no login
        print(f"Sessão inválida ou erro ({e}). Fazendo login com usuário e senha...")
        try:
            cl.login(SEU_NOME_DE_USUARIO, SUA_SENHA)
            cl.dump_settings(ARQUIVO_SESSAO)
            print("Nova sessão salva.")
        except Exception as login_err:
             print(f"❌ ERRO GRAVE NO LOGIN DO INSTAGRAM: {login_err}")
             return None # Retorna None se o login falhar

    return cl

# --- FUNÇÃO 2: Coleta ---
def coletar_posts_instagram(cl: Client, target_username: str, amount: int):
    """
    Coleta os 'amount' posts mais recentes de um usuário.
    Retorna um DataFrame pandas com os dados ou um DataFrame vazio em caso de erro.
    """
    if not isinstance(cl, Client):
        print("❌ Erro: Objeto Client do Instagram inválido.")
        return pd.DataFrame() # Retorna DataFrame vazio

    print(f"\nBuscando os últimos {amount} posts de @{target_username}...")
    lista_de_posts = []

    try:
        user_id = cl.user_id_from_username(target_username)
        medias = cl.user_medias(user_id, amount)
        print(f"--- DADOS EXTRAÍDOS ({len(medias)} posts encontrados) ---")

        for media in medias:
            legenda_completa = media.caption_text or ""
            post_data = {
                'data': media.taken_at.strftime("%Y-%m-%d %H:%M:%S"),
                'id': media.pk,
                'num': media.media_type,
                'curtidas': media.like_count,
                'comentarios': media.comment_count,
                'legenda': legenda_completa,
                'link': f"https://www.instagram.com/p/{media.code}/"
            }
            lista_de_posts.append(post_data)

    except Exception as e:
        print(f"❌ Ocorreu um erro ao buscar os posts: {e}")
        # Retorna o que conseguiu coletar até agora ou um DF vazio
        return pd.DataFrame(lista_de_posts)

    return pd.DataFrame(lista_de_posts)


# --- BLOCO PARA TESTE (se rodar o script diretamente) ---
if __name__ == "__main__":
    print("--- INICIANDO TESTE STANDALONE DO COLETOR ---")
    if len(sys.argv) < 2:
        print("❌ ERRO: Passe o nome do usuário como argumento.")
        print(f"Uso: python {sys.argv[0]} nome_do_usuario [quantidade]")
        sys.exit()

    USUARIO_ALVO_TESTE = sys.argv[1].replace('@', '')
    QUANTIDADE_TESTE = int(sys.argv[2]) if len(sys.argv) > 2 else 5 # Pega 5 posts por padrão

    print(f"🎯 Usuário alvo: @{USUARIO_ALVO_TESTE}")
    print(f"🔢 Quantidade: {QUANTIDADE_TESTE}")

    # 1. Tenta conectar ao Supabase (opcional para este teste)
    if init_connection:
        try:
            supabase_client = init_connection()
            print("✅ Conexão Supabase OK (para salvar).")
        except Exception as e:
            print(f"⚠️ Aviso: Falha ao conectar ao Supabase: {e}. Os dados não serão salvos.")
            supabase_client = None
    else:
        supabase_client = None
        print("⚠️ Aviso: Funções do Supabase não disponíveis. Os dados não serão salvos.")


    # 2. Login no Instagram
    client_insta = login_instagram()

    # 3. Coleta de Posts
    if client_insta:
        df_posts_coletados = coletar_posts_instagram(client_insta, USUARIO_ALVO_TESTE, QUANTIDADE_TESTE)

        if not df_posts_coletados.empty:
            print("\n--- Posts Coletados (DataFrame) ---")
            print(df_posts_coletados.head()) # Mostra os primeiros posts

            # 4. Tenta salvar no Supabase (se conectado)
            if supabase_client and save_posts_to_supabase:
                 print("\n--- Tentando salvar no Supabase ---")
                 save_posts_to_supabase(supabase_client, df_posts_coletados, USUARIO_ALVO_TESTE)
            else:
                 print("\n--- Supabase não conectado. Salvamento ignorado. ---")

        else:
            print("\nNenhum post foi coletado.")
    else:
        print("\nNão foi possível fazer login no Instagram. Coleta cancelada.")

    print("\n--- TESTE STANDALONE CONCLUÍDO ---")
