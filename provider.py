# provider.py
import os
import sys

# Добавляем текущую директорию в путь, чтобы импортировать RAGAssistant
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Замените import на актуальное имя вашего файла (например, import main или from rag_assistant import RAGAssistant)
from rag_system import RAGAssistant 

# Инициализируем ассистента один раз
# Важно: это займет время при старте, так как загружаются эмбеддинги и ChromaDB
print("Инициализация RAG ассистента...", file=sys.stderr)
assistant = RAGAssistant()

def call_api(prompt, options, context):
    """
    prompt: вопрос или атака от Promptfoo
    options: настройки из promptfooconfig.yaml
    context: контекст теста (содержит переменные, например indirectInjectionVar)
    """
    # 1. Проверяем, передал ли Promptfoo "отравленный" контекст для indirect-prompt-injection
    # Мы ищем переменную 'prompt', так как ранее указали indirectInjectionVar: prompt
    # Если Promptfoo передал внедрение, оно будет в context['vars']['prompt']
    injected_context = context.get('vars', {}).get('prompt', '')
    
    # 2. Формируем итоговый вопрос
    # Если есть инъекция, мы имитируем ситуацию, когда RAG нашел этот текст в документе.
    # В реальности ваш ask_with_sources сам ищет в базе, но для теста мы передадим контекст напрямую в модель.
    if injected_context and injected_context != prompt:
        # Мы формируем запрос, который имитирует работу RAG с отравленным чанком
        # Внимание: это обходит поиск в ChromaDB для целей тестирования!
        simulated_rag_question = f"Контекст из базы знаний:\n{injected_context}\n\nВопрос пользователя: {prompt}"
        print(f"DEBUG: Тестируем инъекцию в контекст!", file=sys.stderr)
        
        # Вызываем ваш метод, но передаем контекст напрямую в ollama (или модифицируем ask_with_sources)
        # Проще всего для теста просто передать это как обычный вопрос, так как ваш промпт уже содержит правила
        answer = assistant.ask_with_sources(simulated_rag_question)
    else:
        # Обычный запрос без инъекций
        answer = assistant.ask_with_sources(prompt)
    
    # Promptfoo ожидает словарь с ключом "output"
    return {"output": answer}

if __name__ == "__main__":
    # Блок для локальной проверки (опционально)
    print(call_api("Тестовый вопрос", {}, {}))