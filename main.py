import os
import sys
import datetime
from zoneinfo import ZoneInfo

from contextlib import asynccontextmanager

import aiohttp
from fastapi import Request, FastAPI, HTTPException, Header

from linebot.models import MessageEvent, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot import AsyncLineBotApi, WebhookParser

from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

import bp_advice
import router
import tasks as task_jobs
from bp_image import extract_bp_from_image
from firestore_store import default_store

# --- Configuration -------------------------------------------------------
USE_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI") or "FALSE"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or ""

channel_secret = os.getenv("ChannelSecret", None)
channel_access_token = os.getenv("ChannelAccessToken", None)
TASKS_TOKEN = os.getenv("TasksToken", None)
TZ = ZoneInfo("Asia/Taipei")

if channel_secret is None:
    print("Specify ChannelSecret as environment variable.")
    sys.exit(1)
if channel_access_token is None:
    print("Specify ChannelAccessToken as environment variable.")
    sys.exit(1)
if USE_VERTEX == "True":
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
    if not GOOGLE_CLOUD_PROJECT:
        raise ValueError("Please set GOOGLE_CLOUD_PROJECT when USE_VERTEX is true.")
    if not GOOGLE_CLOUD_LOCATION:
        raise ValueError("Please set GOOGLE_CLOUD_LOCATION when USE_VERTEX is true.")
elif not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY via env var or code.")

# --- App & clients -------------------------------------------------------
# The aiohttp session must be created inside a running event loop, so the LINE
# client is initialised on startup via the lifespan handler below.
line_bot_api: AsyncLineBotApi | None = None
_http_session: aiohttp.ClientSession | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global line_bot_api, _http_session
    _http_session = aiohttp.ClientSession()
    line_bot_api = AsyncLineBotApi(
        channel_access_token, AiohttpAsyncHttpClient(_http_session)
    )
    try:
        yield
    finally:
        await _http_session.close()


app = FastAPI(lifespan=lifespan)
parser = WebhookParser(channel_secret)
store = default_store()

# --- Conversational agent (fall-through for non-BP chat) -----------------
root_agent = Agent(
    name="health_companion_agent",
    model="gemini-2.5-flash",
    description="A warm health companion for elders.",
    instruction=(
        "你是一位親切、有耐心的長輩健康小幫手，請用溫暖、簡單、易懂的繁體中文回覆。"
        "若使用者談到身體不適或血壓問題，給予一般性的關心與提醒，並建議必要時就醫，"
        "但不要提供醫療診斷。回覆請簡短、口語化。"
    ),
    tools=[],
)
session_service = InMemorySessionService()
APP_NAME = "linebot_bp_app"
active_sessions = {}
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


def today_str() -> str:
    return datetime.datetime.now(TZ).strftime("%Y-%m-%d")


# --- LLM polish for advice ----------------------------------------------
def polish_advice(base_text: str, category: bp_advice.Category) -> str:
    """Rewrite advice in a warm tone via Gemini; fall back to base on error."""
    from google import genai

    client = genai.Client()
    prompt = (
        "請把下面這段血壓建議，改寫成對長輩說話、溫暖親切、簡短口語的繁體中文，"
        "保留數值與分級的重點，不要新增醫療診斷：\n\n" + base_text
    )
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return resp.text or base_text


# --- LINE helpers --------------------------------------------------------
async def push_text(uid: str, text: str) -> None:
    try:
        await line_bot_api.push_message(uid, TextSendMessage(text=text))
    except Exception as e:  # noqa: BLE001
        print(f"push_message failed for {uid}: {e}")


async def fetch_image_bytes(message_id: str) -> bytes:
    content = await line_bot_api.get_message_content(message_id)
    chunks = []
    async for chunk in content.iter_content():
        chunks.append(chunk)
    return b"".join(chunks)


# --- Webhook -------------------------------------------------------------
@app.post("/")
async def handle_callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = (await request.body()).decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        user_id = event.source.user_id

        if event.message.type == "text":
            reply = await router.handle_text_message(
                store,
                user_id,
                event.message.text,
                today_str(),
                polish=polish_advice,
                agent_reply=call_agent_async,
            )
            await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        elif event.message.type == "image":
            reply = await handle_image_message(event.message.id, user_id)
            await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        else:
            continue

    return "OK"


async def handle_image_message(message_id: str, user_id: str) -> str:
    try:
        image_bytes = await fetch_image_bytes(message_id)
    except Exception as e:  # noqa: BLE001
        print(f"fetch image failed: {e}")
        return "抱歉，我讀取照片時出了點問題，請再傳一次，或直接輸入血壓數值（例如 120/80）。"

    reading = extract_bp_from_image(image_bytes)
    if reading is None:
        return (
            "我看不太清楚血壓計上的數字 😅 請對準螢幕重拍一張，"
            "或直接輸入血壓數值（例如 120/80）給我。"
        )
    return router.record_and_advise(
        store, user_id, reading, "image", today_str(), polish=polish_advice
    )


# --- Scheduled task endpoints (Cloud Scheduler) --------------------------
def _check_tasks_token(token: str | None) -> None:
    if not TASKS_TOKEN or token != TASKS_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/tasks/morning-reminder")
async def morning_reminder(x_tasks_token: str | None = Header(default=None)):
    _check_tasks_token(x_tasks_token)
    count = await task_jobs.run_morning_reminder(store, today_str(), push_text)
    return {"reminded": count}


@app.post("/tasks/escalation-check")
async def escalation_check(x_tasks_token: str | None = Header(default=None)):
    _check_tasks_token(x_tasks_token)
    sent = await task_jobs.run_escalation_check(store, today_str(), push_text)
    return {"notified": sent}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# --- Conversational agent runner ----------------------------------------
async def get_or_create_session(user_id: str) -> str:
    if user_id not in active_sessions:
        session_id = f"session_{user_id}"
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        active_sessions[user_id] = session_id
    return active_sessions[user_id]


async def call_agent_async(query: str, user_id: str) -> str:
    session_id = await get_or_create_session(user_id)
    content = types.Content(role="user", parts=[types.Part(text=query)])
    final_response_text = "不好意思，我現在沒辦法回覆，請稍後再試。"
    try:
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                break
    except ValueError as e:
        if "Session not found" in str(e):
            active_sessions.pop(user_id, None)
            session_id = await get_or_create_session(user_id)
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        final_response_text = event.content.parts[0].text
                    break
        else:
            print(f"agent error: {e}")
    return final_response_text
