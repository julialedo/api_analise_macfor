__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
import os
import tempfile
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import (
    TextLoader, 
    PyPDFLoader, 
    Docx2txtLoader,
    UnstructuredPowerPointLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

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

# --- Configuração da Página ---
st.set_page_config(
    page_title="Chatbot com Seu Arquivo",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Chatbot com Seu Arquivo")
st.write("Faça upload de um arquivo e converse com ele!")

# --- Carregamento das Chaves ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    ASTRA_DB_TOKEN = st.secrets["ASTRA_DB_APPLICATION_TOKEN"]
    ASTRA_DB_ENDPOINT = st.secrets["ASTRA_DB_API_ENDPOINT"]
    ASTRA_DB_KEYSPACE = st.secrets.get("ASTRA_DB_KEYSPACE", "default_keyspace")
except Exception as e:
    st.error(f"Erro nas chaves: {str(e)}")
    st.stop()

# --- Funções Auxiliares ---
def carregar_documento(arquivo):
    """Carrega o documento baseado no tipo de arquivo"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1]) as tmp_file:
        tmp_file.write(arquivo.getvalue())
        tmp_file_path = tmp_file.name
    
    try:
        if arquivo.name.endswith('.pdf'):
            loader = PyPDFLoader(tmp_file_path)
        elif arquivo.name.endswith('.docx'):
            loader = Docx2txtLoader(tmp_file_path)
        elif arquivo.name.endswith('.pptx') or arquivo.name.endswith('.ppt'):
            loader = UnstructuredPowerPointLoader(tmp_file_path)
        elif arquivo.name.endswith('.txt'):
            loader = TextLoader(tmp_file_path, encoding='utf-8')
        else:
            loader = TextLoader(tmp_file_path, encoding='utf-8')
        
        documentos = loader.load()
        return documentos
    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {str(e)}")
        return None
    finally:
        os.unlink(tmp_file_path)

def configurar_sistema_rag(documentos, nome_arquivo):  # ✅ CORRIGIDO: Adicionado nome_arquivo
    """Configura o sistema RAG com os documentos carregados"""
    try:
        # Dividir os documentos em chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, 
            chunk_overlap=150
        )
        pedacos = text_splitter.split_documents(documentos)
        
        # Configurar embeddings
        model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name, 
            model_kwargs={'device': 'cpu'}
        )
        
        # Criar vectorstore com nome único
        vectorstore = None
        collection_name = f"file_chat_{hash(nome_arquivo) % 10000}"  # ✅ Nome único
        
        if ASTRA_METHOD == "modern":
            vectorstore = AstraDBVectorStore(
                embedding=embeddings,
                collection_name=collection_name,  # ✅ Nome único
                api_endpoint=ASTRA_DB_ENDPOINT,
                token=ASTRA_DB_TOKEN,
                namespace=ASTRA_DB_KEYSPACE
            )
        elif ASTRA_METHOD == "community":
            vectorstore = AstraDB(
                embedding=embeddings,
                collection_name=collection_name,  # ✅ Nome único
                api_endpoint=ASTRA_DB_ENDPOINT,
                token=ASTRA_DB_TOKEN
            )
        else:  
            vectorstore = Chroma.from_documents(
                documents=pedacos,
                embedding=embeddings,
                persist_directory=f"./chroma_db_{collection_name}"  # ✅ Nome único
            )
    
        # Adicionar documentos ao Astra DB
        if ASTRA_METHOD != "chroma_local":
            try:
                vectorstore.clear()  # Limpar antes de adicionar
            except:
                pass  # Se não existir, continua
            vectorstore.add_documents(pedacos)
        
        # Configurar LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            temperature=0.3,
            google_api_key=GOOGLE_API_KEY
        )
        
        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        
        # Configurar memória
        memory = ConversationBufferMemory(
            memory_key='chat_history',
            return_messages=True
        )
        
        # Criar cadeia de conversação
        conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            return_source_documents=False
        )
        
        return conversation_chain
        
    except Exception as e:  # ✅ CORRIGIDO: except faltando
        st.error(f"Erro ao configurar RAG: {str(e)}")
        return None

# --- Inicialização do Estado ---
if 'file_qa_chain' not in st.session_state:
    st.session_state.file_qa_chain = None

if 'current_file' not in st.session_state:
    st.session_state.current_file = None

if 'file_messages' not in st.session_state:
    st.session_state.file_messages = []

# --- Interface de Upload ---
st.sidebar.header("📤 Upload do Arquivo")

arquivo = st.sidebar.file_uploader(
    "Escolha um arquivo",
    type=['pdf', 'txt', 'docx', 'pptx', 'ppt'],
    help="Suporta PDF, TXT, DOCX, PPTX"
)

# --- Processamento do Arquivo ---
if arquivo is not None:
    file_changed = (st.session_state.current_file != arquivo.name)
    
    if file_changed or st.session_state.file_qa_chain is None:
        with st.spinner("Processando arquivo..."):
            if file_changed:
                st.session_state.file_messages = []  # Limpar chat ao trocar arquivo
            
            documentos = carregar_documento(arquivo)
            
            if documentos:
                st.session_state.file_qa_chain = configurar_sistema_rag(documentos, arquivo.name)
                
                if st.session_state.file_qa_chain:
                    st.session_state.current_file = arquivo.name
                    st.session_state.file_messages = [{
                        "role": "assistant", 
                        "content": f"Arquivo '{arquivo.name}' carregado! Faça suas perguntas."
                    }]

# --- Interface do Chat ---
if st.session_state.file_qa_chain and st.session_state.current_file:  # ✅ CORRIGIDO: file_qa_chain em vez de arquivo_carregado
    for message in st.session_state.file_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(f"Pergunte sobre {st.session_state.current_file}..."):
        st.session_state.file_messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    resposta = st.session_state.file_qa_chain.invoke({
                        'question': f"Baseado no documento: {prompt}"
                    })
                    resposta_texto = resposta['answer']
                    
                    st.markdown(resposta_texto)
                    st.session_state.file_messages.append({
                        "role": "assistant", 
                        "content": resposta_texto
                    })
                except Exception as e:
                    erro_msg = f"Erro: {str(e)}"
                    st.error(erro_msg)

else:
    if not st.session_state.current_file:
        st.info("👆 Faça upload de um arquivo para começar.")

# --- Limpar Estado ---
def limpar_estado():
    st.session_state.file_qa_chain = None
    st.session_state.current_file = None
    st.session_state.file_messages = []

if st.session_state.current_file:
    st.sidebar.divider()
    if st.sidebar.button("🗑️ Limpar Tudo"):
        limpar_estado()
        st.rerun()