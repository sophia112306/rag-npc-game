"""story_cli — 直接在 cmd 執行的版本（不需要 Telegram / FastAPI / token）。

啟動：python story_cli.py

指令（不含斜線）：
  start   各角色自我介紹
  chat    開始對話：維達利亞先開場，之後由 gemma4:12b 決定下一位（不連續選同一人），最多 MAX_ROUNDS 則
          Ctrl+C 可中途停止（只停止，不刪紀錄）
  reset   重置：刪除 record.db 內所有紀錄（每次 chat 本來就是新對話）
  exit    離開

每則輸出：
  <角色key>:<模型回覆>
"""
import asyncio
import logging
import uuid

from story_router import MAX_ROUNDS, ROLES, clear_records, generate_reply, plan_next, save_record

# story_router 載入時設了 INFO，cmd 版只留警告，避免蓋掉對話輸出
logging.getLogger().setLevel(logging.WARNING)

CLI_CHAT_ID = 0  # record.db 的 chat_id 欄位；cmd 版固定為 0
HELP = "指令：start / chat / reset / exit（chat 進行中按 Ctrl+C 可停止）"


async def run_chat():
    session_id = uuid.uuid4().hex
    msg = ""
    for _ in range(MAX_ROUNDS):
        role_key, decision, prompt, story = await plan_next(session_id, msg)
        reply = await generate_reply(role_key, prompt, story)
        # print(f"對話角色:{role_key}\n{gemma}Qwen提示詞:{prompt}\n角色回復:{reply.content}\n")
        print(f"{role_key}:{reply.content}\n")
        if not reply.content:
            print("（模型沒有回覆，結束對話）")
            return
        save_record(session_id, CLI_CHAT_ID, reply.created_at, reply.elapsed_sec,
                    ROLES[role_key]["name"], reply.content)
        msg = reply.content
    print(f"已達 {MAX_ROUNDS} rounds，結束對話")


def main():
    # 全程使用同一個 event loop，ollama 的 AsyncClient 才能重複使用
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print(HELP)
    while True:
        try:
            cmd = input("> ").strip().lower().lstrip("/")
        except (EOFError, KeyboardInterrupt):
            break
        if cmd == "start":
            for role in ROLES.values():
                print(f"{role['name']}：{role['start_text'].replace('/chat', 'chat')}")
        elif cmd == "chat":
            task = loop.create_task(run_chat())
            try:
                loop.run_until_complete(task)
            except KeyboardInterrupt:
                task.cancel()
                try:
                    loop.run_until_complete(task)
                except asyncio.CancelledError:
                    pass
                print("\n（已停止對話）")
            except Exception as e:
                print(f"（對話失敗：{e}）")
        elif cmd == "reset":
            print(f"已重置：刪除 record.db 內 {clear_records()} 筆紀錄，下次 chat 會開始新的對話。")
        elif cmd in ("exit", "quit"):
            break
        elif cmd:
            print(HELP)


if __name__ == "__main__":
    main()
