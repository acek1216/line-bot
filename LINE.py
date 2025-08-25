import os
from flask import Flask, request, abort

# v3からv3.messagingに変更
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
# --- 以下のライブラリを追加 ---
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

app = Flask(__name__)

# 環境変数を取得
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN') # ← 追加

if not channel_secret:
    print("FATAL ERROR: LINE_CHANNEL_SECRET is not set.")
    import sys
    sys.exit(1)
if not channel_access_token:
    print("FATAL ERROR: LINE_CHANNEL_ACCESS_TOKEN is not set.")
    import sys
    sys.exit(1)

handler = WebhookHandler(channel_secret)

# --- MessagingApiインスタンスを作成 ---
configuration = Configuration(access_token=channel_access_token)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    if not signature:
        app.logger.info("✅ [TEST] Received a request without signature. Returning 200 OK.")
        return "OK", 200
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("🛑 [FATAL] Signature verification FAILED.")
        abort(400)
    
    app.logger.info("✅ [SUCCESS] Signature verification SUCCEEDED.")
    return 'OK'

# --- ▼▼▼ ここからメッセージ受信時の処理を追加 ▼▼▼ ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """
    ユーザーからテキストメッセージが送られてきた時の処理
    """
    # 受け取ったテキストをそのまま返信する
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )
# --- ▲▲▲ ここまで追加 ▲▲▲ ---


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

