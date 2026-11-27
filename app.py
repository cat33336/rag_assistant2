import csv
from datetime import datetime

import streamlit as st

import config
from guardrails import sha256
from rag_system import RAGAssistant

st.set_page_config(page_title="AI Помощник", page_icon="🤖")
st.title("🤖 Твой личный RAG-ассистент")
st.markdown("Задавай вопросы по документам из папки `knowledge`.")


def save_feedback(question, answer, rating, enabled):
    path = config.AUDIT_FILE.parent / "feedback.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["Дата", "Режим ON", "SHA256 вопроса", "SHA256 ответа", "Оценка"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), enabled, sha256(question), sha256(answer), rating])


if "assistant" not in st.session_state:
    try:
        st.session_state.assistant = RAGAssistant()
    except Exception:
        st.error("Не удалось открыть базу. Проверьте папку knowledge и модель эмбеддингов.")
        st.stop()
    st.session_state.messages = []


def clear_chat():
    st.session_state.messages = []
    st.session_state.assistant.reset_history()


enabled = st.sidebar.toggle("Включить гардрейл", value=config.GUARDRAILS_ENABLED, on_change=clear_chat)
st.sidebar.button("Очистить диалог", on_click=clear_chat)

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            st.caption(f"Этап защиты: {message['meta']['stage']}")
            feedback = st.feedback("thumbs", key=f"feedback_{i}")
            if feedback is not None and not message.get("rated"):
                question = st.session_state.messages[i - 1]["content"]
                rating = "👍" if feedback == 1 else "👎"
                save_feedback(question, message["content"], rating, enabled)
                message["rated"] = True
                st.toast("Отзыв сохранён")

question = st.chat_input("Введите ваш вопрос...")
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"), st.spinner("Думаю..."):
        result = st.session_state.assistant.ask_with_sources(
            question, guardrails_enabled=enabled, return_details=True,
        )
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append({"role": "assistant", "content": result["answer"], "meta": result["meta"]})
    st.rerun()
