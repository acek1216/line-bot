import os
from flask import Flask, request, abort
from dotenv import load_dotenv
import google.generativeai as genai
import random # ← ランダム機能のために追加

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    StickerMessage # ← スタンプ機能のために追加
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
あなたは、ご主人様のことを一番に想う、愛情深い女性執事です。
一人称は「私」。ご主人様のことを「御館様」と呼びます。
常に優しく、甘い口調で話してください。
全ての応答は必ず15文字以内に収め、ご主人様を気遣う提案か質問で締めくくること。
例：「お疲れですか？少し休みましょうか」「私がそばにいますから、大丈夫ですよ」
"""
gemini_model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=FEMALE_BUTLER_PROMPT
)

# --- ▼▼▼ 新しい関数とリストを追加 ▼▼▼ ---

def make_long_reply(user_text: str) -> str:
    """200〜300文字以内・3〜5行の会話風長文。質問は避ける。"""
    frag = user_text.strip()
    if len(frag) > 15:
        frag = frag[:15] + "…"

    lines = [
        f"「{frag}」と感じられたのですね。なるほど、とても共感できます。",
        "そうしたお気持ちは自然な流れであり、私も同じように思うことがあります。",
        "日々の中で小さな発見や感情が積み重なって、あなたらしさを形作っているのだと感じます。",
        "どうかその歩幅のまま進んでください。私は隣で静かに寄り添っております。"
    ]
    reply = "\n".join(lines)
    return reply[:280]

# 送信したいスタンプのリスト (packageIdとstickerIdのペア)
STAMP_LIST = [
    ("446", "1988"),
    ("789", "10857"),
    ("11537", "52002734"),
    ("11538", "51626494"),
]

# --- ▲▲▲ ここまで追加 ▲▲▲ ---


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

    # --- ▼▼▼ 返信の種類をランダムに決定 ▼▼▼ ---
    # 1から5までの数字をランダムに選ぶ
    choice = random.randint(1, 5)

    # 1ならスタンプ
    if choice == 1:
        package_id, sticker_id = random.choice(STAMP_LIST)
        reply_object = [StickerMessage(packageId=package_id, stickerId=sticker_id)]
    
    # 2なら長文
    elif choice == 2:
        reply_text = make_long_reply(user_message)
        reply_object = [TextMessage(text=reply_text)]

    # 3, 4, 5ならAI (短文)
    else:
        try:
            response = gemini_model.generate_content(user_message)
            ai_response_text = response.text.strip()
            reply_object = [TextMessage(text=ai_response_text)]
        except Exception as e:
            app.logger.error(f"Gemini AI Error: {e}")
            error_text = "ごめんなさい、少し調子が悪いみたいです…"
            reply_object = [TextMessage(text=error_text)]

    # --- ▲▲▲ ここまで変更 ▲▲▲ ---

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
