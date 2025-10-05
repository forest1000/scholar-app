# Flask設定
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-in-production

# データベース設定
DATABASE_URL=postgresql://username:password@localhost:5432/scholar_app

# OpenAI API設定
OPENAI_API_KEY=your-openai-api-key

# Redis設定（キャッシュ用）
REDIS_URL=redis://localhost:6379/0

# Google Scholar設定
SCHOLAR_WAIT_TIME=2
MAX_RESULTS_PER_QUERY=100