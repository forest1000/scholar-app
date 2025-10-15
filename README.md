# 学術論文検索・分析システム (AI Feature Search)

## 概要

このシステムは、arXivから学術論文を検索し、AI技術を活用して高度な特徴量検索と分析を行うWebアプリケーションです。OpenAIに依存せず、完全にローカルで動作するHugging FaceモデルとFAISSを使用しています。

## 主な機能

### 🔍 AI特徴量検索
- **自然言語クエリ**: 「深層学習を使った画像認識の新しい手法を提案している論文」のような自然な文章で検索
- **ベクトル類似度検索**: HuggingFace Embeddingsを使用した意味的類似度による検索
- **論文分析**: 各論文の背景、手法、新規性を自動抽出
- **コサイン類似度計算**: 検索クエリと論文のベクトル表現の類似度を計算し、上位K件を選択

### 📊 基本機能
- キーワード検索、著者名検索
- 年代別フィルタリング
- データマイニング（頻出キーワード抽出、トピックモデリング）
- 統計分析とビジュアライゼーション
- ブックマーク機能
- 検索セッション管理

## 技術スタック

### バックエンド
- **Flask**: Webフレームワーク
- **SQLAlchemy**: ORM
- **LangChain**: LLM統合フレームワーク
- **FAISS**: ベクトル類似度検索
- **HuggingFace Transformers**: 事前学習済みモデル
- **scikit-learn**: 機械学習ライブラリ

### AI/MLモデル（OpenAI不使用）
- **Embeddings**: `intfloat/multilingual-e5-large` (多言語対応)
- **Summarization**: `sonoisa/t5-base-japanese` (日本語対応)
- **Text Processing**: NLTK, spaCy

### フロントエンド
- **Vue.js 3**: リアクティブUI
- **Axios**: HTTP通信
- **Chart.js**: データビジュアライゼーション

## セットアップ

### 1. 環境構築

```bash
# リポジトリのクローン
git clone 
cd scholar-research-assistant

# Python仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt

# NLTKデータのダウンロード
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
```

### 2. データベース初期化

```bash
# データベースの作成
flask init-db

# サンプルデータの投入（オプション）
flask seed-db
```

### 3. モデルのダウンロード

```bash
# 必要なAIモデルをダウンロード（初回のみ）
flask download-models
```

### 4. 環境変数の設定

`.env`ファイルを作成:

```env
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///scholar_research.db

# GPU使用時（オプション）
CUDA_VISIBLE_DEVICES=0
```

## 起動方法

### 開発サーバー

```bash
# Flaskアプリケーションの起動
python run.py

# または
flask run
```

アプリケーションは `http://localhost:5000` でアクセス可能です。

### 本番環境

```bash
# Gunicornを使用（推奨）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

## AI特徴量検索の使い方

1. **検索ページへアクセス**
   - トップページから「検索を開始」をクリック

2. **検索タイプの選択**
   - 「AI特徴量検索」を選択

3. **自然言語でクエリ入力**
   - 例：「強化学習を医療診断に応用した研究」
   - 例：「Transformerを使った時系列予測の新手法」
   - 例：「環境問題に機械学習を適用した事例」

4. **検索範囲の設定**
   - すべての論文
   - ブックマークした論文
   - 特定セッションの論文

5. **結果の確認**
   - 類似度スコアとともに上位K件の論文が表示
   - 各論文の背景、手法、新規性が自動分析されて表示

6. **ブックマーク保存**
   - 「検索結果を自動でブックマーク」オプションで一括保存可能

## プロジェクト構造

```
scholar-research-assistant/
├── app/
│   ├── __init__.py           # Flaskアプリケーション初期化
│   ├── models.py             # データベースモデル
│   ├── main/
│   │   ├── routes_v2.py     # 改良されたAPIエンドポイント
│   │   └── llm_routes.py    # LLM設定関連のルート
│   ├── services/
│   │   ├── llm_service_v2.py # AI特徴量検索サービス（OpenAI不使用）
│   │   ├── scholar_service.py # arXiv検索サービス
│   │   ├── analysis_service.py # データ分析サービス
│   │   └── export_service.py  # エクスポート機能
│   ├── templates/
│   │   ├── base.html         # ベーステンプレート
│   │   ├── index.html        # トップページ
│   │   └── search_v2.html   # AI特徴量検索ページ
│   └── static/
│       ├── css/
│       └── js/
├── config.py                 # アプリケーション設定
├── requirements.txt          # 依存パッケージ
├── run.py                   # 起動スクリプト
└── README.md                # このファイル
```

## API エンドポイント

### AI特徴量検索
- `POST /api/llm/feature-search`
  - パラメータ：query, scope, top_k, save_bookmarks
  - レスポンス：類似度順の論文リストと分析結果

### 論文分析
- `POST /api/llm/analyze-papers`
  - パラメータ：paper_ids
  - レスポンス：各論文の背景、手法、新規性

### 基本検索
- `POST /api/search`
  - パラメータ：query, type, year_from, year_to

### データマイニング
- `POST /api/mining`
  - パラメータ：paper_ids, type (keywords/topics/network)

## パフォーマンス最適化

### GPU利用
CUDAが利用可能な場合、自動的にGPUを使用します:

```python
# config.py
DEFAULT_DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
```

### ベクトルインデックス
大規模データセットの場合、FAISSのIVFインデックスを使用:

```python
# config.py
FAISS_INDEX_TYPE = 'IVF'  # デフォルトは 'Flat'
```

## トラブルシューティング

### メモリ不足エラー
- モデルサイズを削減（より小さいモデルを使用）
- バッチサイズを減らす
- CPUモードに切り替える

### モデルダウンロードエラー
- ネットワーク接続を確認
- Hugging Faceのトークンを設定（プライベートモデルの場合）

### 検索速度が遅い
- FAISSインデックスを事前構築
- GPUを使用
- 検索対象の論文数を制限

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## 謝辞

- arXiv APIを提供するCornell University
- Hugging Faceコミュニティ
- LangChainプロジェクト
- FAISSライブラリ（Meta Research）

---

**注意**: このシステムはOpenAIのAPIを使用せず、完全にローカルで動作する設計となっています。すべてのAI機能はHugging Faceの事前学習済みモデルとオープンソースライブラリで実装されています。


