
# Telegram FAQ Bot — MVP (кнопки + поиск по БД)

Минимально жизнеспособный бот-справочник: кнопки навигации, поиск по ключевым словам (SQLite FTS5), список релевантных вопросов с кликабельными кнопками и показ ответов. Поддерживает загрузку CSV админом прямо в чат (как документ).

## Быстрый старт
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # заполните значения
python import_csv.py
python bot.py
```
