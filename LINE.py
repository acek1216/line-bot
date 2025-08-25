import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

channel_secret = os.environ.get('LINE_CHANNEL_SECRET', None)
if not channel_secret:
    print("FATAL ERROR: LINE_CHANNEL_SECRET is not set.")
    # この環境では起動させない
    import sys
    sys.exit(1)

handler = WebhookHandler(channel_secret)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    # 検証ボタン（署名なし）か、本物のメッセージ（署名あり）かをログに出力
    if not signature:
        app.logger.info("✅ [TEST] Received a request without signature (likely Verify button). Returning 200 OK.")
        return "OK", 200
    
    # 署名検証
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("🛑 [FATAL] Signature verification FAILED. The LINE_CHANNEL_SECRET is WRONG.")
        abort(400)
    
    app.logger.info("✅ [SUCCESS] Signature verification SUCCEEDED.")
    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
