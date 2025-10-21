# test_save.py

import pandas as pd
from datetime import datetime

# Importa as funções que você quer testar do seu arquivo supabase_utils
from supabase_utils import init_connection, save_posts_to_supabase

def main():
    """Função principal para executar o teste."""
    print("--- INICIANDO TESTE DE SALVAMENTO NO SUPABASE ---")

    # 1. Criar um DataFrame fictício
    #    As colunas devem ter os mesmos nomes que o seu script de coleta gera
    #    ('data', 'id', 'curtidas', etc.)
    post_ficticio = {
        'data': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        'id': ["99999999999999999"],  # Use um ID único e improvável para o teste
        'num': [1],  # 1 para Foto, 2 para Vídeo, 8 para Carrossel
        'curtidas': [123],
        'comentarios': [45],
        'legenda': ["Este é um post de teste gerado automaticamente."],
        'link': ["https://instagram.com/p/teste123"]
    }
    df_ficticio = pd.DataFrame(post_ficticio)

    print("\n[1] DataFrame fictício criado:")
    print(df_ficticio)

    # 2. Conectar ao Supabase
    print("\n[2] Conectando ao Supabase...")
    try:
        supabase_client = init_connection()
        if supabase_client:
            print("✅ Conexão com o Supabase bem-sucedida!")
        else:
            print("❌ Falha ao conectar. Verifique as credenciais no config.py.")
            return # Encerra o script se não conseguir conectar
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
        return

    # 3. Chamar a função para salvar os dados
    #    Vamos salvar este post para um usuário de teste chamado 'teste_perfil'
    username_teste = "perfil_de_teste"
    print(f"\n[3] Chamando a função save_posts_to_supabase para o usuário '{username_teste}'...")
    
    save_posts_to_supabase(supabase_client, df_ficticio, username_teste)

    print("\n--- TESTE CONCLUÍDO ---")
    print("Verifique a tabela 'posts' no seu dashboard do Supabase para confirmar se o registro foi inserido.")


# Executa a função main quando o script é rodado diretamente
if __name__ == "__main__":
    main()