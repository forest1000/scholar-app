import os
from datetime import timedelta

class Config:
    """基本設定クラス"""
    # Flask設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # データベース設定
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///scholar_research.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ページネーション
    ITEMS_PER_PAGE = 10
    
    # arXiv設定
    ARXIV_WAIT_TIME = 0.1  # API呼び出し間の待機時間（秒）
    MAX_RESULTS_PER_QUERY = 3
    MOCK_ARXIV = False  # 開発時はTrueにしてモックデータを使用
    
    # セッション設定
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_TYPE = 'filesystem'
    
    # ファイルアップロード設定
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}
    
    # Celery設定（非同期タスク用）
    CELERY_BROKER_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # キャッシュ設定
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # ロギング設定
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    
    # AI/ML設定（OpenAI不使用）
    USE_LOCAL_MODELS = True
    EMBEDDING_MODEL_NAME = 'intfloat/multilingual-e5-large'
    SUMMARIZER_MODEL_NAME = 'sonoisa/t5-base-japanese'  # 日本語対応
    DEFAULT_DEVICE = 'cuda' if os.environ.get('CUDA_VISIBLE_DEVICES') else 'cpu'
    
    # モデルキャッシュディレクトリ
    MODEL_CACHE_DIR = os.path.join(os.path.expanduser('~'), '.cache', 'scholar_app', 'models')
    
    # ベクトル検索設定
    VECTOR_DIMENSION = 1024  # multilingual-e5-largeの次元数
    FAISS_INDEX_TYPE = 'Flat'  # or 'IVF' for large datasets
    
    # 言語設定
    DEFAULT_LANGUAGE = 'ja'
    SUPPORTED_LANGUAGES = ['ja', 'en']


class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = False
    TESTING = False
    MOCK_ARXIV = False  # 開発時はモックデータを使用
    
    # SQLiteを使用（開発環境）
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev_scholar.db'
    
    # より詳細なロギング
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = True  # SQLクエリをログに出力


class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    TESTING = False
    MOCK_ARXIV = False
    
    # PostgreSQLを使用（本番環境）
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        # HerokuのPostgreSQLのURIを修正
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    # セキュリティ設定
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    
    # パフォーマンス設定
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }


class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    DEBUG = True
    
    # インメモリSQLiteを使用
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # テスト用の設定
    WTF_CSRF_ENABLED = False
    MOCK_ARXIV = True


# 設定の選択
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """設定オブジェクトを取得"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config.get(config_name, DevelopmentConfig)