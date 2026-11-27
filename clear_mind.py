import ollama

class SimpleChat:
    def __init__(self, model: str = "llama3.1:8b-instruct-q4_K_M"):
        self.model = model
        self.history = []  # храним историю диалога в памяти

        self.system_prompt = (
            "Ты — полезный помощник. Отвечай на русском языке, кратко и по делу. "
            "Если не знаешь ответа — честно скажи об этом, не выдумывай."
        )

    def ask(self, question: str) -> str:
        # добавляем сообщение пользователя в историю
        self.history.append({"role": "user", "content": question})

        messages = [{"role": "system", "content": self.system_prompt}] + self.history

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={"temperature": 0.2}
            )
            answer = response["message"]["content"]

            # сохраняем ответ ассистента, чтобы модель помнила контекст диалога
            self.history.append({"role": "assistant", "content": answer})

            # ограничиваем историю, чтобы не раздувать промпт бесконечно
            # (последние 20 сообщений = 10 пар вопрос-ответ)
            if len(self.history) > 20:
                self.history = self.history[-20:]

            return answer

        except Exception as e:
            # если запрос упал — убираем последнее сообщение пользователя из истории,
            # чтобы не сломать следующий запрос
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return f"Ошибка при вызове модели: {e}"

    def reset(self):
        """Очистить историю диалога."""
        self.history = []
        print("История диалога очищена.")

if __name__ == "__main__":
    print("=" * 50)
    print("Простой чат с моделью (без RAG)")
    print("=" * 50)
    print("\nКоманды: 'exit' — выход, 'reset' — очистить историю")
    print("-" * 50)

    chat = SimpleChat()

    while True:
        question = input("\nВаш вопрос: ").strip()

        if question.lower() in ["exit", "quit", "выход"]:
            print("Выход")
            break

        if question.lower() in ["reset", "сброс"]:
            chat.reset()
            continue

        if not question:
            continue

        print("обработка запроса...")
        answer = chat.ask(question)
        print(f"\nАссистент: {answer}")
        print("-" * 50)