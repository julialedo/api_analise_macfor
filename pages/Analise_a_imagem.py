__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
import os
from PIL import Image
import io
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA

# --- 1. Configuração da Página ---
st.set_page_config(
    page_title="Chatbot Coca-Cola (Análise de Imagem)",
    page_icon="🥤",
    layout="wide"
)

# --- 2. Carregamento da API Key ---
os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])


st.title("🖼️ Analisador de Imagens")
st.write("Envie uma imagem e faça uma pergunta sobre ela.")
st.divider()

# --- 3. Inicialização do Estado da Sessão ---
if "image_messages" not in st.session_state:
    st.session_state.image_messages = []
if "current_image" not in st.session_state:
    st.session_state.current_image = None


# --- 4. Widget para Upload de Imagem ---
uploaded_file = st.file_uploader(
    "📤 Escolha uma imagem para analisar",
    type=["jpg", "jpeg", "png", "webp"],
    help="Selecione uma imagem de propaganda, produto ou material da Coca-Cola"
)

# ---  Processar o upload da imagem
if uploaded_file is not None:
    try:
        # Abre a imagem usando a biblioteca Pillow
        image = Image.open(uploaded_file)
        # Armazena a imagem na sessão
        st.session_state.current_image = image
        
        # Exibe a imagem no app
        st.image(image, caption="✅ Imagem Carregada com Sucesso", width='stretch')
        
        # Mensagem inicial se for a primeira imagem
        if not st.session_state.image_messages:
            st.session_state.image_messages.append({
                "role": "assistant", 
                "content": "Imagem carregada! Agora faça uma pergunta sobre ela. Exemplo: 'Esta propaganda segue os padrões da marca Coca-Cola?'"
            })
            
    except Exception as e:
        st.error(f"Erro ao carregar a imagem: {e}")
else:
    st.info("👆 Por favor, carregue uma imagem para começar a análise.")


# --- 5. Exibir Histórico de Mensagens ---
for message in st.session_state.image_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. Campo para Perguntas sobre a Imagem ---
if st.session_state.current_image:
    prompt_usuario = st.chat_input(
        "💬 Digite sua pergunta sobre a imagem...",
        key="image_prompt_input"
    )


    if prompt_usuario:
        # Adiciona pergunta ao histórico
        st.session_state.image_messages.append({"role": "user", "content": prompt_usuario})
        
        # Exibe a pergunta do usuário
        with st.chat_message("user"):
            st.markdown(prompt_usuario)
        
        # Processa a análise da imagem
        with st.chat_message("assistant"):
            with st.spinner("🔍 Analisando imagem..."):
                try:
                    # Configura o modelo multimodal do Gemini
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    # Cria o prompt multimodal (texto + imagem)
                    prompt_com_instrucao = f"Responda em português: {prompt_usuario}"
                    prompt_multimodal = [prompt_com_instrucao, st.session_state.current_image]
                    
                    # Gera a análise
                    response = model.generate_content(prompt_multimodal)
                     # Exibe a resposta
                    st.markdown(response.text)
                    
                    # Adiciona resposta ao histórico
                    st.session_state.image_messages.append({
                        "role": "assistant", 
                        "content": response.text
                    })
                    
                except Exception as e:
                    error_msg = f"❌ Ocorreu um erro durante a análise: {str(e)}"
                    st.error(error_msg)
                    st.session_state.image_messages.append({
                        "role": "assistant", 
                        "content": error_msg
                    })

# --- 6. Botão para Limpar Conversa ---
if st.session_state.image_messages:
    if st.button("🗑️ Limpar Conversa", type="secondary"):
        st.session_state.image_messages = []
        if st.session_state.current_image:
            # Mantém a imagem mas limpa o chat
            st.session_state.image_messages.append({
                "role": "assistant", 
                "content": "Conversa limpa! A imagem ainda está carregada. Faça uma nova pergunta."
            })
        st.rerun()