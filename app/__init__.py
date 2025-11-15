from flask import Flask
from flask_migrate import Migrate
from config import config
from app.database import db

migrate = Migrate()

def create_app(config_name='default'):
    """アプリケーションファクトリー"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    db.init_app(app)
    migrate.init_app(app, db)

    from app import models
        
    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # LLMルートの登録
    from app.main.llm_routes import llm_bp
    app.register_blueprint(llm_bp)
    
    return app