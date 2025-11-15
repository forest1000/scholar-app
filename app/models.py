from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import JSON

class Bookmark(db.Model):
    """ブックマーク機能（論文情報を保存）
        SQLAlchemyが自動的に__init__を生成するためdef __init__(self,)を書かない
    """
    __tablename__ = 'bookmarks'

    id = db.Column(db.Integer, primary_key=True)

    # 論文情報
    title = db.Column(db.Text, nullable=False)
    abstract = db.Column(JSON)
    publication_year = db.Column(db.Integer, index=True)
    url = db.Column(db.Text)

    # bookmarkされた日時
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'abstract': self.abstract,
            'publication_year': self.publication_year,
            'url': self.url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

