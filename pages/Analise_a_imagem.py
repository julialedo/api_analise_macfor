__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
import os
from PIL import Image
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# --- Detecção do método Astra DB ---
ASTRA_METHOD = "unknown"

try:
    from langchain_astradb import AstraDBVectorStore
    ASTRA_METHOD = "modern"
except ImportError:
    try:
        from langchain_community.vectorstores import AstraDB
        ASTRA_METHOD = "community"
    except ImportError:
        from langchain_community.vectorstores import Chroma
        ASTRA_METHOD = "chroma_local"

# --- 1. Configuração da Página ---
st.set_page_config(
    page_title="Chatbot Coca-Cola (Análise de Imagem)",
    page_icon="🥤",
    layout="wide"
)

st.title("🖼️ Analisador de Imagens Coca-Cola")
st.write("Envie uma imagem e faça uma pergunta sobre ela usando as informações da Coca-Cola.")
st.divider()

# --- 2. Carregamento das Chaves ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    ASTRA_DB_TOKEN = st.secrets["ASTRA_DB_APPLICATION_TOKEN"]
    ASTRA_DB_ENDPOINT = st.secrets["ASTRA_DB_API_ENDPOINT"]
    ASTRA_DB_KEYSPACE = st.secrets.get("ASTRA_DB_KEYSPACE", "default_keyspace")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"❌ Erro nas chaves: {str(e)}")
    st.stop()

# --- 3. Sistema RAG para Coca-Cola ---
@st.cache_resource(show_spinner="🚀 Carregando informações da Coca-Cola...")
def configurar_sistema_rag():
    try:
        # Verificar e criar arquivo se necessário
        if not os.path.exists("dados_coca_cola.txt"):
            with open("dados_coca_cola.txt", "w", encoding="utf-8") as f:
                f.write("Informações sobre a Coca-Cola.\nA Coca-Cola foi inventada em 1886.")
            st.info("📄 Arquivo de exemplo criado")

        # Carregar documentos
        loader = TextLoader("dados_coca_cola.txt", encoding="utf-8")
        documentos = loader.load()
        
        # Processar texto
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        pedacos = text_splitter.split_documents(documentos)

        # Configurar embeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )

        # Conexão com vectorstore
        vectorstore = None
        
        if ASTRA_METHOD == "modern":
            vectorstore = AstraDBVectorStore(
                embedding=embeddings,
                collection_name="coca_cola_imagens",
                api_endpoint=ASTRA_DB_ENDPOINT,
                token=ASTRA_DB_TOKEN,
                namespace=ASTRA_DB_KEYSPACE
            )
        elif ASTRA_METHOD == "community":
            vectorstore = AstraDB(
                embedding=embeddings,
                collection_name="coca_cola_imagens",
                api_endpoint=ASTRA_DB_ENDPOINT,
                token=ASTRA_DB_TOKEN
            )
        else:
            vectorstore = Chroma.from_documents(
                documents=pedacos,
                embedding=embeddings,
                persist_directory="./chroma_db_imagens"
            )

        # Adicionar documentos ao Astra DB
        if ASTRA_METHOD != "chroma_local":
            try:
                vectorstore.add_documents(pedacos)
            except:
                pass

        # Configurar LLM e memória
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.3,
            google_api_key=GOOGLE_API_KEY
        )
        
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
            memory=memory
        )

        return qa_chain

    except Exception as e:
        st.error(f"💥 Erro ao configurar sistema: {str(e)}")
        return None

# --- 4. Inicializar sistema RAG ---
qa_chain = configurar_sistema_rag()

# --- 5. Inicialização do Estado da Sessão ---
if "image_messages" not in st.session_state:
    st.session_state.image_messages = []
if "current_image" not in st.session_state:
    st.session_state.current_image = None

# --- 6. Widget para Upload de Imagem ---
uploaded_file = st.file_uploader(
    "📤 Escolha uma imagem para analisar",
    type=["jpg", "jpeg", "png", "webp"],
    help="Selecione uma imagem de propaganda, produto ou material da Coca-Cola"
)

