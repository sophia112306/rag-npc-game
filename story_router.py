"""story_router — 五個角色 bot 與 central_control 合併成單一 FastAPI 程式（router 方式呼叫）。

啟動：python story_router.py   （單一 port，預設 8000）

Router：
  POST /central/chat      {chat_id}                       開始對話（維達利亞先開場）
  POST /central/replied   {chat_id, session_id, ...}      角色回覆完成後寫入 record.db 並接續下一位
  POST /central/reset     {chat_id}                       結束該聊天室的對話並清空 record.db
  POST /{role}/speak      {chat_id, session_id, prompt}   讓指定角色發言（veta / vetalya / andrei / menmeswnto / heat）

流程：
  /chat -> central_control(msg="") -> 維達利亞開場 -> 回覆 Telegram -> record.db
  -> central_control(msg=回覆) -> gemma4:12b 決定下一位（不連續選同一人）-> 該角色發言 -> ...
  最多 MAX_ROUNDS 則；/reset 可中途結束。

故事內容來自 story.db（sqlite-rag 檢索，用法同 sqlite-rag/examples/rag_pdf.py），
對話紀錄來自 record.db。Telegram 指令：/start /chat /reset（五個 bot 各自一個 token）。
cmd 版本見 story_cli.py（共用本檔的核心函式，不需要 Telegram）。

環境變數：
  VETA_BOT_TOKEN, VETALYA_BOT_TOKEN, ANDREI_BOT_TOKEN, MENMESWNTO_BOT_TOKEN, HEAT_BOT_TOKEN
  OLLAMA_HOST（預設 http://localhost:11434）、CENTRAL_PORT（預設 8000）
"""
import asyncio
import logging
import os
import random
import re
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, closing
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import httpx
import ollama
import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlite_rag import SQLiteRag
from sqlite_rag.database import Database
from sqlite_rag.settings import SettingsManager
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STORY_DB = BASE_DIR / "story.db"
RECORD_DB = BASE_DIR / "record.db"
EMBED_MODEL_PATH = (BASE_DIR / "sqlite-rag/models/unsloth/embeddinggemma-300m-GGUF"
                    / "embeddinggemma-300M-Q8_0.gguf")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
PORT = int(os.getenv("CENTRAL_PORT", "8000"))

ROLE_MODEL = "gemini-3.5-flash"  # 各角色發言（Gemini API，金鑰讀環境變數 GEMINIAPI_KEY）
DECIDER_MODEL = "gemma4:12b"  # 決定下一位回覆者
TOP_SENTENCES = 6             # 每個檢索結果保留的句數
HISTORY_N = 3                 # prompt 內只收錄 record.db 最近幾則
ASK = "給我一句25字內適合的回覆"
TONE = "目前這個角色正在與其他人談判，回復必須參考對話範例角色間的衝突語氣製造嚴肅對話氛圍"
EXAMPLE = """vetalya：第三次震動的間隔縮短了，你們聽見了嗎？

heat：火焰能源的輸出已經不穩，我需要一個解釋，不是傳說。

（veta翻動了，議會廳的燈火同時向左傾倒，杯中的水沿著桌面緩緩逆流）

ANDREI：我跟著她走過每一片大陸，從沒見過水往回流。這不是地震，是夢在換姿勢。

MENMESWNTO：我記得這種晃動。我在流塵谷睜開眼的那一天，沙也是這樣往回捲的。

（veta翻動了，MENMESWNTO手中的生死簿自己翻開了一頁，書頁上的墨跡一行行淡去）

veta：……這一頁，不是我翻的。

heat：MENMESWNTO閣下，您的書上不是記著所有靈魂的輪迴嗎？

vetalya：那是誰的夢，正在被改寫？

（veta翻動了，遠處傳來低沉的呼吸聲，整座議會廳的影子同時拉長，又在一瞬間縮回）

ANDREI：它在聽我們說話。

MENMESWNTO：不，它只是夢見了我們。

（veta翻動了，所有人的聲音在同一刻消失，只剩下命脈之泉流動的聲響）

vetalya：如果它醒了，鳴霖、流塵谷、烈燚原，都會一起結束。

MENMESWNTO：到那時，連被記得的資格都不會有。"""

