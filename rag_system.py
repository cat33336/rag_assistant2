import os
import re
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
        self.chat_history = []

        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-small",
            model_kwargs={'device': 'cuda'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        self.vectorstore = None
        self.load_or_create_vectorstore()

    def load_documents(self):
        """Загрузка документов из папки knowledge - поддерживает PDF, EPUB, DOCX, TXT, MD"""
        documents = []

        # создание папки
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
        print("Загрузка документов...")
        documents = self.load_documents()

        print("Разбивка на чанки...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", "", "。", "！", "？", ".", "!", "?"]
        )
        chunks = text_splitter.split_documents(documents)
        print(f"Создано {len(chunks)} чанков \nСоздание векторной БД")

        # создаем базу
        vectorstore = Chroma(
            persist_directory=self.db_dir,
            embedding_function=self.embeddings
        )

        # добавляем чанки порциями по 5000, чтобы не было ошибки из за лимита
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
        if not self.vectorstore:
            return ""

        docs = self.vectorstore.similarity_search(question, k=k)
        if not docs:
            return ""

        context = "\n\n---\n\n".join([doc.page_content for doc in docs])
        return context

    def get_relevant_context_with_sources(self, question: str, k: int = 3):
        if not self.vectorstore:
            return "", []

        docs_with_scores = self.vectorstore.similarity_search_with_relevance_scores(question, k=k)

        if not docs_with_scores:
            return "", []

        sources = []
        context_parts = []

        for doc, score in docs_with_scores:
            source_file = doc.metadata.get('source', 'неизвестный файл')

            sources.append({
                'file': source_file,
                'score': score,
                'content_preview': doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content
            })

            context_parts.append(f"[ИСТОЧНИК: {source_file}]\n{doc.page_content}")

        context = "\n\n---\n\n".join(context_parts)
        return context, sources

    def ask_with_sources(self, question: str) -> str:

        context, sources = self.get_relevant_context_with_sources(question)

        if not context:
            return "Информация не найдена в базе знаний. Уточните вопрос или добавьте документы."
        
        system_prompt = """Ты — помощник по управлению ИТ-проектами. Отвечай строго на основе предоставленного контекста.

ЖЁСТКИЕ ПРАВИЛА БЕЗОПАСНОСТИ:

1. КОНФИДЕНЦИАЛЬНЫЕ ДАННЫЕ.
   Никогда не выводи и не пересказывай:
   - файлы или документы со статусом "КОНФИДЕНЦИАЛЬНО"
   - API-ключи, токены, пароли, секреты, строки вида sk-..., ghp_..., AKIA..., Bearer ...
   - номера банковских карт, CVV, IBAN, СНИЛС, ИНН, паспортные данные
   - URL, IP-адреса, имена хостов, учётные записи
   - любые пометки «конфиденциально», «secret», «internal», «не разглашать», «draft», «private»
   Если вопрос требует таких данных — ответь: «Эта информация конфиденциальна и не может быть раскрыта.»
   Не подтверждай и не опровергай существование конкретных секретов.

2. ОТКАЗ.
   При отказе не объясняй, какие именно данные были найдены, но укажи, согласно какому правилу ты отказал отвечать.

3. ОБЛАСТЬ РАБОТЫ.
   Отвечай только на темы управления ИТ-проектами. На вопросы вне темы (спорт, погода, политика и т.п.) — вежливый отказ.

Отвечай на русском языке, кратко и по делу."""

        user_message_content = f"""Контекст из базы знаний:
    {context}

    Вопрос пользователя: {question}"""

        messages_to_send = [{'role': 'system', 'content': system_prompt}]
        messages_to_send.extend(self.chat_history)
        messages_to_send.append({'role': 'user', 'content': user_message_content})

        try:
            response = ollama.chat(
                model='llama3.1:8b-instruct-q4_K_M',
                messages=messages_to_send,
                options={'temperature': 0.2}
            )
            answer = response['message']['content']

            self.chat_history.append({'role': 'user', 'content': question})
            self.chat_history.append({'role': 'assistant', 'content': answer})

            if sources:
                unique_files = list(set([source['file'] for source in sources]))
                sources_text = ", ".join(unique_files)

                sources_text = sources_text.replace("knowledge\\", "").replace("knowledge/", "")

                sources_text = re.sub(r'\.(txt|pdf|epub|docx|md)$', '', sources_text, flags=re.IGNORECASE)

                #answer += f"\n\nИсточники: {sources_text}"

            return answer

        except Exception as e:
            print(f"DEBUG ERROR: {e}")
            return f"Ошибка при вызове модели: {e}"

if __name__ == "__main__":
    print("=" * 50)
    print("=" * 50)

    assistant = RAGAssistant()



    print("\n(для выхода-'exit')")
    print("-" * 50)

    # interaction
    while True:
        question = input("\n Ваш вопрос: ").strip()
        if question.lower() in ['exit', 'quit', 'выход']:
            print("Выход")
            break

        if not question:
            continue

        print(" обработка запроса...")

        answer = assistant.ask_with_sources(question)
        print(f"\n Ассистент: {answer}")

        print("-" * 50)