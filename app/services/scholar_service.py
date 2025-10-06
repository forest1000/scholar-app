import time
import logging
from typing import List, Dict, Optional
from scholarly import scholarly
from app.models import Paper, db
from flask import current_app

logger = logging.getLogger(__name__)

class ScholarService:
    """Google Scholarとの連携処理を担当するサービスクラス"""
    
    def __init__(self):
        self.wait_time = current_app.config.get('SCHOLAR_WAIT_TIME', 2)
        self.max_results = current_app.config.get('MAX_RESULTS_PER_QUERY', 100)
    
    def search_papers(self, query: str, year_from: Optional[int] = None, 
                     year_to: Optional[int] = None, max_results: Optional[int] = None) -> List[Dict]:
        """
        論文を検索する
        
        Args:
            query: 検索クエリ
            year_from: 開始年
            year_to: 終了年
            max_results: 最大取得件数
            
        Returns:
            論文情報のリスト
        """
        results = []
        max_results = max_results or self.max_results
        
        try:
            # 年範囲の指定がある場合はクエリに追加
            if year_from or year_to:
                year_query = self._build_year_query(year_from, year_to)
                query = f"{query} {year_query}"
            
            search_query = scholarly.search_pubs(query)
            
            for i, article in enumerate(search_query):
                if i >= max_results:
                    break
                
                # レート制限対策
                if i > 0:
                    time.sleep(self.wait_time)
                
                paper_info = self._extract_paper_info(article)
                results.append(paper_info)
                
                # データベースに保存
                self._save_paper(paper_info)
                
        except Exception as e:
            logger.error(f"Error searching papers: {str(e)}")
            raise
        
        return results
    
    def search_by_author(self, author_name: str, max_results: Optional[int] = None) -> List[Dict]:
        """著者名で論文を検索"""
        results = []
        max_results = max_results or self.max_results
        
        try:
            search_query = scholarly.search_author(author_name)
            authors = list(search_query)
            
            if authors:
                # 最初の著者の詳細を取得
                author = scholarly.fill(authors[0])
                
                for i, pub in enumerate(author['publications'][:max_results]):
                    if i > 0:
                        time.sleep(self.wait_time)
                    
                    # 論文の詳細情報を取得
                    pub_filled = scholarly.fill(pub)
                    paper_info = self._extract_paper_info(pub_filled)
                    results.append(paper_info)
                    self._save_paper(paper_info)
                    
        except Exception as e:
            logger.error(f"Error searching by author: {str(e)}")
            raise
        
        return results
    
    def get_paper_details(self, scholar_id: str) -> Optional[Dict]:
        """論文の詳細情報を取得"""
        # まずDBから検索
        paper = Paper.query.filter_by(scholar_id=scholar_id).first()
        if paper:
            return paper.to_dict()
        
        # DBにない場合はGoogle Scholarから取得
        try:
            # IDで直接検索する方法は限定的なので、タイトル検索を使用
            # 実際の実装では、より確実な方法を検討する必要がある
            return None
        except Exception as e:
            logger.error(f"Error getting paper details: {str(e)}")
            return None
    
    def _extract_paper_info(self, article: Dict) -> Dict:
        """scholarlyの結果から必要な情報を抽出"""
        bib = article.get('bib', {})
        
        return {
            'scholar_id': article.get('scholar_id', ''),
            'title': bib.get('title', ''),
            'authors': bib.get('author', []) if isinstance(bib.get('author'), list) else [bib.get('author', '')],
            'abstract': bib.get('abstract', ''),
            'publication_year': int(bib.get('pub_year', 0)) if bib.get('pub_year') else None,
            'journal': bib.get('venue', ''),
            'citations': article.get('num_citations', 0),
            'url': article.get('pub_url', ''),
            'pdf_link': article.get('eprint_url', '')
        }
    
    def _save_paper(self, paper_info: Dict):
        """論文情報をデータベースに保存"""
        try:
            paper = Paper.query.filter_by(scholar_id=paper_info['scholar_id']).first()
            
            if not paper:
                paper = Paper()
            
            # 情報を更新
            for key, value in paper_info.items():
                if hasattr(paper, key):
                    setattr(paper, key, value)
            
            db.session.add(paper)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error saving paper: {str(e)}")
            db.session.rollback()
    
    def _build_year_query(self, year_from: Optional[int], year_to: Optional[int]) -> str:
        """年範囲のクエリを構築"""
        if year_from and year_to:
            return f"after:{year_from} before:{year_to}"
        elif year_from:
            return f"after:{year_from}"
        elif year_to:
            return f"before:{year_to}"
        return ""