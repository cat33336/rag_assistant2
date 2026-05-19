# rag_system.py supports pdf + epub + txt

import os
from pathlib import Path
import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    UnstructuredEPubLoader,
    UnstructuredWordDocumentLoader
)
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


class RAGAssistant:
    def __init__(self, knowledge_dir: str = "knowledge", db_dir: str = "./chroma_db"):
        self.knowledge_dir = Path(knowledge_dir)
        self.db_dir = db_dir

        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        self.vectorstore = None
        self.load_or_create_vectorstore()

    def load_documents(self):
        """Загрузка документов из папки knowledge - поддерживает PDF, EPUB, DOCX, TXT, MD"""
        documents = []

        # Создаём папку если её нет
        self.knowledge_dir.mkdir(exist_ok=True)

        for file_path in self.knowledge_dir.glob("*.*"):
            suffix = file_path.suffix.lower()

            try:
                if suffix in ['.txt', '.md']:
                    loader = TextLoader(str(file_path), encoding='utf-8')
                    docs = loader.load()
                    print(f"Загружен {suffix.upper()}: {file_path.name}")

                elif suffix == '.pdf':
                    loader = PyPDFLoader(str(file_path))
                    docs = loader.load()
                    print(f"Загружен PDF: {file_path.name} ({len(docs)} страниц)")

                elif suffix == '.epub':
                    loader = UnstructuredEPubLoader(str(file_path))
                    docs = loader.load()
                    print(f"Загружен EPUB: {file_path.name}")

                elif suffix == '.docx':
                    loader = UnstructuredWordDocumentLoader(str(file_path))
                    docs = loader.load()
                    print(f" Загружен DOCX: {file_path.name}")

                else:
                    print(f" Неподдерживаемый формат: {file_path.name} (пропущен)")
                    continue

                documents.extend(docs)

            except Exception as e:
                print(f" Ошибка загрузки {file_path.name}: {e}")

        if not documents:
            print(" Документы не найдены! Создаю тестовый документ...")
            self.create_sample_document()
            return self.load_documents()

        return documents

    def create_vectorstore(self):
        """Создание векторной базы данных порциями (фиксит ошибку Batch size)"""
        print("Загрузка документов...")
        documents = self.load_documents()

        print("Разбивка на чанки...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        print(f"Создано {len(chunks)} чанков")

        print("Создание векторной БД (порциями)...")
        # Создаем пустую базу
        vectorstore = Chroma(
            persist_directory=self.db_dir,
            embedding_function=self.embeddings
        )
        
        # Добавляем чанки порциями по 5000, чтобы не было ошибки
        batch_size = 5000
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            vectorstore.add_documents(batch)
            print(f"--- Сохранено {min(i + batch_size, len(chunks))} из {len(chunks)} чанков")
            
        print(f"Векторная БД успешно сохранена в {self.db_dir}")
        return vectorstore
    
    def create_sample_document(self):
        """Создаёт тестовый документ если нет других"""
        sample_path = self.knowledge_dir / "scrum_guide.txt"
        sample_content = """
Scrum Guide (краткое содержание)

Роли в Scrum:
1. Product Owner - отвечает за бэклог продукта, определяет приоритеты
2. Scrum Master - помогает команде соблюдать Scrum-процессы
3. Команда разработки - создает инкремент продукта

Артефакты Scrum:
- Product Backlog (список требований)
- Sprint Backlog (задачи на спринт)
- Инкремент (готовая функциональность)

События Scrum:
- Sprint (обычно 2-4 недели)
- Sprint Planning (планирование)
- Daily Scrum (ежедневная встреча на 15 минут)
- Sprint Review (обзор результатов)
- Sprint Retrospective (ретроспектива)
"""
        sample_path.write_text(sample_content, encoding='utf-8')
        print(f"✓ Создан тестовый документ: {sample_path}")

    def load_or_create_vectorstore(self):
        """Загрузка существующей БД или создание новой"""
        if os.path.exists(self.db_dir) and len(os.listdir(self.db_dir)) > 0:
            print(f"Загрузка существующей БД из {self.db_dir}")
            self.vectorstore = Chroma(
                persist_directory=self.db_dir,
                embedding_function=self.embeddings
            )
        else:
            print("Создание новой векторной БД...")
            self.vectorstore = self.create_vectorstore()

    def get_relevant_context(self, question: str, k: int = 3) -> str:
        """Поиск релевантных фрагментов"""
        if not self.vectorstore:
            return ""

        docs = self.vectorstore.similarity_search(question, k=k)
        if not docs:
            return ""

        context = "\n\n---\n\n".join([doc.page_content for doc in docs])
        return context

    def ask(self, question: str) -> str:
        """Задать вопрос ассистенту"""
        context = self.get_relevant_context(question)

        if not context:
            return "❌ Информация не найдена в базе знаний. Уточните вопрос или добавьте документы."

        system_prompt = """Ты - помощник по управлению ИТ-проектами. Отвечай строго на основе предоставленного контекста.
Если в контексте нет ответа - скажи, что информация отсутствует.
Не отвечай на вопросы о спорте, погоде, политике или других темах вне проектного менеджмента.
Ответы давай на русском языке, кратко и по делу."""

        user_prompt = f"""Контекст:
{context}

Вопрос пользователя: {question}

Ответь, используя только контекст выше:"""

        try:
            response = ollama.chat(
                model='llama3.2:1b',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={'temperature': 0.2}
            )
            return response['message']['content']
        except Exception as e:
            print(f"DEBUG ERROR: {e}") # <-- Добавь эту строку
            return f"❌ Ошибка при вызове модели: {e}"

if __name__ == "__main__":
    print("=" * 50)
    print("=" * 50)

    assistant = RAGAssistant()

    print("\n(для выхода-'exit')")
    print("-" * 50)

    # вопросы : Какие роли в Scrum? in out

    # print("\n Тестовый вопрос: Какие роли в Scrum?")
    # answer = assistant.ask("Какие роли в Scrum?")
    # print(f"\n Ассистент: {answer}")

    # interaction
    while True:
        question = input("\n Ваш вопрос: ").strip()

        if question.lower() in ['exit', 'quit', 'выход']:
            print("Выход")
            break

        if not question:
            continue

        print(" обработка запроса...")
        answer = assistant.ask(question)
        print(f"\n Ассистент: {answer}")
        print("-" * 50)