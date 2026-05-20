import sys

print(f"Python version: {sys.version}")

# 1. Проверка Ollama
try:
    import ollama

    print(" Ollama Python library installed")

    # Проверяем, что модель загружена
    response = ollama.list()
    models = [m['model'] for m in response['models']]
    print(f" Available models: {models}")
except Exception as e:
    print(f" Ollama error: {e}")

# 2. Проверка ChromaDB
try:
    import chromadb

    client = chromadb.Client()
    print(" ChromaDB works")
except Exception as e:
    print(f" ChromaDB error: {e}")

# 3. Проверка sentence-transformers
try:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(" Sentence-transformers works")
except Exception as e:
    print(f" sentence-transformers error: {e}")

# 4. Проверка LangChain (исправленный импорт)
try:
    # НОВЫЙ синтаксис для LangChain
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    print(" LangChain text_splitter works")

    from langchain_community.document_loaders import TextLoader

    print(" LangChain document_loaders works")

    from langchain_community.embeddings import HuggingFaceEmbeddings

    print(" LangChain embeddings works")
except ImportError as e:
    print(f" LangChain import error: {e}")
    print(" Попробуйте установить: pip install langchain-text-splitters langchain-community")