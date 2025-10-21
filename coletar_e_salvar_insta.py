# coletar_e_salvar.py

import pandas as pd
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
import os

# --- [ETAPA 1] IMPORTAR AS FERRAMENTAS ---

# Importa as funções do Supabase que você criou e testou
from supabase_utils import init_connection, save_posts_to_supabase

# Importa suas credenciais e configurações
# Lembre-se: este arquivo DEVE estar na pasta raiz, NÃO dentro de .github
try:
    from config import (
        SEU_NOME_DE_USUARIO, SUA_SENHA, 
        SUPABASE_URL, SUPABASE_KEY
    )
except ImportError:
    print("="*50)
    print("ERRO CRÍTICO: Não foi possível encontrar o arquivo 'config.py'.")
    print("Verifique se o arquivo está na pasta raiz e com o nome correto.")
    print("="*50)
    exit() # Interrompe o script se a configuração não for encontrada

# --- Configuração da Coleta ---
USUARIO_ALVO = "somosbroto" 
QUANTIDADE_DE_POSTS = 20 # Quantos posts você quer buscar
ARQUIVO_SESSAO = "sessao_instagrapi.json"


def main():
    print("--- INICIANDO PROCESSO DE COLETA E SALVAMENTO ---")
    
    # --- [ETAPA 2] CONECTAR AO SUPABASE ---
    print("\n[ETAPA 2/4] Conectando ao Supabase...")
    try:
        supabase_client = init_connection()
        print("✅ Conexão com o Supabase bem-sucedida!")
    except Exception as e:
        print(f"❌ FALHA AO CONECTAR AO SUPABASE: {e}")
        return

    # --- [ETAPA 3] CONECTAR E EXTRAIR DO INSTAGRAM ---
    print("\n[ETAPA 3/4] Conectando ao Instagram...")
    cl = Client()
    
    try:
        if os.path.exists(ARQUIVO_SESSAO):
            cl.load_settings(ARQUIVO_SESSAO)
            print("Sessão do Instagram carregada.")
            cl.login(SEU_NOME_DE_USUARIO, SUA_SENHA)
            cl.get_timeline_feed() # Verifica se a sessão é válida
            print("Login via sessão bem-sucedido.")
        else:
            raise FileNotFoundError # Força o login padrão

    except (FileNotFoundError, LoginRequired):
        print("Sessão não encontrada ou expirada. Fazendo login com usuário e senha...")
        cl.login(SEU_NOME_DE_USUARIO, SUA_SENHA)
        cl.dump_settings(ARQUIVO_SESSAO)
        print("Nova sessão salva.")

    print(f"\nBuscando os últimos {QUANTIDADE_DE_POSTS} posts de @{USUARIO_ALVO}...")
    
    lista_de_posts = [] # Lista para guardar os dicionários de posts

    try:
        user_id = cl.user_id_from_username(USUARIO_ALVO)
        medias = cl.user_medias(user_id, QUANTIDADE_DE_POSTS)
        
        print(f"--- DADOS EXTRAÍDOS ({len(medias)} posts encontrados) ---")

        for media in medias:
            # CORREÇÃO DA LEGENDA: Salva a legenda completa
            legenda_completa = media.caption_text or "" # Pega o texto completo ou uma string vazia

            # Criar um dicionário com os nomes de coluna exatos
            # que a sua função 'save_posts_to_supabase' espera
            post_data = {
                'data': media.taken_at.strftime("%Y-%m-%d %H:%M:%S"),
                'id': media.pk, # 'id' no seu teste era o 'post_pk'
                'num': media.media_type, # 'num' no seu teste era o 'media_type_id'
                'curtidas': media.like_count,
                'comentarios': media.comment_count,
                'legenda': legenda_completa,
                'link': f"https://www.instagram.com/p/{media.code}/"
            }
            lista_de_posts.append(post_data)

    except Exception as e:
        print(f"Ocorreu um erro ao buscar os posts: {e}")
        return

    # --- [ETAPA 4] SALVAR NO SUPABASE ---
    print("\n[ETAPA 4/4] Salvando dados no Supabase...")
    
    if not lista_de_posts:
        print("Nenhum post foi encontrado para salvar.")
        return

    # Converter a lista de dicionários em um DataFrame
    df_para_salvar = pd.DataFrame(lista_de_posts)
    
    # Chamar sua função de salvamento testada!
    save_posts_to_supabase(supabase_client, df_para_salvar, USUARIO_ALVO)
    
    print("\n--- PROCESSO CONCLUÍDO ---")


# Executa a função principal
if __name__ == "__main__":
    main()