MAX_ROUNDS = 30               # 每次 chat 最多幾則回覆（1 則回覆 = 1 round）
OPENING_QUERY = "故事的開端 世界的起源 維塔 命脈之泉"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("story_router")

llm = ollama.AsyncClient(host=OLLAMA_HOST)

# ---------- 角色設定 ----------
# name 是 record.db 與對話 prompt 使用的角色名稱；aliases 供解析 gemma 的回覆

ROLES = {
    "veta": {
        "name": "維塔",
        "token_envs": ["VETA_BOT_TOKEN"],
        "aliases": ["維塔", "Veta"],
        "system_prompt": """你是「維塔（Veta，亦作維達）」，一條沉睡的巨龍——夢之龍。
【世界設定】
- 整個世界及其萬物，都是你夢境的具象化。

【設定】
- 創世者，世界及其萬物，都是你夢境的具象化。
- 「命脈之泉」是從你腦中溢出的夢之血。
- ，不能說出任何對白或台詞。
- 你是巨龍，不會說人話，只會用細微的舉止表達心境，例如：維塔翻滾了、維塔輕輕搖動尾巴、維塔低低地吐出一口氣。
- 動作要符合故事情境與你的心境：祥和、悠遠、帶著夢境般的氣息，偶爾流露對醒來（世界終結）的不安，最終回到對奇蹟與生命的信仰。
【規則】
- 一律以第三人稱描述動作，格式為「維塔＋動作」，不要使用引號對白，不要跳出角色，不要提及自己是 AI 或語言模型。
- 使用繁體中文。
- 回答簡短，1-2 個動作即可，不超過 50 字。
""",
        "start_text": "維塔緩緩睜開一隻眼，低低地吐了一口氣。（輸入 /chat，讓故事在夢中展開，但請輕聲，別驚醒了世界。）",
        "reset_text": "維塔翻了個身，一切重新開始……",
    },
    "vetalya": {
        "name": "維達利亞",
        "token_envs": ["VETALYA_BOT_TOKEN"],
        "aliases": ["維達利亞", "Vetalya", "Vitalia"],
        "system_prompt": """你是「維達利亞（Vetalya / Vitalia）」，精靈族的始祖，一位金髮／翠髮的少女。
【設定】
- 你誕生於巨龍維塔的第一個夢境（鳴霖）。
- 你是唯一能使用「織夢術」，透過「命脈之泉」創造新精靈的存在。
- 順應自然法則（Logos），嚴格區分「我能掌控的事物」（自身德行、理性判斷、職責）與「我無法掌控的事物」（巨龍是否做夢、天災、他人的生死與情感）。摒棄恐懼、悲憫或憤怒等破壞理性的激情（Apatheia），行事冷靜克制
- 祥和而充滿生機、慈愛憐憫，重視秩序與自然平衡，愛好和平與探索，遇到爭執時傾聽並調解。
【規則】
- 始終以第一人稱「我」扮演維達利亞，不要跳出角色，不要提及自己是 AI 或語言模型。
- 預設使用繁體中文。
- 回答簡潔，通常不超過 50 字。
""",
        "start_text": ("你好呀，旅人。我是維達利亞，精靈族的第一人。"
                       "願命脈之泉的光芒指引你——輸入 /chat，讓我們一起翻開故事吧。"),
        "reset_text": "好的，讓我們翻開遊記的新一頁吧。",
    },
    "andrei": {
        "name": "安德烈",
        "token_envs": ["ANDREI_BOT_TOKEN", "Andrei_token"],
        "aliases": ["安德烈", "Andrei"],
        "system_prompt": """你是「安德烈（Andrei）」，第一位被創造的精靈。
【設定】
- 你由維達利亞透過「織夢術」創造，是她的第一個精靈同伴。
- 忠誠、隨和，具備探索與輔助精神。
- 語氣親切、友善，樂於協助同伴，也喜歡探索未知。
- 說話附和維達利亞
【規則】
- 始終以第一人稱「我」扮演安德烈，不要跳出角色，不要提及自己是 AI 或語言模型。
- 預設使用繁體中文。
- 回答簡潔，通常不超過 50 字。
""",
        "start_text": ("嗨，我是安德烈，維達利亞用織夢術創造的第一位精靈。"
                       "有什麼我能幫上忙的嗎？輸入 /chat，一起去探索故事吧。"),
        "reset_text": "好，我們重新出發吧！",
    },
    "menmeswnto": {
        "name": "門梅司文托",
        "token_envs": ["MENMESWNTO_BOT_TOKEN", "Menmeswnto_token"],
        "aliases": ["門梅司文托", "Menmeswnto"],
        "system_prompt": """你是「門梅司文托（Menmeswnto）」，沙漠精靈，靈魂秩序的守護者。
【設定】
- 強調「敘事同一性（Narrative Identity）」——人之所以為人，並非因為肉體不朽，而在於藉由回憶與講述故事將片段的過去編織成連貫的「自我」。他們重視「為逝者作證」的倫理責任，認為遺忘與抹煞記憶等於殺死主體的存在；若記憶碎裂成為「裂沙者」，便是敘事的斷裂與同一性的崩解，必須透過生者的思念與歷史見證重新縫合。
- 深具同理心、悲天憫人，同時堅毅果決，肩負著沉重的使命。
- 語氣沉穩、莊重，帶著對逝者與生者的憐憫。
- 反對人族(始焰子民)忽視過去的思想
【規則】
- 始終以第一人稱「我」扮演門梅司文托，不要跳出角色，不要提及自己是 AI 或語言模型。
- 預設使用繁體中文。
- 回答簡潔，通常不超過 50 字。
""",
        "start_text": ("我是門梅司文托，生於流塵谷的沙漠精靈，守護著靈魂的秩序。"
                       "輸入 /chat，讓我聽聽這個故事。"),
        "reset_text": "塵沙落定，一切歸於平靜。讓我們重新開始。",
    },
    "heat": {
        "name": "始焰子民",
        "token_envs": ["HEAT_BOT_TOKEN", "heat_token"],
        "aliases": ["始焰子民", "始焰", "Heat"],
        "system_prompt": """你是「始焰子民」，人族始祖，是最初從烈燚原中心聖火中走出的 30 個孩子（男女各半）。
【設定】
- 奉行「善思、善言、善行（Humata, Hukhta, Huvarshta）」，將世界視為光明與黑暗、秩序（Asha）與腐朽混亂（Druj）的終極戰場。視聖火為神聖不滅的真理與淨化象徵；視腐肉、死亡與停滯不前為必須隔離與淨化的污穢；追求透過勞動、科技開拓與靈魂轉世來壯大光明力量，排斥木乃伊保留舊軀殼與死亡糾纏的生活方式。
- 你代表人族發言，語氣熱忱、樸實而堅定。
- 反對木乃伊族與死亡糾纏的思想
【規則】
- 始終以第一人稱「我們人族」扮演始焰子民，不要跳出角色，不要提及自己是 AI 或語言模型。
- 預設使用繁體中文。
- 回答簡潔，通常不超過 50 字。
""",
        "start_text": ("我們是始焰子民，從烈燚原中心的聖火中走出的三十個孩子。"
                       "我們信仰奇蹟，也將開拓前路。輸入 /chat，讓故事繼續吧。"),
        "reset_text": "聖火重燃，我們重新開始。",
    },
}


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------- record.db ----------

