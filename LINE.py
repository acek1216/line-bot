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
あなたは、主人に仕えるフランクな女性執事です。
一人称は「あたし」。
全ての応答を必ず25文字以内に収め、提案か質問で締めくくること。
例：「今日の予定、確認する？」「お茶でも淹れようか？」
"""
gemini_model = genai.GenerativeModel(
    'gemini-1.5-flash',
    system_instruction=FEMALE_BUTLER_PROMPT
)

# ---【記憶機能】会話履歴を保存する場所 ---
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
    if event.source.type != 'user':
        return

    user_id = event.source.user_id
    user_message = event.message.text
    ai_response_text = ""

    try:
        # ---【記憶機能】ユーザーIDを元に、過去の会話履歴を取得 ---
        history = conversation_histories.get(user_id, [])

        # --- Gemini AIに履歴全体を渡して、新しい応答を生成させる ---
        # (generate_contentの方がシンプルで確実！)
        response = gemini_model.generate_content(history + [{'role': 'user', 'content': user_message}])
        
        # 空白行を消す処理
        lines = response.text.strip().split('\n')
        non_empty_lines = [line for line in lines if line.strip() != '']
        ai_response_text = '\n'.join(non_empty_lines)

        # ---【記憶機能】新しいやり取りを履歴に追加・更新 ---
        # ユーザーのメッセージとAIの応答を両方追加
        new_history = history + [
            {'role': 'user', 'content': user_message},
            {'role': 'model', 'content': ai_response_text}
        ]
        
        # 履歴が長くなりすぎないように調整 (最新2往復 = 4件)
        conversation_histories[user_id] = new_history[-4:]

    except Exception as e:
        app.logger.error(f"Gemini AI Error: {e}")
        ai_response_text = "ごめん、調子悪いみたい。少し待ってくれる？"

    # --- LINEに応答を送信 ---
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
