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
    SCHOLAR_WAIT_TIME = 2  # リクエスト間の待機時間（秒）
    MAX_RESULTS_PER_QUERY = 100
    
    # LLM settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = "gpt-4"
    
    # Cache settings
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CACHE_DEFAULT_TIMEOUT = 3600  # 1時間
    
    # UI settings
    ITEMS_PER_PAGE = 20
    
class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    
class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}