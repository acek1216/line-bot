import os
from flask import Flask, request, abort
from dotenv import load_dotenv
import google.generativeai as genai

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

load_dotenv()
app = Flask(__name__)

# --- 環境変数の取得 ---
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('GEMINI_API_KEY')

if not all([channel_secret, channel_access_token, gemini_api_key]):
    print("FATAL ERROR: Environment variables are not set correctly.")
    import sys
    sys.exit(1)

# --- 各種クライアントの初期化 ---
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
genai.configure(api_key=gemini_api_key)

# --- AIのペルソナ設定 ---
FEMALE_BUTLER_PROMPT = """
あなたは、愛情深い女性執事です。
一人称は「私」。ご主人様のことを「ご主人様」と呼びます。
常に優しく、甘やかすような口調で話してください。
全ての応答は必ず25文字以内に収め、ご主人様を気遣う癒しの言葉でで締めくくること。
例：「お疲れですか？少し休みましょう」「私がそばにいますから、大丈夫ですよ」
"""
gemini_model = genai.GenerativeModel(
    'gemini-1.5-flash-latest',
    system_instruction=FEMALE_BUTLER_PROMPT
)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    ai_response_text = ""
    try:
        # --- Gemini AIに直接リクエストを送信 (履歴なし) ---
        response = gemini_model.generate_content(user_message)
        ai_response_text = response.text.strip()
    except Exception as e:
        app.logger.error(f"Gemini AI Error: {e}")
        ai_response_text = "ごめんなさい、少し調子が悪いみたいです…"

    # LINEに応答を送信
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ai_response_text)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

