import streamlit as st
import csv
import os
from datetime import datetime
from rag_system import RAGAssistant

st.set_page_config(page_title="AI Помощник", page_icon="🤖")
st.title("🤖 Твой личный RAG-ассистент")
st.markdown("Задавай вопросы по документам из папки `knowledge`")

# ФУНКЦИЯ ДЛЯ ФИДБЕКА
def save_feedback(query, response, feedback_val):
    """Сохраняет оценку в CSV-файл для дальнейшей аналитики"""
    file_path = "feedback.csv"
    file_exists = os.path.exists(file_path)
    
    with open(file_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # для нового файла
        if not file_exists:
            writer.writerow(["Дата", "Вопрос", "Ответ", "Оценка"])
        
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), query, response, feedback_val])

@st.cache_resource
def init_assistant():
    return RAGAssistant()

try:
    assistant = init_assistant()
except Exception as e:
    st.error(f"Ошибка при загрузке базы данных: {e}")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if message["role"] == "assistant":
            fb_key = f"fb_{i}"
            saved_key = f"saved_{i}"
            
            feedback = st.feedback("thumbs", key=fb_key)

            if feedback is not None and saved_key not in st.session_state:
                val = "👍" if feedback == 1 else "👎"
                
                user_q = st.session_state.messages[i-1]["content"] if i > 0 else "Нет вопроса"
                
                save_feedback(user_q, message["content"], val)
                
                st.toast(f"Отзыв сохранен: {val}", icon="✅")
                
                st.session_state[saved_key] = True

if prompt := st.chat_input("Введите ваш вопрос..."):
    # вопрос пользователя
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ответ нейронки
    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            try:
                response = assistant.ask_with_sources(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()

            except Exception as e:
                st.error(f"Произошла ошибка: {e}")
                print(f"ПОЛНЫЙ ЛОГ ОШИБКИ: {e}")