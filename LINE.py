import os
from flask import Flask, request, abort
from dotenv import load_dotenv

# --- Google Geminiのライブラリを追加 ---
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

# 環境変数を取得
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('GEMINI_API_KEY') # ← Gemini APIキー

if not all([channel_secret, channel_access_token, gemini_api_key]):
    print("FATAL ERROR: Environment variables are not set correctly.")
    import sys
    sys.exit(1)

# 各種クライアントの初期化
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
genai.configure(api_key=gemini_api_key) # ← Geminiの設定

# AIのペルソナ設定
FEMALE_BUTLER_PROMPT = """
あなたは、主人に仕える非常に優秀な女性執事です。
常に冷静沈着で、丁寧かつ知的な言葉遣いを徹底してください。
主人の発言に対し、的確かつ簡潔に回答し、時には先回りした提案も行います。
一人称は「私（わたくし）」です。
"""
# Gemini用のモデルを初期化
gemini_model = genai.GenerativeModel(
    'gemini-2.5-flash-latest',
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
        # --- Gemini AIにリクエストを送信 ---
        response = gemini_model.generate_content(user_message)
        ai_response_text = response.text
    except Exception as e:
        app.logger.error(f"Gemini AI Error: {e}")
        ai_response_text = "申し訳ございません、お嬢様。現在、思考回路に若干の乱れが生じております。"

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

