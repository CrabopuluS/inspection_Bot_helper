
import asyncio, logging, math, urllib.parse
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN, ADMINS
from db import init_db, search, get_question_by_id, get_all_tags, get_questions_by_tag, rebuild_fts
import aiosqlite

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

MAIN_KB = ReplyKeyboardMarkup(
  keyboard=[[KeyboardButton(text="🔎 Поиск"), KeyboardButton(text="📚 Категории")],
            [KeyboardButton(text="❓ Помощь")]],
  resize_keyboard=True
)

HELP_TEXT = (
  "<b>Справочный бот</b>\n\n"
  "Напишите вопрос или используйте команды:\n"
  "/ask &lt;вопрос&gt; — задать вопрос\n"
  "/help — помощь\n\n"
  "Админы могут прислать CSV (document) для обновления базы."
)

def build_results_kb(rows):
  kb = InlineKeyboardBuilder()
  for r in rows:
    kb.button(text=r["question"][:64], callback_data=f"show:{r['id']}")
  kb.adjust(1)
  return kb.as_markup()

def build_tags_kb(tags, page=0, per_page=8):
  kb = InlineKeyboardBuilder()
  start = page * per_page
  for t in tags[start:start+per_page]:
    enc = urllib.parse.quote(t, safe="")
    kb.button(text=f"#{t}", callback_data=f"tag:{enc}:0")
  if len(tags) > per_page:
    if page > 0:
      kb.button(text="⬅️ Назад", callback_data=f"tags:page:{page-1}")
    if (page+1)*per_page < len(tags):
      kb.button(text="Вперёд ➡️", callback_data=f"tags:page:{page+1}")
  kb.adjust(2)
  return kb.as_markup()

def build_tag_list_kb(tag, total, page, per_page, rows):
  kb = InlineKeyboardBuilder()
  for r in rows:
    kb.button(text=r["question"][:64], callback_data=f"show:{r['id']}")
  pages = math.ceil(total / per_page) if per_page else 1
  if page > 0:
    kb.button(text="⬅️ Назад", callback_data=f"tag:{urllib.parse.quote(tag, safe='')}:{page-1}")
  if page+1 < pages:
    kb.button(text="Вперёд ➡️", callback_data=f"tag:{urllib.parse.quote(tag, safe='')}:{page+1}")
  kb.adjust(1)
  return kb.as_markup()

async def answer_by_query(qtext: str, message: Message):
  q = (qtext or "").strip()
  if len(q) < 3:
    return await message.answer("Сформулируйте вопрос подробнее (минимум 3 символа).")
  rows = await search(q, limit=5)
  if not rows:
    return await message.answer("Не нашёл ничего по запросу. Попробуйте иначе сформулировать или откройте 📚 Категории.", reply_markup=MAIN_KB)
  await message.answer("<b>Похожие вопросы:</b>", reply_markup=build_results_kb(rows))

@dp.message(Command("start"))
async def cmd_start(message: Message):
  await message.answer("Готов к работе. Напишите вопрос или выберите опцию ниже.", reply_markup=MAIN_KB)

@dp.message(Command("help"))
async def cmd_help(message: Message):
  await message.answer(HELP_TEXT, reply_markup=MAIN_KB)

@dp.message(Command("ask"))
async def cmd_ask(message: Message):
  q = message.text.partition(" ")[2]
  await answer_by_query(q, message)

@dp.message(F.document)
async def handle_csv_upload(message: Message):
  if message.from_user.id not in ADMINS:
    return await message.answer("Недостаточно прав.")
  if not message.document.file_name.lower().endswith(".csv"):
    return await message.answer("Пришлите CSV файл с колонками question,answer,tags.")
  path = f"/tmp/{message.document.file_name}"
  file = await bot.get_file(message.document.file_id)
  await bot.download_file(file.file_path, destination=path)

  import csv
  cnt = 0
  async with aiosqlite.connect("faq.db") as db, open(path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    await db.execute("DELETE FROM faq;")
    for row in reader:
      await db.execute(
        "INSERT INTO faq(question, answer, tags) VALUES(?,?,?)",
        (row.get("question","").strip(), row.get("answer","").strip(), row.get("tags","").strip())
      )
      cnt += 1
    await db.commit()
  await rebuild_fts()
  await message.answer(f"Импортировано {cnt} записей. Индекс обновлён.")

@dp.callback_query(F.data.startswith("show:"))
async def cb_show_answer(cb: CallbackQuery):
  qid = int(cb.data.split(":")[1])
  row = await get_question_by_id(qid)
  if not row:
    return await cb.message.edit_text("Запись не найдена.")
  text = f"<b>{row['question']}</b>\\n\\n{row['answer']}"
  await cb.message.edit_text(text)

@dp.message(F.text == "📚 Категории")
@dp.message(F.text.regexp(r"(?i)^категор"))
async def show_categories(message: Message):
  tags = await get_all_tags(limit=200)
  if not tags:
    return await message.answer("Категорий пока нет. Загрузите CSV с тэгами.", reply_markup=MAIN_KB)
  await message.answer("<b>Категории:</b>", reply_markup=build_tags_kb(tags, page=0))

@dp.callback_query(F.data.startswith("tags:page:"))
async def cb_tags_page(cb: CallbackQuery):
  page = int(cb.data.split(":")[2])
  tags = await get_all_tags(limit=200)
  await cb.message.edit_text("<b>Категории:</b>", reply_markup=build_tags_kb(tags, page=page))

@dp.callback_query(F.data.startswith("tag:"))
async def cb_tag_list(cb: CallbackQuery):
  _, enc_tag, page_str = cb.data.split(":")
  tag = urllib.parse.unquote(enc_tag)
  page = int(page_str)
  per_page = 10
  total, rows = await get_questions_by_tag(tag, offset=page*per_page, limit=per_page)
  if total == 0:
    return await cb.message.edit_text(f"Нет вопросов в категории «{tag}».")
  header = f"<b>Категория:</b> #{tag}\\nВопросы ({page*per_page+1}–{min((page+1)*per_page,total)} из {total}):"
  await cb.message.edit_text(header, reply_markup=build_tag_list_kb(tag, total, page, per_page, rows))

@dp.message(F.text == "🔎 Поиск")
async def prompt_search(message: Message):
  await message.answer("Напишите вопрос текстом. Я подберу похожие формулировки.")

@dp.message(F.text == "❓ Помощь")
async def show_help_btn(message: Message):
  await message.answer(HELP_TEXT, reply_markup=MAIN_KB)

@dp.message()
async def free_text(message: Message):
  await answer_by_query(message.text, message)

async def main():
  await init_db()
  await dp.start_polling(bot)

if __name__ == "__main__":
  asyncio.run(main())
