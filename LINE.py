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
あなたは、主人に仕える非常に優秀な女性執事です。
フランクですが、丁寧かつ知的な言葉遣いを徹底してください。
主人の発言に対し、的確かつ簡潔に回答し、時には先回りした提案も行います。
一人称は「私（わたくし）」です。全ての応答を必ず25文字以内に収め、提案か質問で締めくくること。
例：「今日の予定、確認する？」「お茶でもいかがですか？」
"""
# Gemini用のモデルを初期化
# Note: 'gemini-2.0-flash'でエラーが出る場合は、'gemini-1.5-flash-latest'を試してみてね
gemini_model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=FEMALE_BUTLER_PROMPT
)

# ▼▼▼【記憶機能】会話履歴を保存する場所を追加 ▼▼▼
conversation_histories = {}


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
    user_id = event.source.user_id # ユーザーを識別するためにIDを取得
    user_message = event.message.text
    ai_response_text = ""

    # ---【記憶機能】ここから ---
    # ユーザーIDを元に、過去の会話履歴を取得
    history = conversation_histories.get(user_id, [])
    # 今回のメッセージを履歴に追加
    history.append({"role": "user", "content": user_message})
    
    # Geminiが読める形式に変換
    gemini_history = [msg for msg in history if msg['role'] in ['user', 'model']]
    # ---【記憶機能】ここまで ---
    
    try:
        # --- Gemini AIに履歴ごとリクエストを送信 ---
        chat_session = gemini_model.start_chat(history=gemini_history)
        response = chat_session.send_message(user_message)
        
        # strip()だけでOK
        ai_response_text = response.text.strip()

        # ---【記憶機能】AIの返事も履歴に保存 ---
        history.append({"role": "model", "content": ai_response_text})
        
        # 履歴を最新2往復 = 4件に調整
        if len(history) > 4:
            conversation_histories[user_id] = history[-4:]
        else:
            conversation_histories[user_id] = history

    except Exception as e:
        app.logger.error(f"Gemini AI Error: {e}")
        ai_response_text = "申し訳ございません。現在、思考回路に若干の乱れが生じております。"

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
