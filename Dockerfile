# Pythonの公式イメージをベースにする
FROM python:3.11-slim

# 環境変数を設定
ENV APP_HOME /app
WORKDIR $APP_HOME

# 必要なライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# プロジェクトのファイルをコピー
COPY . .

# コンテナの起動コマンド (gunicornを使用)
# LINE.pyの中のFlaskアプリ変数「app」を起動
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 LINE:app
