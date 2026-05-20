что нужно сделать, чтобы всё работало:

// ПРЕДВАРИТЕЛЬНО (если еще не сделал):

Ставь Ollama с ollama.com, иконка ламы в трее.

ВАЖНО СТАВЬ СТАБИЛЬНЫЙ PYTHON 3.11.

При установке питона не забудь галочку "Add to PATH".

// ЗАПУСК СИСТЕМЫ:

в терминале IDE:

ollama pull llama3.2:1b (или же ollama pull llama3.2(она умная), но делали на 1b)

python -m pip install -r requirements.txt

python -m pip install streamlit

// ЗАПУСК САЙТА:

python -m streamlit run app.py

после этого откроется вкладка в браузере. Если долго висит "Running init_assistant" - это норм, синхронится 42к чанков по 5к, просто он 

сохраняет их порциями, чтобы не вылетало. Подожди пару минут, пока создастся папка "chroma_db".

// ТРАБЛШУТИНГ (если что-то пошло не так):

Если база "не находит" инфу — удали папку chroma_db и запусти сайт заново, пусть переиндексирует нормально.

// P.S работа в venv(ВИРТ пространство):

Ollama: Скачать с сайта, установить, запустить.

Модель: В терминале: ollama pull llama3.2:1b 

Настройка папки (Виртуальное окружение)

python -m venv venv              # создать "изолятор"

.\venv\Scripts\activate          # активировать (появится надпись (venv))

pip install -r requirements.txt  # все основные библиотеки

pip install streamlit            # сам движок сайта

git checkout -b "твоя ветка"            # создать свою ветку

НАСТРОИТЬ .gitignore (добавить venv/, chroma_db/, ollama_models/)

git add .                        # добавить изменения

git commit -m "site ready"       # сохранить

git push origin "твоя ветка"            # отправка в облако

python -m streamlit run app.py       # запуск сайта

// ВОЗМОЖНЫЕ ОШИБКИ

1) Если не активируется окружение (ошибка красным текстом)

Если при вводе .\venv\Scripts\activate пишет «выполнение сценариев отключено»:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

После этого снова:

.\venv\Scripts\activate

2) Если «не видит» библиотеки (ModuleNotFoundError)

Если пишет, что нет ollama, streamlit или langchain, хотя ты их вроде ставил:

python -m pip install -r requirements.txt       # проверь чтобы лбыло venv

python -m pip install streamlit

3) Если будут такие ошибки "No module named 'langchain_community'"

pip install langchain-community        # также убедись что горит venv от ввода команды

pip install langchain langchain-text-splitters pypdf ebooklib python-docx tiktoken sentence-transformers