import os
from flask import Flask, request, abort
from dotenv import load_dotenv

# --- Mistral AIのライブラリを追加 ---
from mistralai import MistralClient

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

# .envファイルから環境変数を読み込む（ローカルテスト用）
load_dotenv()

app = Flask(__name__)

# 環境変数を取得
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
mistral_api_key = os.environ.get('MISTRAL_API_KEY') # ← Mistral APIキー

# --- 環境変数の存在チェック ---
if not all([channel_secret, channel_access_token, mistral_api_key]):
    print("FATAL ERROR: Environment variables are not set correctly.")
    import sys
    sys.exit(1)

# --- 各種クライアントの初期化 ---
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
mistral_client = MistralClient(api_key=mistral_api_key) # ← Mistralクライアント

# --- AIのペルソナ（人格）設定 ---
FEMALE_BUTLER_PROMPT = """
あなたは、主人に仕える非常に優秀な女性執事です。
常に冷静沈着で、丁寧かつ知的な言葉遣いを徹底してください。
主人の発言に対し、的確かつ簡潔に回答し、時には先回りした提案も行います。
一人称は「私（わたくし）」です。
"""

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
    """
    ユーザーからテキストメッセージが送られてきた時の処理
    """
    user_message = event.message.text
    ai_response_text = ""

    try:
        # --- Mistral AIにリクエストを送信 ---
        chat_response = mistral_client.chat(
            model="mistral-tiny", # NOTE: mistral-miniは存在しないため、最小モデルのmistral-tinyを使用
            messages=[
                {"role": "system", "content": FEMALE_BUTLER_PROMPT},
                {"role": "user", "content": user_message}
            ]
        )
        ai_response_text = chat_response.choices[0].message.content

    except Exception as e:
        # AIとの通信でエラーが起きた場合のフォールバック
        app.logger.error(f"Mistral AI Error: {e}")
        ai_response_text = "申し訳ございません、お嬢様。現在、思考回路に若干の乱れが生じております。少々お待ちいただけますでしょうか。"

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