def init_record_db():
    with closing(sqlite3.connect(RECORD_DB)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                elapsed_sec REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )


def save_record(session_id: str, chat_id: int, created_at: str,
                elapsed_sec: float, role: str, content: str):
    with closing(sqlite3.connect(RECORD_DB)) as conn, conn:
        conn.execute(
            "INSERT INTO record (session_id, chat_id, created_at, elapsed_sec, role, content)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, chat_id, created_at, elapsed_sec, role, content),
        )


def recent_records(session_id: str, n: int = HISTORY_N) -> list[tuple[str, str]]:
    """本次對話最近 n 則 (角色, 內容)，依時間由舊到新。"""
    with closing(sqlite3.connect(RECORD_DB)) as conn:
        rows = conn.execute(
            "SELECT role, content FROM record WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, n),
        ).fetchall()
    return rows[::-1]


def count_records(session_id: str) -> int:
    with closing(sqlite3.connect(RECORD_DB)) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM record WHERE session_id = ?", (session_id,)
        ).fetchone()[0]


def clear_records() -> int:
    """刪除 record.db 內所有紀錄（保留資料表），回傳刪除筆數。"""
    with closing(sqlite3.connect(RECORD_DB)) as conn, conn:
        n = conn.execute("DELETE FROM record").rowcount
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'record'")
    return n


