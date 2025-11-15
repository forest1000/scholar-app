"""
学術論文検索・分析システム
メインアプリケーション起動スクリプト
"""

import os
import sys
import logging
from flask import Flask
from flask_migrate import Migrate, upgrade
from app import create_app, db
from config import get_config

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数から設定を取得
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)



@app.cli.command()
def init_db():
    """データベースを初期化"""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized successfully")

@app.cli.command()
def seed_db():
    """テストデータを投入"""
    from app.models import Paper
    
    with app.app_context():
        # サンプル論文データ
        sample_papers = [
            {
                'scholar_id': 'sample_001',
                'title': 'Deep Learning for Natural Language Processing: A Survey',
                'authors': ['John Doe', 'Jane Smith'],
                'abstract': 'This paper provides a comprehensive survey of deep learning techniques...',
                'publication_year': 2023,
                'citations': 150
            },
            {
                'scholar_id': 'sample_002', 
                'title': 'Advances in Computer Vision with Transformers',
                'authors': ['Alice Johnson', 'Bob Wilson'],
                'abstract': 'We explore the application of transformer architectures to computer vision...',
                'publication_year': 2024,
                'citations': 75
            }
        ]
        
        for paper_data in sample_papers:
            paper = Paper(**paper_data)
            db.session.add(paper)
        
        db.session.commit()
        logger.info(f"Added {len(sample_papers)} sample papers to database")

@app.cli.command()
def download_models():
    """必要なAIモデルをダウンロード"""
    from app.services.llm_service import FeatureSearchService
    
    logger.info("Downloading required models...")
    service = FeatureSearchService()
    logger.info("Models downloaded successfully")

@app.shell_context_processor
def make_shell_context():
    """Flaskシェルコンテキスト"""
    from app.models import Paper, SearchSession, Bookmark
    from app.services.llm_service import FeatureSearchService
    
    return {
        'db': db,
        'Paper': Paper,
        'SearchSession': SearchSession,
        'Bookmark': Bookmark,
        'FeatureSearchService': FeatureSearchService
    }

if __name__ == '__main__':
    # 開発サーバーの起動
    port = int(os.environ.get('PORT', 5000))
    debug = config_name == 'development'
    
    logger.info(f"Starting application in {config_name} mode on port {port}")
    
    # 本番環境ではGunicornなどのWSGIサーバーを使用することを推奨
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )


