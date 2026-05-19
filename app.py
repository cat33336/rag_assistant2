import streamlit as st
from rag_system import RAGAssistant

# Настройка страницы
st.set_page_config(page_title="AI Помощник", page_icon="🤖")

st.title("🤖 Твой личный RAG-ассистент")
st.markdown("Задавай вопросы по документам из папки `knowledge`")

# Кэшируем инициализацию
@st.cache_resource
def init_assistant():
    return RAGAssistant()

try:
    assistant = init_assistant()
except Exception as e:
    st.error(f"Ошибка при загрузке базы данных: {e}")
    st.stop()

# История чата в памяти браузера
if "messages" not in st.session_state:
    st.session_state.messages = []

# Отображаем историю
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("Введите ваш вопрос..."):
    # Добавляем вопрос пользователя
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Получаем ответ от нейронки
    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            try:
                response = assistant.ask(prompt)
                st.markdown(response)
            except Exception as e:
                st.error(f"Произошла ошибка: {e}")
                print(f"ПОЛНЫЙ ЛОГ ОШИБКИ: {e}") # Это появится в терминале VS Code
    
    # Сохраняем ответ
    st.session_state.messages.append({"role": "assistant", "content": response})