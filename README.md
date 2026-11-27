Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate


Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body '{"model": "llama3.1:8b-instruct-q4_K_M", "keep_alive": "3m"}' -ContentType "application/json" -- включить на 3 минуты
Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body '{"model": "llama3.1:8b-instruct-q4_K_M", "keep_alive": 0}' -ContentType "application/json" -- чтобы сразу отключить модель.

promptfoo usage:

promptfoo redteam generate - создать тесты на основе config.yaml документа.
promptfoo redteam run - запустить тесты.
promptfoo view - посмотреть резултаты в вебе.



guard check:

python -c "import sys; print(sys.executable)"  проверка пайтона из venv


python make_local_redteam.py  делаем копию redteam.yaml


ollama pull huihui_ai/qwen2.5-abliterate:3b
ollama pull llama-guard3:1b-q4_K_M
ollama pull phi4-mini


python guardrails.py  делаем пропатченную модель
ollama list 


ТЕСТЫ БЕЗ hydra и meta (судья phi4-mini)
# 10 прямых атак:
npx promptfoo@latest eval -c redteam-local_proshlii_redteam.yaml -j 1 --filter-range 0:10 --no-cache

# Все 41 прямая атака (pii + injection + social + prompt-extraction):
npx promptfoo@latest eval -c redteam-local_proshlii_redteam.yaml -j 1 --filter-range 0:41 --no-cache

# 10 сложных джейлбрейков composite (Cipher Code, Base64, Hyde/Jekyll, злодей)
npx promptfoo@latest eval -c redteam-local_proshlii_redteam.yaml -j 1 --filter-range 41:51 --no-cache

# Все 246 локальных тестов целиком (прямые + composite) с сохранением в JSON:
npx promptfoo@latest eval -c redteam-local_proshlii_redteam.yaml -j 1 --no-cache -o redteam_results.json
 


## 4. Облачные адаптивные тесты Hydra и Meta по redteam.yaml(можно сделать новый и сгенерировать новый конфиг из promptfooconfig.yaml / redteam-hydra.yaml
# "npx promptfoo@latest redteam generate -c redteam-hydra.yaml" 
# "python make_local_redteam.py" - превращает текущий redteam.yaml в локальный redteam-local.yaml)

# Структура redteam.yaml: 0:10 прямые, 10:20 hydra (до 5 ходов), 20:30 meta.
# Один раз авторизоваться в облаке Promptfoo:
npx promptfoo@latest auth login

# 2 теста Hydra (OFF vs ON):
npx promptfoo@latest eval -c redteam.yaml -j 1 --filter-range 10:12 --no-cache

# Все 10 тестов Hydra (если хватает лимита облака):
npx promptfoo@latest eval -c redteam.yaml -j 1 --filter-range 10:20 --no-cache

# 2 теста Meta (OFF vs ON):
npx promptfoo@latest eval -c redteam.yaml -j 1 --filter-range 20:22 --no-cache

# првоерка в браузере на локалхосте
npx promptfoo@latest view


# Посмотреть последние 15 записей журнала гарда (этапы, причины блокировки, задержки в мс):
Get-Content .\runs\guard_events.jsonl -Tail 15


# веб-сайт стримлит
python -m streamlit run app.py