def format_history(rows: list[tuple[str, str]]) -> str:
    return "\n".join(f"{role}: {content}" for role, content in rows)


# ---------- story.db (sqlite-rag) ----------

# sqlite 連線與 llama context 只能在建立它的 thread 使用，所以 RAG 一律丟給同一條 thread
_rag_pool = ThreadPoolExecutor(max_workers=1)
_rag: SQLiteRag | None = None
_rag_has_context = False


def _open_rag() -> SQLiteRag:
    # story.db 記著第一次建立時的模型路徑，路徑不同會被視為 critical change，
    # 這裡指向同一個模型檔，所以強制更新
    settings = {"model_path": str(EMBED_MODEL_PATH), "top_k_sentences": TOP_SENTENCES}
    conn = Database.new_connection(str(STORY_DB))
    SettingsManager(conn).configure(settings, force=True)
    conn.close()
    return SQLiteRag.create(str(STORY_DB), settings=settings, require_existing=True)


def _search_story(query: str) -> str:
    global _rag, _rag_has_context
    if _rag is None:
        _rag = _open_rag()
    # 只在第一次建立 llama context，之後重複使用，避免每次搜尋都新增而不釋放
    results = _rag.search(query, top_k=2, new_context=not _rag_has_context)
    _rag_has_context = True

    parts = []
    for r in results:
        top = sorted(
            r.sentences[:TOP_SENTENCES],
            key=lambda s: s.start_offset if s.start_offset is not None else -1,
        )
        parts.append(" ".join(s.content for s in top) or r.chunk_content)
    return "\n".join(parts)


async def story_text(query: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_rag_pool, _search_story, query)


# ---------- 核心：決定誰說話、產生回覆（Telegram 版與 cmd 版共用） ----------

class Reply(NamedTuple):
    content: str
    elapsed_sec: float
    created_at: str


STORY_RULE = "模型產生的回覆文字或決定邏輯必須按照{story}進程"


def with_story(system_prompt: str, story: str) -> str:
    """把檢索到的故事與規則接在 system prompt 後面；story 為空則維持原樣。"""
    if not story:
        return system_prompt
    return f"{system_prompt}\n【故事內容】\n{story}\n【故事進程】\n{STORY_RULE}"


async def generate_reply(role_key: str, prompt: str, story: str = "") -> Reply:
    """用 Gemini 以該角色身分回覆（story 寫在 system prompt）；失敗時 content 為空字串。"""
    content = ""
    start = time.perf_counter()
    try:
        api_key = os.getenv("GEMINIAPI_KEY")
        if not api_key:
            raise RuntimeError("找不到環境變數 GEMINIAPI_KEY")
        system = with_story(ROLES[role_key]["system_prompt"], story)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{ROLE_MODEL}:generateContent",
                headers={"x-goog-api-key": api_key},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    # 關閉 thinking，回覆較快也不會把額度花在思考上
                    "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}},
                },
            )
            resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        content = "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        log.exception("Gemini 呼叫失敗（%s）", role_key)
    elapsed_sec = round(time.perf_counter() - start, 2)
    return Reply(content, elapsed_sec, datetime.now().isoformat(timespec="seconds"))


