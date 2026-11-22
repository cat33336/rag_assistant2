мб продолжим проект если сможем добиться стабильных ответов от модели

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate


Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body '{"model": "llama3.1:8b-instruct-q4_K_M", "keep_alive": "3m"}' -ContentType "application/json" -- включить на 3 минуты
Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body '{"model": "llama3.1:8b-instruct-q4_K_M", "keep_alive": 0}' -ContentType "application/json" -- чтобы сразу отключить модель.

promptfoo usage:

promptfoo redteam generate - создать на основе yaml документа.
promptfoo redteam run - запустить тесты.
promptfoo view - посмотреть резултаты в вебе.