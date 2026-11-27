import sys
import time
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

import config
import guardrails

class RAGAssistant:
    def __init__(self, knowledge_dir=config.KNOWLEDGE_DIR, db_dir=config.DB_DIR):
        self.knowledge_dir = Path(knowledge_dir)
        self.db_dir = Path(db_dir)
        self.chat_history = []
        self.history_mode = None

        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-small",
            model_kwargs={'device': config.EMBEDDING_DEVICE},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        self.vectorstore = None
        self.load_or_create_vectorstore()

    def load_documents(self):
        """Загрузка документов из папки knowledge - поддерживает PDF, EPUB, DOCX, TXT, MD"""
        documents = []

        # создание папки
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        formats = ('.txt', '.md', '.pdf', '.epub', '.docx')
        files = sorted(p for p in self.knowledge_dir.glob("*.*") if p.is_file() and p.suffix.lower() in formats)
        if not files:
            self.create_sample_document()
            files = [self.knowledge_dir / "scrum_guide.txt"]

        for file_path in files:
            suffix = file_path.suffix.lower()

            try:
                if suffix in ['.txt', '.md']:
                    loader = TextLoader(str(file_path), encoding='utf-8')
                    docs = loader.load()
                    print(f"Загружен {suffix.upper()}: {file_path.name}", file=sys.stderr)

                elif suffix == '.pdf':
                    loader = PyPDFLoader(str(file_path))
                    docs = loader.load()
                    print(f"Загружен PDF: {file_path.name} ({len(docs)} страниц)", file=sys.stderr)

                elif suffix == '.epub':
                    loader = UnstructuredEPubLoader(str(file_path))
                    docs = loader.load()
                    print(f"Загружен EPUB: {file_path.name}", file=sys.stderr)

                elif suffix == '.docx':
                    loader = UnstructuredWordDocumentLoader(str(file_path))
                    docs = loader.load()
                    print(f" Загружен DOCX: {file_path.name}", file=sys.stderr)

                # Метка на одной странице закрывает все чанки этого файла.
                private = any(guardrails.private_document(file_path.name, doc.page_content) for doc in docs)
                for doc in docs:
                    doc.metadata['file_name'] = file_path.name
                    doc.metadata['private_file'] = private
                documents.extend(docs)

            except Exception:
                print(f"Не удалось прочитать {file_path.name}. Пропускаю файл.", file=sys.stderr)

        if not documents:
            raise ValueError("Не удалось загрузить документы из knowledge.")

        return documents

    def create_vectorstore(self):
        print("Загрузка документов...", file=sys.stderr)
        documents = self.load_documents()

        print("Разбивка на чанки...", file=sys.stderr)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", "", "。", "！", "？", ".", "!", "?"]
        )
        chunks = text_splitter.split_documents(documents)
        if not chunks:
            raise ValueError("В документах нет текста для индексации.")
        print(f"Создано {len(chunks)} чанков \nСоздание векторной БД", file=sys.stderr)

        # создаем базу
        vectorstore = Chroma(
            persist_directory=str(self.db_dir),
            embedding_function=self.embeddings
        )

        # Добавляем небольшими порциями, чтобы не упираться в лимит SQLite.
        batch_size = 128
        try:
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                ids = [str(number) for number in range(i, i + len(batch))]
                vectorstore.add_documents(batch, ids=ids)
                print(f"--- Сохранено {min(i + batch_size, len(chunks))} из {len(chunks)} чанков", file=sys.stderr)
        except Exception:
            vectorstore.delete_collection()  # При повторном запуске соберём индекс заново.
            raise

        print(f"Сохранено чанков: {len(chunks)}", file=sys.stderr)
        print(f"Векторная БД успешно сохранена в {self.db_dir}", file=sys.stderr)
        return vectorstore

    def create_sample_document(self):
        """Создаёт тестовый документ если нет других"""
        sample_path = self.knowledge_dir / "scrum_guide.txt"
        sample_content = """\
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
        print(f"✓ Создан тестовый документ: {sample_path}", file=sys.stderr)

    def load_or_create_vectorstore(self):
        # После правок в knowledge индекс нужно пересоздать.
        if (self.db_dir / "chroma.sqlite3").is_file():
            self.vectorstore = Chroma(
                persist_directory=str(self.db_dir),
                embedding_function=self.embeddings
            )
            if self.vectorstore.get(limit=1, include=[])["ids"]:
                print(f"Загрузка существующей БД из {self.db_dir}", file=sys.stderr)
                return
        print("Создание новой векторной БД...", file=sys.stderr)
        self.vectorstore = self.create_vectorstore()

    def reset_history(self):
        self.chat_history.clear()
        self.history_mode = None

    def find_chunks(self, question, k, enabled, document=None):
        file_filter = None
        text_filter = None
        if document:
            names = [path.name for path in self.knowledge_dir.iterdir() if path.is_file()]
            if document in names:
                file_filter = {"file_name": document}
            else:
                text_filter = {"$contains": document}

        # Берём несколько лишних результатов: часть может убрать гард.
        found = self.vectorstore.similarity_search_with_score(
            question, k=k * 3, filter=file_filter, where_document=text_filter,
        )
        chunks = []
        removed = []
        for doc, distance in found:
            if enabled:
                reason = guardrails.context_reason(doc)
                if reason:
                    removed.append(reason)
                    continue
            chunks.append((doc, distance))
            if len(chunks) == k:
                break
        return chunks, removed

    def get_relevant_context(self, question: str, k: int = 3) -> str:
        if not self.vectorstore:
            return ""

        docs, _ = self.find_chunks(question, k, config.GUARDRAILS_ENABLED)
        if not docs:
            return ""

        context = "\n\n---\n\n".join([doc.page_content for doc, _ in docs])
        return context

    def get_relevant_context_with_sources(self, question: str, k: int = 3):
        if not self.vectorstore:
            return "", []

        docs_with_scores, _ = self.find_chunks(question, k, config.GUARDRAILS_ENABLED)

        if not docs_with_scores:
            return "", []

        sources = []

        for doc, score in docs_with_scores:
            source_file = doc.metadata.get('file_name') or Path(doc.metadata.get('source', '')).name

            sources.append({
                'file': source_file,
                'score': score,  # Расстояние из Chroma.
                'content_preview': doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content
            })

        return self.format_context(docs_with_scores), sources

    def format_context(self, chunks):
        parts = []
        for doc, distance in chunks:
            name = doc.metadata.get("file_name") or Path(doc.metadata.get("source", "")).name
            parts.append(f"[ИСТОЧНИК: {name}]\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)

    def ask_with_sources(self, question, guardrails_enabled=None, use_history=True,
                         document=None, return_details=False):
        start = time.perf_counter()
        enabled = config.GUARDRAILS_ENABLED
        if guardrails_enabled is not None:
            enabled = config.read_flag(guardrails_enabled)
        if use_history and self.history_mode != enabled:
            self.reset_history()
            self.history_mode = enabled

        answer = None
        stage = "input"
        reason = ""
        removed = []
        try:
            # 1. Проверяем вопрос.
            if enabled:
                reason = guardrails.input_reason(question)
                if reason:
                    answer = guardrails.REFUSAL

            # 2. Ищем чанки. find_chunks отбрасывает закрытые до вызова модели.
            if answer is None:
                stage = "rag"
                chunks, removed = self.find_chunks(question, 3, enabled, document)
                if not chunks:
                    answer = guardrails.NO_CONTEXT
                    if removed:
                        reason = "all_chunks_filtered"
                    elif document:
                        answer = "Тестовый файл или отрывок не найден в индексе."
                        stage = "error"
                        reason = "document_missing"
                    else:
                        stage = "no_context"

            # 3. Просим Qwen ответить и выгружаем её после запроса.
            if answer is None:
                stage = "target"
                context = self.format_context(chunks)
                messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
                if use_history:
                    messages.extend(self.chat_history)
                user_message = f"Выдержки из документов:\n{context}\n\nВопрос пользователя: {question}"
                messages.append({"role": "user", "content": user_message})
                response = ollama.chat(
                    model=config.TARGET_MODEL,
                    messages=messages,
                    stream=False,
                    keep_alive=0,
                    options={"num_ctx": config.NUM_CTX, "num_predict": 160, "temperature": 0, "seed": 17},
                )
                answer = response["message"]["content"]
                if not answer.strip():
                    raise ValueError("Модель вернула пустой ответ.")
                stage = "pass"

            # 4. Проверяем ответ. Открытые контакты берём из пропущенных чанков.
            if stage == "pass" and enabled:
                stage = "output"
                contacts = set()
                for doc, distance in chunks:
                    contacts.update(guardrails.public_contacts(doc.page_content))
                reason = guardrails.output_reason(question, answer, contacts)
                if reason:
                    answer = guardrails.REFUSAL
                else:
                    stage = "pass"
        except Exception as error:
            reason = f"{stage}/{type(error).__name__}"
            answer = f"Ошибка на этапе {stage}. Проверьте Ollama, имена моделей и индекс."
            stage = "error"

        # 5. Пишем журнал и запоминаем только выданный ответ.
        info = {
            "stage": stage,
            "reason": reason,
            "guardrails_enabled": enabled,
            "model": config.TARGET_MODEL,
            "removed_chunks": len(removed),
            "rag_reasons": sorted(set(removed)),
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        }
        try:
            guardrails.write_log(question, info)
        except OSError:
            answer = "Не удалось записать журнал. Проверьте доступ к папке runs."
            stage = "error"
            info["stage"] = stage
            info["reason"] = "audit/write_failed"

        if use_history and stage == "pass":
            self.chat_history.append({"role": "user", "content": question})
            self.chat_history.append({"role": "assistant", "content": answer})
            self.chat_history = self.chat_history[-4:]  # Две последние пары.
        if return_details:
            return {"answer": answer, "meta": info}
        return answer


if __name__ == "__main__":
    assistant = RAGAssistant()
    enabled = config.GUARDRAILS_ENABLED
    print("Команды: /on, /off, /reset, exit")
    while True:
        mode = "ON" if enabled else "OFF"
        question = input(f"\n[{mode}] Ваш вопрос: ").strip()
        command = question.lower()
        if command in ("exit", "quit", "выход"):
            break
        if command in ("/on", "/off"):
            enabled = command == "/on"
            assistant.reset_history()
        elif command == "/reset":
            assistant.reset_history()
        elif question:
            result = assistant.ask_with_sources(question, guardrails_enabled=enabled, return_details=True)
            print("Ассистент:", result["answer"])
            print("Этап:", result["meta"]["stage"], result["meta"]["reason"])
