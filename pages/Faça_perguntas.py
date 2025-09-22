# --- 0. Correção Essencial para Implementação ---
# Esta secção é uma solução alternativa para um problema com a biblioteca
# de base de dados (SQLite) que o ChromaDB utiliza em ambientes como o Streamlit Cloud.
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# --- 1. Importações ---
import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
# Importamos a cadeia correta e o objeto de memória
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# --- 2. Configuração da Página ---
st.set_page_config(
    page_title="Chatbot Coca-Cola",
    page_icon="🥤",
    layout="wide"
)

st.title("🥤 Chatbot Coca-Cola")
st.write("Este chatbot recorda o contexto da conversa para responder a perguntas de seguimento.")
st.divider()

# --- 3. Carregamento da Chave da API ---
try:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
except (KeyError, TypeError):
    st.error("🔑 A chave 'GOOGLE_API_KEY' não foi encontrada nos segredos da sua app Streamlit.")
    st.stop()


# --- 4. Função para Configurar o Sistema RAG (com Cache) ---
@st.cache_resource(show_spinner="A configurar o sistema de consulta...")
def configurar_sistema_rag():
    # st.toast foi movido para fora desta função para corrigir o erro de cache.
    try:
        loader = TextLoader("dados_coca_cola.txt", encoding="utf-8")
        documentos = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=150)
        pedacos = text_splitter.split_documents(documentos)
        model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        embeddings_model = HuggingFaceEmbeddings(model_name=model_name, model_kwargs={'device': 'cpu'})
        vectorstore = Chroma.from_documents(documents=pedacos, embedding=embeddings_model)
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3, convert_system_message_to_human=True)
        retriever = vectorstore.as_retriever()

        # Criamos um objeto de memória para guardar o histórico
        # A 'memory_key' diz à cadeia onde encontrar o histórico.
        # 'return_messages=True' garante que ele seja devolvido no formato correto.
        memory = ConversationBufferMemory(
            memory_key='chat_history',
            return_messages=True
        )

        # Usamos a ConversationalRetrievalChain em vez da RetrievalQA
        # Esta cadeia é projetada para usar tanto um retriever (para pesquisar nos docs)
        # quanto uma memória (para se lembrar da conversa).
        conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory
        )
        return conversation_chain
    except Exception as e:
        st.error(f"Erro ao configurar RAG: {str(e)}")
        return None

# --- 5. Inicialização e Interface do Chat ---
# CORREÇÃO: Movemos o st.toast para fora da função em cache.
# Ele só será exibido na primeira vez que a página carregar.
if 'system_ready' not in st.session_state:
    st.toast("A preparar o sistema de consulta de documentos...", icon="🔨")
    st.session_state.system_ready = True

qa_chain = configurar_sistema_rag()


if qa_chain:
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar hoje com as diretrizes da Coca-Cola?"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Qual é a fonte oficial da Coca-Cola?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("A consultar as diretrizes e a pensar..."):
                # A forma de invocar a cadeia muda um pouco.
                # A cadeia agora gere o histórico internamente através do objeto 'memory'.
                # A resposta vem na chave 'answer'.
                resposta = qa_chain.invoke({'question': prompt})
                resposta_texto = resposta['answer']

                st.markdown(resposta_texto)
                st.session_state.messages.append({"role": "assistant", "content": resposta_texto})
else:
    st.error("Ocorreu um erro ao configurar o sistema RAG. Por favor, verifique os logs.")