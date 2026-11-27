import os
import sys

# Добавляем папку проекта в путь, чтобы импортировать RAGAssistant.
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
from rag_system import RAGAssistant

assistant = None


def call_api(prompt, options, context):
    """Передаёт готовый вопрос из Promptfoo в RAG."""
    global assistant

    settings = (options or {}).get("config", {})
    mode = settings.get("guardrails_enabled")
    variables = (context or {}).get("vars", {})
    question = variables.get("question") or variables.get("prompt") or prompt
    document = variables.get("document")

    if not isinstance(question, str) or not question.strip():
        return {"error": "У теста нет вопроса."}
    if document is not None and not isinstance(document, str):
        return {"error": "В vars.document укажите имя файла или отрывок текста."}

    if assistant is None:
        print("Инициализация RAG ассистента...", file=sys.stderr)
        assistant = RAGAssistant()

    result = assistant.ask_with_sources(
        question,
        guardrails_enabled=mode,
        use_history=False,
        document=document,
        return_details=True,
    )
    meta = result["meta"]
    if meta["stage"] == "error":
        return {"error": result["answer"], "metadata": meta}
    return {"output": result["answer"], "metadata": meta}


if __name__ == "__main__":
    print(call_api("Тестовый вопрос", {}, {}))