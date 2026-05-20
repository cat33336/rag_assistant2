import streamlit as st
from rag_system import RAGAssistant

# настройки страницы 
st.set_page_config(page_title="AI Помощник", page_icon="🤖")

st.title("🤖 Твой личный RAG-ассистент")
st.markdown("Задавай вопросы по документам из папки `knowledge`")

# кэширование инициализации
@st.cache_resource
def init_assistant():
    return RAGAssistant()

try:
    assistant = init_assistant()
except Exception as e:
    st.error(f"Ошибка при загрузке базы данных: {e}")
    st.stop()

# история чата
if "messages" not in st.session_state:
    st.session_state.messages = []

# отображение истории
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# поле чата
if prompt := st.chat_input("Введите ваш вопрос..."):
    # вопрос пользователя
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ответ нейронки
    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            try:
                response = assistant.ask(prompt)
                st.markdown(response)
            except Exception as e:
                st.error(f"Произошла ошибка: {e}")
                print(f"ПОЛНЫЙ ЛОГ ОШИБКИ: {e}")
    
    st.session_state.messages.append({"role": "assistant", "content": response})