# --- 7. Processar o upload da imagem ---
if uploaded_file is not None:
    try:
        image = Image.open(uploaded_file)
        st.session_state.current_image = image
        
        st.image(image, caption="✅ Imagem Carregada com Sucesso", use_column_width=True)
        
        if not st.session_state.image_messages:
            st.session_state.image_messages.append({
                "role": "assistant", 
                "content": "Imagem carregada! Agora faça uma pergunta sobre ela. Exemplo: 'Esta propaganda segue os padrões da marca Coca-Cola?'"
            })
            
    except Exception as e:
        st.error(f"Erro ao carregar a imagem: {e}")
else:
    st.info("👆 Por favor, carregue uma imagem para começar a análise.")

# --- 8. Exibir Histórico de Mensagens ---
for message in st.session_state.image_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 9. Análise de Imagem com Contexto da Coca-Cola ---
if st.session_state.current_image and qa_chain:
    prompt_usuario = st.chat_input("💬 Digite sua pergunta sobre a imagem...")

    if prompt_usuario:
        # Adiciona pergunta ao histórico
        st.session_state.image_messages.append({"role": "user", "content": prompt_usuario})
        
        with st.chat_message("user"):
            st.markdown(prompt_usuario)
        
        with st.chat_message("assistant"):
            with st.spinner("🔍 Analisando imagem com base nas informações da Coca-Cola..."):
                try:
                    # Primeiro: Analisar a imagem com Gemini Vision
                    model_vision = genai.GenerativeModel('gemini-1.5-flash')
                    prompt_analise_imagem = f"""
                    Analise esta imagem e descreva o que você vê. 
                    Pergunta do usuário: {prompt_usuario}
                    """
                    
                    response_imagem = model_vision.generate_content([prompt_analise_imagem, st.session_state.current_image])
                    descricao_imagem = response_imagem.text
                    
                    # Segundo: Consultar o sistema RAG com a descrição da imagem + pergunta original
                    pergunta_com_contexto = f"""
                    Com base nesta análise de imagem: "{descricao_imagem}"
                    
                    E com base nas informações sobre a Coca-Cola, responda:
                    {prompt_usuario}
                    
                    Se a pergunta for sobre a imagem, relacione com as informações da marca Coca-Cola.
                    """
                    
                    resposta_rag = qa_chain.invoke({"question": pergunta_com_contexto})
                    resposta_final = resposta_rag["answer"]
                    
                    # Exibir a resposta
                    st.markdown(resposta_final)
                    
                    # Adicionar ao histórico
                    st.session_state.image_messages.append({
                        "role": "assistant", 
                        "content": resposta_final
                    })
                    
                except Exception as e:
                    error_msg = f"❌ Erro na análise: {str(e)}"
                    st.error(error_msg)
                    st.session_state.image_messages.append({
                        "role": "assistant", 
                        "content": error_msg
                    })

elif st.session_state.current_image and not qa_chain:
    st.warning("⚠️ Sistema de informações da Coca-Cola não carregado. A análise será apenas visual.")

# --- 10. Botão para Limpar Conversa ---
if st.session_state.image_messages:
    if st.button("🗑️ Limpar Conversa", type="secondary"):
        st.session_state.image_messages = []
        if st.session_state.current_image:
            st.session_state.image_messages.append({
                "role": "assistant", 
                "content": "Conversa limpa! A imagem ainda está carregada. Faça uma nova pergunta."
            })
        st.rerun()

# --- 11. Sidebar Informações ---
with st.sidebar:
    st.header("🔧 Status do Sistema")
    st.info(f"""
    **Método:** {ASTRA_METHOD}
    **Sistema RAG:** {'✅ Carregado' if qa_chain else '❌ Erro'}
    **Imagem:** {'✅ Carregada' if st.session_state.current_image else '❌ Nenhuma'}
    """)