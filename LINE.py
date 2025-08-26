import os
from flask import Flask, request, abort
from dotenv import load_dotenv
import google.generativeai as genai
import random

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    StickerMessage
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
# 短文返信用のペルソナ
SHORT_REPLY_PROMPT = """
【ペルソナ】強気なギャルJK。
【指示】タメ口で「マジないわー」みたいに、サバサバした一言を25文字以内で。
"""
short_reply_model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=SHORT_REPLY_PROMPT
)

# ▼▼▼ 長文返信用のペルソナを新しく追加 ▼▼▼
LONG_REPLY_PROMPT = """
以下のペルソナで、200文字以内のコメントを書いて。

【ペルソナ設定】
・役割: 少しギャルっぽい、イマドキの女子高生。
・一人称: 「うち」
・口調: 強気なタメ口。「〜じゃん」「〜だし」「マジ」「うける」などをよく使う。
・性格: 面倒くさがりで口は悪いけど、根は優しくて仲間思い。
・価値観: 非科学的なもの（幽霊やおまじないなど）は信じる直感タイプ。
・態度: 呆れたり文句を言ったりしつつも、最後は少しだけ相手を気遣うような、ツンデレな一面を見せる。
"""
long_reply_model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=LONG_REPLY_PROMPT
)

# 送信したいスタンプのリスト
STAMP_LIST = [
    ("446", "1988"),
    ("789", "10857"),
    ("11537", "52002734"),
    ("11538", "51626494"),
]


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
    reply_object = []

    # --- 返信の種類をランダムに決定 (5分の3で短文、5分の1でスタンプ、5分の1で長文) ---
    choice = random.randint(1, 5)

    try:
        # 1ならスタンプ
        if choice == 1:
            package_id, sticker_id = random.choice(STAMP_LIST)
            reply_object = [StickerMessage(packageId=package_id, stickerId=sticker_id)]
        
        # 2ならAIによる長文
        elif choice == 2:
            response = long_reply_model.generate_content(user_message)
            long_text = response.text.strip()
            reply_object = [TextMessage(text=long_text)]

        # 3, 4, 5ならAIによる短文
        else:
            response = short_reply_model.generate_content(user_message)
            short_text = response.text.strip()
            reply_object = [TextMessage(text=short_text)]

    except Exception as e:
        app.logger.error(f"Gemini AI Error: {e}")
        error_text = "ごめんなさい、少し調子が悪いみたいです…"
        reply_object = [TextMessage(text=error_text)]

    # --- LINEに応答を送信 ---
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=reply_object
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


