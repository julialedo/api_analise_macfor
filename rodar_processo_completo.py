# rodar_processo_completo.py
import pandas as pd
import sys
import os
import time
import random
from datetime import datetime
import pytz # Para lidar com datas

# --- Imports do Instagram ---
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

# --- Imports dos nossos módulos ---
from supabase_utils import (
    init_connection, 
    save_posts_to_supabase,
    fetch_instagram_data, 
    update_post_classification
)
from classificador_post import classificar_posts_gemini
from config import (
    GEMINI_API_KEY, 
    SEU_NOME_DE_USUARIO, 
    SUA_SENHA
)

# --- Configurações do Script ---
ARQUIVO_SESSAO = "sessao_instagrapi.json"
# Quantidade de posts recentes para verificar.
# Aumente este número se quiser buscar mais posts (ex: 50)
QUANTIDADE_DE_POSTS = 20 



def login_instagram(username, password, session_file):
    """Cuida do login no Instagram e retorna o cliente."""
    print("Iniciando login no Instagram...")
    cl = Client()
    cl.delay_range = [2, 5]
    
    try:
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            print("Sessão do Instagram carregada.")
            cl.login(username, password)
            cl.get_timeline_feed() # Verifica se a sessão é válida
            print("Login via sessão bem-sucedido.")
        else:
            raise FileNotFoundError # Força o login padrão
    
    except (FileNotFoundError, LoginRequired):
        print("Sessão não encontrada ou expirada. Fazendo login com usuário e senha...")
        cl.login(username, password)
        cl.dump_settings(session_file)
        print("Nova sessão salva.")
    except Exception as e:
        print(f"Erro no login do Instagram: {e}")
        return None
        
    return cl


def coletar_posts_instagram(cl, target_username, data_inicio_str, data_fim_str):
    """
    Coleta posts de um usuário dentro de um período e retorna um DataFrame.
    """
    print(f"Iniciando coleta para @{target_username} de {data_inicio_str} até {data_fim_str}")
    
    lista_de_posts = []
    posts_ids_vistos = set()
    
    try:
        user_id = cl.user_id_from_username(target_username)
        
        # Converte as datas para datetime com fuso horário
        timezone = pytz.UTC
        data_inicio_dt = timezone.localize(datetime.strptime(data_inicio_str, "%Y-%m-%d"))
        data_fim_dt = timezone.localize(datetime.strptime(data_fim_str, "%Y-%m-%d") + pd.Timedelta(days=1))
        
        # Coleta os posts
        medias = cl.user_medias_v1(user_id, amount=100) # Coleta os 100 posts mais recentes
        
        if not medias:
            print("Nenhum post encontrado na coleta.")
            return pd.DataFrame(lista_de_posts)

        print(f"Verificando {len(medias)} posts recentes...")
        
        for media in medias:
            if media.pk in posts_ids_vistos:
                continue
            posts_ids_vistos.add(media.pk)
            
            # Verifica se o post está dentro do período desejado
            if data_inicio_dt <= media.taken_at <= data_fim_dt:
                post_data = {
                    'data': media.taken_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'id': media.pk, # 'id' que vira 'post_pk'
                    'num': media.media_type,
                    'curtidas': media.like_count,
                    'comentarios': media.comment_count,
                    'legenda': (media.caption_text or ""), # Legenda completa
                    'link': f"https://www.instagram.com/p/{media.code}/",
                    'lote': 1 # Lote fixo
                }
                lista_de_posts.append(post_data)
            elif media.taken_at < data_inicio_dt:
                # Se o post é mais antigo que o período, podemos parar
                print("Posts mais antigos que o período de início encontrados. Parando a coleta.")
                break
            
            time.sleep(random.uniform(0.5, 1.5)) # Pausa leve

        print(f"Encontrados {len(lista_de_posts)} posts no período selecionado.")
        return pd.DataFrame(lista_de_posts)

    except Exception as e:
        print(f"Erro durante a coleta: {e}")
        return pd.DataFrame(lista_de_posts)


def main():
    print("--- INICIANDO PROCESSO COMPLETO (COLETA E CLASSIFICAÇÃO) ---")
    
    # --- ETAPA 1: OBTER O USUÁRIO-ALVO ---
    if len(sys.argv) < 2:
        print("❌ ERRO: Você esqueceu de passar o nome do usuário.")
        print(f"Uso correto: python {sys.argv[0]} nome_do_usuario")
        return
    
    USUARIO_ALVO = sys.argv[1].replace('@', '')
    print(f"🎯 Usuário alvo definido: @{USUARIO_ALVO}")

    # --- ETAPA 2: CONECTAR AO SUPABASE ---
    print(f"\n[ETAPA 1/5] Conectando ao Supabase...")
    supabase_client = init_connection()
    if not supabase_client: return
    print("✅ Conexão com o Supabase bem-sucedida!")

    # --- ETAPA 3: LOGIN E COLETA DO INSTAGRAM ---
    print(f"\n[ETAPA 2/5] Conectando ao Instagram...")
    cl_instagram = login_instagram(SEU_NOME_DE_USUARIO, SUA_SENHA, ARQUIVO_SESSAO)
    if not cl_instagram: return
    
    df_novos_posts = coletar_posts_instagram(cl_instagram, USUARIO_ALVO, DATA_INICIO, DATA_FIM)

    # --- ETAPA 4: SALVAR NOVOS POSTS NO BANCO ---
    print(f"\n[ETAPA 3/5] Salvando novos posts no Supabase...")
    if not df_novos_posts.empty:
        save_posts_to_supabase(supabase_client, df_novos_posts, USUARIO_ALVO)
    else:
        print("ℹ️ Nenhum post novo para salvar.")

    # --- ETAPA 5: BUSCAR E CLASSIFICAR POSTS PENDENTES ---
    print(f"\n[ETAPA 4/5] Buscando posts pendentes de classificação...")
    df_todos_posts = fetch_instagram_data(supabase_client, USUARIO_ALVO)
    
    if df_todos_posts is None or df_todos_posts.empty:
        print(f"Nenhum post encontrado para @{USUARIO_ALVO} no banco.")
        return

    # Filtra posts onde 'tipo' é Nulo OU 'Erro na Classificação'
    df_para_classificar = df_todos_posts[
        (df_todos_posts['tipo'].isnull()) | 
        (df_todos_posts['tipo'] == 'Erro na Classificação')
    ]
    
    if df_para_classificar.empty:
        print("✅ Todos os posts deste usuário já estão classificados.")
        print("--- PROCESSO CONCLUÍDO ---")
        return

    print(f"Encontrados {len(df_para_classificar)} posts que precisam de classificação.")

    # --- ETAPA 6: CLASSIFICAR COM IA ---
    print(f"\n[ETAPA 5/5] Enviando {len(df_para_classificar)} posts para a IA (Gemini)...")
    classificacoes = classificar_posts_gemini(df_para_classificar, GEMINI_API_KEY)
    
    if not classificacoes:
        print("❌ A classificação falhou ou não retornou resultados.")
        return

    # --- ETAPA 7: SALVAR CLASSIFICAÇÕES NO BANCO ---
    update_post_classification(supabase_client, classificacoes)
    
    print("\n--- PROCESSO COMPLETO CONCLUÍDO ---")

if __name__ == "__main__":
    main()