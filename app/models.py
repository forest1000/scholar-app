from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import JSON

class Paper(db.Model):
    """論文情報のモデル"""
    __tablename__ = 'papers'
    
    id = db.Column(db.Integer, primary_key=True)
    scholar_id = db.Column(db.String(255), unique=True, index=True)
    title = db.Column(db.Text, nullable=False)
    authors = db.Column(JSON)  # ["Author1", "Author2", ...]
    abstract = db.Column(db.Text)
    publication_year = db.Column(db.Integer, index=True)
    citations = db.Column(db.Integer, default=0)
    url = db.Column(db.Text)
    pdf_link = db.Column(db.Text)
    
    # ベクトル埋め込み用
    embedding = db.Column(JSON)  # 将来的にpgvectorに移行可能
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'scholar_id': self.scholar_id,
            'title': self.title,
            'authors': self.authors,
            'abstract': self.abstract,
            'publication_year': self.publication_year,
            'citations': self.citations,
            'url': self.url,
            'pdf_link': self.pdf_link,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SearchSession(db.Model):
    """検索セッションの保存"""
    __tablename__ = 'search_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(255), nullable=False)
    query = db.Column(db.Text)
    filters = db.Column(JSON)  # 検索フィルターの保存
    results_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 論文との多対多の関係
    papers = db.relationship('Paper', secondary='session_papers', backref='sessions')

# 中間テーブル
session_papers = db.Table('session_papers',
    db.Column('session_id', db.Integer, db.ForeignKey('search_sessions.id'), primary_key=True),
    db.Column('paper_id', db.Integer, db.ForeignKey('papers.id'), primary_key=True)
)

class Bookmark(db.Model):
    """ブックマーク機能"""
    __tablename__ = 'bookmarks'
    
    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('papers.id'), nullable=False)
    note = db.Column(db.Text)
    tags = db.Column(JSON)  # ["tag1", "tag2", ...]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    paper = db.relationship('Paper', backref='bookmarks')