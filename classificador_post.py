# classificar.py

import pandas as pd
import google.generativeai as genai
import time

def classificar_posts_gemini(df_posts_para_classificar, api_key):
    try:
        genai.configure(api_key=api_key)
        # Recomendo usar o modelo mais recente
        model = genai.GenerativeModel('gemini-2.0-flash') 
        
        # O DataFrame já vem filtrado, pegamos as colunas 'id' e 'legenda'
        # que a função fetch_instagram_data nos deu.
        legendas = df_posts_para_classificar[['id', 'legenda']]
        resultados = []
        
        print(f"Iniciando classificação de {len(legendas)} posts...")
        
        for i, (_, row) in enumerate(legendas.iterrows()):
            legenda = row['legenda']
            
            # Imprime o progresso no terminal
            print(f"  Classificando... {i + 1}/{len(legendas)} (Post ID: {row['id']})")

            if pd.isna(legenda) or legenda.strip() == "":
                resultados.append({'id': row['id'], 'categoria': 'Sem legenda'})
                continue
                
            # O seu prompt de classificação (exatamente como estava)
            prompt = f"""
            Analise esta legenda do Instagram e classifique em UMA destas categorias:
            - Institucional: Quando promove ou menciona produtos, serviços, vendas
            - Conteúdo técnico: Quando ensina, explica, dá dicas ou informações educativas  
            - Engajamento: Quando faz perguntas, pede opiniões, incentiva interação
            - Data comemorativa: Quando menciona datas especiais, feriados, celebrações

            Legenda: "{legenda[:500]}" # Limite de caracteres

            Responda APENAS com o nome da categoria, sem explicações, sem pontuação.
            """
            
            try:
                response = model.generate_content(prompt)
                # Limpa a resposta da IA (remove espaços, *, etc.)
                categoria = response.text.strip().replace("*", "") 

                # Sua lógica de validação (exatamente como estava)
                categorias_validas = ['Institucional', 'Conteúdo técnico', 'Engajamento', 'Data comemorativa']
                if categoria not in categorias_validas:
                    if 'institucional' in categoria.lower() or 'venda' in categoria.lower():
                        categoria = 'Institucional'
                    elif 'técnico' in categoria.lower() or 'educati' in categoria.lower() or 'dica' in categoria.lower():
                        categoria = 'Conteúdo técnico'
                    elif 'engajament' in categoria.lower() or 'interaç' in categoria.lower() or 'pergunta' in categoria.lower():
                        categoria = 'Engajamento'
                    elif 'data' in categoria.lower() or 'comemorati' in categoria.lower():
                        categoria = 'Data comemorativa'
                    else:
                        categoria = 'Outros' # Categoria padrão
                
                resultados.append({'id': row['id'], 'categoria': categoria})
                
                # Pausa de 1 segundo para não sobrecarregar a API
                time.sleep(1) 
                print("REQUISIÇÃO DA CLASSIFICAÇÃO")
                
            except Exception as e:
                print(f"    Erro ao classificar post ID {row['id']}: {str(e)[:100]}...")
                print("REQUISIÇÃO QUE TEVE ERRO")
                resultados.append({'id': row['id'], 'categoria': 'Erro na Classificação'})
        
        print("Classificação concluída.")
        return resultados
        
    except Exception as e:
        print(f"Erro fatal na configuração do Gemini: {e}")
        return []