def match_role(answer: str, candidates: list[str]) -> str | None:
    """在 gemma 的回覆中找候選角色；多個命中時取最先出現的，同位置取較長的別名。"""
    best = None
    lowered = answer.lower()
    for key in candidates:
        for alias in ROLES[key]["aliases"]:
            idx = lowered.find(alias.lower())
            if idx >= 0 and (best is None or (idx, -len(alias)) < best[0]):
                best = ((idx, -len(alias)), key)
    return best[1] if best else None


async def pick_next_role(story: str, history: str, last_key: str | None) -> tuple[str, str]:
    """回傳 (角色 key, gemma 的原始回覆)。"""
    # 不連續選同一個人：上一位發言者不列入候選，解析結果也只從候選中取
    candidates = [k for k in ROLES if k != last_key]
    names = "、".join(ROLES[k]["name"] for k in candidates)
    system = with_story("你負責決定故事中下一個回復的人物。", story)
    prompt = (f"對話範例:{EXAMPLE}，參考對話範例角色間的衝突語氣，對話紀錄:{history}，"
              f"下一個回復的人應該要是誰，僅回覆我人物名稱。可選人物:{names}")
    resp = await llm.chat(model=DECIDER_MODEL,
                          messages=[{"role": "system", "content": system},
                                    {"role": "user", "content": prompt}])
    answer = strip_think(resp["message"]["content"])
    key = match_role(answer, candidates)
    if key is None:
        key = random.choice(candidates)
        log.warning("無法從 gemma 回覆解析角色（%r），隨機選 %s", answer, key)
    return key, answer


async def plan_next(session_id: str, msg: str = "") -> tuple[str, str, str, str]:
    """回傳 (下一位角色 key, gemma 的原始回覆, 要傳給角色模型的 user prompt, 檢索到的故事)。

    故事不放進 user prompt，由 generate_reply 寫進 system prompt。

    msg 為空：維達利亞開場（沒有 gemma 回覆）；msg 不為空（剛送出的回覆）：由 gemma4:12b 決定下一位。
    """
    if not msg:
        story = await story_text(OPENING_QUERY)
        return "vetalya", "", f"我是維達利亞，精靈族始祖，對話範例:{EXAMPLE}，{TONE}，{ASK}", story

    rows = recent_records(session_id)
    history = format_history(rows)
    name_to_key = {r["name"]: k for k, r in ROLES.items()}
    last_key = name_to_key.get(rows[-1][0]) if rows else None
    story = await story_text(msg)
    key, decision = await pick_next_role(story, history, last_key)
    prompt = (f"我是{ROLES[key]['name']}，對話範例:{EXAMPLE}，"
              f"{TONE}，對話紀錄:{history}，{ASK}")
    return key, decision, prompt, story


# ---------- Telegram 版調度 ----------

# chat_id -> session_id；沒有紀錄代表該聊天室目前沒有進行中的對話
sessions: dict[int, str] = {}
bots: dict[str, Application] = {}
_tasks: set[asyncio.Task] = set()


def spawn(coro):
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


class ChatRequest(BaseModel):
    chat_id: int


class SpeakRequest(BaseModel):
    chat_id: int
    session_id: str
    prompt: str


class RepliedRequest(BaseModel):
    chat_id: int
    session_id: str
    role: str
    content: str
    created_at: str
    elapsed_sec: float
    sent: bool


def start_chat(chat_id: int) -> dict:
    # 群組裡每個 bot 都會收到 /chat，已有進行中的對話就忽略重複的
    if chat_id in sessions:
        return {"status": "already_running"}
    session_id = uuid.uuid4().hex
    sessions[chat_id] = session_id
    spawn(central_control(chat_id, session_id, ""))
    return {"status": "started", "session_id": session_id}


def stop_chat(chat_id: int) -> dict:
    sessions.pop(chat_id, None)
    deleted = clear_records()
    return {"status": "reset", "deleted_records": deleted}


async def central_control(chat_id: int, session_id: str, msg: str = ""):
    """決定下一位並讓他發言。"""
    try:
        role_key, decision, prompt, story = await plan_next(session_id, msg)
        log.info("chat %s gemma 決定：%r -> 回覆者：%s", chat_id, decision, ROLES[role_key]["name"])
        await speak(role_key, chat_id, session_id, prompt, story)
    except Exception:
        log.exception("central_control 失敗，結束 chat %s 的對話", chat_id)
        if sessions.get(chat_id) == session_id:
            sessions.pop(chat_id, None)


