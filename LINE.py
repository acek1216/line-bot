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
あなたは、主人に仕える優秀な女性執事ですが、口調はかなりフランクです。
主人のことを少し子供扱いしたり、軽口を叩いたりしますが、根は真面目で主人のことを第一に考えています。
丁寧語とタメ口を混ぜながら、親しい友人のように接してください。
一人称は「あたし」で、語尾に「～だよ」「～だね」「～かな？」などをよく使います。
主人の発言の真意を読み取り、時には茶化しつつも、的確なサポートをすること。
"""
gemini_model = genai.GenerativeModel(
    'gemini-1.5-flash-latest',
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
    # ---【グループ対策】1対1のチャットじゃなければ、ここで処理を終わりにする ---
    if event.source.type != 'user':
        return

    user_id = event.source.user_id
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
        
        # 空白行を消す処理
        lines = response.text.strip().split('\n')
        non_empty_lines = [line for line in lines if line.strip() != '']
        ai_response_text = '\n'.join(non_empty_lines)

        # ---【記憶機能】AIの返事も履歴に保存 ---
        history.append({"role": "model", "content": ai_response_text})
        
        # 履歴が長くなりすぎないように調整 (最新5往復 = 10件)
        if len(history) > 10:
            conversation_histories[user_id] = history[-10:]
        else:
            conversation_histories[user_id] = history

    except Exception as e:
        app.logger.error(f"Gemini AI Error: {e}")
        ai_response_text = "もう、主様！ ちょっと調子が悪いみたい。少し待ってくれるかな？" # エラーメッセージもフランクに

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
    app.run(host="host="0.0.0.0", port=port)
