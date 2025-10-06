from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from datetime import datetime

class User(UserMixin, db.Model):
    """ユーザーモデル"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # プロフィール情報
    full_name = db.Column(db.String(120))
    institution = db.Column(db.String(200))
    research_interests = db.Column(db.Text)
    
    # タイムスタンプ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # リレーションシップ
    bookmarks = db.relationship('UserBookmark', back_populates='user', cascade='all, delete-orphan')
    search_sessions = db.relationship('UserSearchSession', back_populates='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """パスワードをハッシュ化して保存"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """パスワードの検証"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """最終ログイン時刻を更新"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """ユーザー情報を辞書形式で返す"""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'institution': self.institution,
            'research_interests': self.research_interests,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserBookmark(db.Model):
    """ユーザー固有のブックマーク"""
    __tablename__ = 'user_bookmarks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey('papers.id'), nullable=False)
    note = db.Column(db.Text)
    tags = db.Column(db.JSON)
    is_favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', back_populates='bookmarks')
    paper = db.relationship('Paper')
    
    def to_dict(self):
        return {
            'id': self.id,
            'paper': self.paper.to_dict(),
            'note': self.note,
            'tags': self.tags,
            'is_favorite': self.is_favorite,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class UserSearchSession(db.Model):
    """ユーザー固有の検索セッション"""
    __tablename__ = 'user_search_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_name = db.Column(db.String(255), nullable=False)
    query = db.Column(db.Text)
    filters = db.Column(db.JSON)
    search_type = db.Column(db.String(50))  # keyword, author, llm
    results_count = db.Column(db.Integer)
    is_saved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', back_populates='search_sessions')
    papers = db.relationship('Paper', secondary='user_session_papers')
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_name': self.session_name,
            'query': self.query,
            'filters': self.filters,
            'search_type': self.search_type,
            'results_count': self.results_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 中間テーブル（ユーザーセッションと論文の関連）
user_session_papers = db.Table('user_session_papers',
    db.Column('session_id', db.Integer, db.ForeignKey('user_search_sessions.id'), primary_key=True),
    db.Column('paper_id', db.Integer, db.ForeignKey('papers.id'), primary_key=True)
)