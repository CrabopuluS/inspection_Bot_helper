
import csv, asyncio
from pathlib import Path
from db import init_db, rebuild_fts
import aiosqlite

CSV_PATH = Path("data/faq.csv")

async def main():
  await init_db()
  if not CSV_PATH.exists():
    print(f"CSV not found: {CSV_PATH}")
    return

  async with aiosqlite.connect("faq.db") as db:
    await db.execute("DELETE FROM faq;")
    cnt = 0
    with CSV_PATH.open("r", encoding="utf-8") as f:
      reader = csv.DictReader(f)
      for row in reader:
        await db.execute(
          "INSERT INTO faq(question, answer, tags) VALUES(?,?,?)",
          (row.get("question","").strip(), row.get("answer","").strip(), row.get("tags","").strip())
        )
        cnt += 1
    await db.commit()
  await rebuild_fts()
  print(f"Импортировано {cnt} записей; FTS индекс пересобран.")

if __name__ == "__main__":
  asyncio.run(main())
