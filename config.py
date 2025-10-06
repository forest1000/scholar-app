import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """基本設定クラス"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://user:pass@localhost/scholar_app'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Google Scholar settings
    SCHOLAR_WAIT_TIME = 2 # リクエスト間の待機時間（秒）
    MAX_RESULTS_PER_QUERY = 20
    
    MOCK_SCHOLAR = False
    
    # LLM settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = "gpt-4"
    
    # Local LLM settings
    LOCAL_MODEL_CACHE_DIR = os.environ.get('LOCAL_MODEL_CACHE_DIR') or \
        os.path.expanduser('~/.cache/scholar_app/models')
    MAX_MODEL_CACHE_SIZE_GB = 50  # モデルキャッシュの最大サイズ
    
    # Cache settings
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CACHE_DEFAULT_TIMEOUT = 3600  # 1時間
    
    # Celery settings
    CELERY_BROKER_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # UI settings
    ITEMS_PER_PAGE = 20
    
class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    
class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    
    # Production specific settings
    PREFERRED_URL_SCHEME = 'https'
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}