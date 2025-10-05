import os
from app import create_app, db
from app.models import Paper, SearchSession, Bookmark

app = create_app(os.getenv('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    """Flaskシェルコンテキストの設定"""
    return {
        'db': db,
        'Paper': Paper,
        'SearchSession': SearchSession,
        'Bookmark': Bookmark
    }

if __name__ == '__main__':
    with app.app_context():
        # データベーステーブルの作成
        db.create_all()
        print("Database tables created.")
    
    # 開発サーバーの起動
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )