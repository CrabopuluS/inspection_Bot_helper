
import aiosqlite
from pathlib import Path
from typing import List, Dict, Any, Tuple

DB_PATH = Path("faq.db")

CREATE_TABLES = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS faq(
  id INTEGER PRIMARY KEY,
  question TEXT NOT NULL,
  answer   TEXT NOT NULL,
  tags     TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE VIRTUAL TABLE IF NOT EXISTS faq_fts
USING fts5(question, answer, content='faq', content_rowid='id', tokenize='unicode61');
"""

async def init_db():
  async with aiosqlite.connect(DB_PATH) as db:
    await db.executescript(CREATE_TABLES)
    await db.commit()

async def rebuild_fts():
  async with aiosqlite.connect(DB_PATH) as db:
    await db.execute("DELETE FROM faq_fts;")
    await db.execute("""
      INSERT INTO faq_fts(rowid, question, answer)
      SELECT id, question, answer FROM faq;
    """)
    await db.commit()

def _fts_query_from_text(text: str) -> str:
  terms = [w for w in text.lower().split() if len(w) > 1]
  if not terms:
    return ""
  return " OR ".join(f"{t}*" for t in terms[:8])

async def search(text: str, limit: int = 5) -> List[Dict[str, Any]]:
  q = _fts_query_from_text(text)
  if not q:
    return []
  sql_ranked = """
    SELECT f.id, f.question, f.answer,
           bm25(faq_fts) AS rank
    FROM faq_fts
    JOIN faq f ON f.id = faq_fts.rowid
    WHERE faq_fts MATCH ?
    ORDER BY rank
    LIMIT ?;
  """
  sql_fallback = """
    SELECT f.id, f.question, f.answer
    FROM faq_fts
    JOIN faq f ON f.id = faq_fts.rowid
    WHERE faq_fts MATCH ?
    LIMIT ?;
  """
  async with aiosqlite.connect(DB_PATH) as db:
    db.row_factory = aiosqlite.Row
    try:
      rows = await db.execute_fetchall(sql_ranked, (q, limit))
    except Exception:
      rows = await db.execute_fetchall(sql_fallback, (q, limit))
    return [dict(r) for r in rows]

async def get_question_by_id(qid: int) -> Dict[str, Any] | None:
  async with aiosqlite.connect(DB_PATH) as db:
    db.row_factory = aiosqlite.Row
    row = await db.execute_fetchone(
      "SELECT id, question, answer, tags FROM faq WHERE id = ?",
      (qid,)
    )
    return dict(row) if row else None

async def get_all_tags(limit: int = 50) -> List[str]:
  async with aiosqlite.connect(DB_PATH) as db:
    rows = await db.execute_fetchall("SELECT tags FROM faq WHERE tags IS NOT NULL AND tags <> ''")
  s = set()
  for (tagstr,) in rows:
    for t in tagstr.split(";"):
      t = t.strip()
      if t:
        s.add(t)
  return sorted(list(s))[:limit]

async def get_questions_by_tag(tag: str, offset: int = 0, limit: int = 10) -> Tuple[int, List[Dict[str, Any]]]:
  async with aiosqlite.connect(DB_PATH) as db:
    db.row_factory = aiosqlite.Row
    (count_row,) = await db.execute_fetchone(
      "SELECT COUNT(*) FROM faq WHERE tags LIKE ?",
      (f"%{tag}%",)
    )
    rows = await db.execute_fetchall(
      "SELECT id, question FROM faq WHERE tags LIKE ? ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
      (f"%{tag}%", limit, offset)
    )
    return count_row, [dict(r) for r in rows]