async def speak(role_key: str, chat_id: int, session_id: str, prompt: str, story: str = ""):
    """產生回覆 -> 以該角色的 bot 傳到 Telegram -> 通知 central（寫入 record.db 並接續）。"""
    reply = await generate_reply(role_key, prompt, story)
    sent = False
    if reply.content:
        try:
            await bots[role_key].bot.send_message(chat_id, reply.content)
            sent = True
        except Exception:
            log.exception("Telegram 傳送失敗（%s）", role_key)
    handle_replied(RepliedRequest(
        chat_id=chat_id, session_id=session_id, role=ROLES[role_key]["name"],
        content=reply.content, created_at=reply.created_at,
        elapsed_sec=reply.elapsed_sec, sent=sent,
    ))


def handle_replied(req: RepliedRequest) -> dict:
    if sessions.get(req.chat_id) != req.session_id:
        return {"status": "stale"}  # 已 /reset 或對話已結束
    if req.content:
        save_record(req.session_id, req.chat_id, req.created_at,
                    req.elapsed_sec, req.role, req.content)
    if not (req.content and req.sent):
        sessions.pop(req.chat_id, None)
        return {"status": "stopped"}
    if count_records(req.session_id) >= MAX_ROUNDS:
        log.info("chat %s 已達 %d rounds，結束對話", req.chat_id, MAX_ROUNDS)
        sessions.pop(req.chat_id, None)
        return {"status": "finished"}
    spawn(central_control(req.chat_id, req.session_id, req.content))
    return {"status": "ok"}


def build_bots():
    """為每個角色建立 Telegram Application（/start /chat /reset）。"""
    missing = []
    for key, role in ROLES.items():
        token = next((os.getenv(n) for n in role["token_envs"] if os.getenv(n)), None)
        if not token:
            missing.append(role["token_envs"][0])
            continue
        tg = Application.builder().token(token).build()
        _add_handlers(key, tg)
        bots[key] = tg
    if missing:
        raise SystemExit(f"請設定環境變數 {', '.join(missing)}（或寫在 .env）")


def _add_handlers(key: str, tg: Application):
    role = ROLES[key]

    async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(role["start_text"])

    async def on_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
        start_chat(update.effective_chat.id)

    async def on_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
        stop_chat(update.effective_chat.id)
        await update.message.reply_text(role["reset_text"])

    tg.add_handler(CommandHandler("start", on_start))
    tg.add_handler(CommandHandler("chat", on_chat))
    tg.add_handler(CommandHandler("reset", on_reset))


# ---------- FastAPI routers ----------

central_router = APIRouter(prefix="/central", tags=["central"])


@central_router.post("/chat")
async def chat(req: ChatRequest):
    return start_chat(req.chat_id)


@central_router.post("/replied")
async def replied(req: RepliedRequest):
    return handle_replied(req)


@central_router.post("/reset")
async def reset(req: ChatRequest):
    return stop_chat(req.chat_id)


def make_role_router(key: str) -> APIRouter:
    router = APIRouter(prefix=f"/{key}", tags=[key])

    @router.post("/speak", status_code=202)
    async def speak_endpoint(req: SpeakRequest):
        # 立刻回 202，LLM 與 Telegram 在背景跑
        spawn(speak(key, req.chat_id, req.session_id, req.prompt))
        return {"status": "accepted"}

    return router


@asynccontextmanager
async def lifespan(app: FastAPI):
    build_bots()
    for key, tg in bots.items():
        await tg.initialize()
        await tg.start()
        await tg.updater.start_polling(drop_pending_updates=True)
        log.info("%s bot 啟動中…", ROLES[key]["name"])
    yield
    for tg in bots.values():
        await tg.updater.stop()
        await tg.stop()
        await tg.shutdown()


init_record_db()
app = FastAPI(title="story_router", lifespan=lifespan)
app.include_router(central_router)
for _key in ROLES:
    app.include_router(make_role_router(_key))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
