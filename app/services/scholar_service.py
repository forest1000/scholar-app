import time
import logging
from typing import List, Dict, Optional
import arxiv
from arxiv_query_builder import build_query, run
from app.models import Paper, db
from flask import current_app

logger = logging.getLogger(__name__)

class ScholarService:
    """arXivとの連携処理を担当するサービスクラス（既存のインターフェースを維持）"""

    def __init__(self):

        self.wait_time = current_app.config.get('ARXIV_WAIT_TIME',
                           current_app.config.get('SCHOLAR_WAIT_TIME', 2))
        self.max_results = current_app.config.get('MAX_RESULTS_PER_QUERY', 100)
        self.mock_mode = current_app.config.get('MOCK_ARXIV',
                           current_app.config.get('MOCK_SCHOLAR', True))

    def search_papers(self, query: str, year_from: Optional[int] = None,
                      year_to: Optional[int] = None, max_results: Optional[int] = None) -> List[Dict]:
        """論文を検索する（arXiv）"""

        if self.mock_mode:
            logger.info(f"Mock mode: Searching for '{query}'")
            return self._get_mock_results(query, year_from, year_to, max_results)

        results: List[Dict] = []
        max_results = max_results or self.max_results

        try:
            # 年で絞りたい場合はクライアント側でフィルタ（arXivは年フィルタのネイティブサポートが弱いため）
            # マッチ抜けを避けるため一旦少し多めに取ってから年で間引く
            fetch_upper_bound = max_results * 2 if (year_from or year_to) else max_results

            logger.info(f"Searching on arXiv for: {query}")
            search = arxiv.Search(
                query=query,
                max_results=fetch_upper_bound,
                sort_by=arxiv.SortCriterion.Relevance
            )

            for i, result in enumerate(search.results()):
                if i > 0:
                    time.sleep(self.wait_time)

                pub_year = result.published.year if result.published else None
                if not self._year_ok(pub_year, year_from, year_to):
                    continue

                paper_info = self._extract_paper_info(result)
                results.append(paper_info)
                self._save_paper(paper_info)

                if len(results) >= max_results:
                    break

        except Exception as e:
            error_msg = f"arXiv接続エラー: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg)

        return results

    def search_by_author(self, author_name: str, max_results: Optional[int] = None) -> List[Dict]:
        """著者名で論文を検索（arXiv）"""
        if self.mock_mode:
            return self._get_mock_results(f"papers by {author_name}", None, None, max_results)

        results: List[Dict] = []
        max_results = max_results or self.max_results

        try:
            # arXivの著者検索はクエリで au:"Name"
            query = f'au:"{author_name}"'
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )

            for i, result in enumerate(search.results()):
                if i > 0:
                    time.sleep(self.wait_time)

                paper_info = self._extract_paper_info(result)
                results.append(paper_info)
                self._save_paper(paper_info)

        except Exception as e:
            logger.error(f"Error searching by author on arXiv: {str(e)}", exc_info=True)
            raise

        return results

    def _get_mock_results(self, query: str, year_from: Optional[int],
                          year_to: Optional[int], max_results: Optional[int]) -> List[Dict]:
        """モックデータを返す（そのまま流用）"""
        max_results = max_results or 10

        mock_papers = []
        for i in range(min(max_results, 5)):
            year = year_from if year_from else 2024
            mock_papers.append({
                'scholar_id': f'mock_{i}_{hash(query) % 10000}',  # フィールド名は維持
                'title': f'{query.title()} - Research Paper {i+1}',
                'authors': [f'Author {i*2+1}', f'Author {i*2+2}'],
                'abstract': (f'This is a mock abstract for a paper about {query}. '
                             f'It demonstrates various techniques and applications in the field. '
                             f'The research presents novel approaches to solving key challenges.'),
                'publication_year': year + (i % 2),
                'citations': (i + 1) * 15,
                'url': f'https://example.com/paper/{i}',
                'pdf_link': f'https://example.com/paper/{i}.pdf'
            })

        return mock_papers

    def get_paper_details(self, scholar_id: str) -> Optional[Dict]:
        """論文の詳細情報を取得（DB優先、arXivの個別取得は行わない挙動も維持）"""
        paper = Paper.query.filter_by(scholar_id=scholar_id).first()
        if paper:
            return paper.to_dict()

        try:
            return None
        except Exception as e:
            logger.error(f"Error getting paper details: {str(e)}")
            return None

    # ===== arXiv用の内部ヘルパ =====

    def _extract_paper_info(self, result: "arxiv.Result") -> Dict:
        """arxiv.Result から必要情報を抽出して既存スキーマに合わせる"""
        arxiv_id = self._normalize_arxiv_id(result.entry_id)
        authors = []
        try:
            authors = [a.name for a in result.authors]
        except Exception:
            authors = [str(a) for a in result.authors] if result.authors else []

        return {
            # 既存のDBスキーマ互換のためキー名は scholar_id のまま
            'scholar_id': arxiv_id,
            'title': (result.title or "").strip(),
            'authors': authors,
            'abstract': (result.summary or "").strip(),
            'publication_year': result.published.year if result.published else None,
            'url': result.entry_id,     # 例: https://arxiv.org/abs/2101.12345v2
            'pdf_link': result.pdf_url  # 例: https://arxiv.org/pdf/2101.12345v2.pdf
        }

    def _normalize_arxiv_id(self, entry_id: str) -> str:
        """entry_id(URL)から安定したID（absの末尾）を抽出"""
        # 例: https://arxiv.org/abs/2101.12345v2 -> 2101.12345v2
        try:
            return entry_id.rstrip('/').split('/')[-1]
        except Exception:
            return entry_id

    def _year_ok(self, pub_year: Optional[int],
                 year_from: Optional[int], year_to: Optional[int]) -> bool:
        """公開年の範囲チェック"""
        if pub_year is None:
            # 年不明のものは絞り込みが指定されている場合は除外
            return not (year_from or year_to)
        if year_from and pub_year < year_from:
            return False
        if year_to and pub_year > year_to:
            return False
        return True

    def _save_paper(self, paper_info: Dict):
        """論文情報をデータベースに保存（そのまま流用）"""
        try:
            paper = Paper.query.filter_by(scholar_id=paper_info['scholar_id']).first()
            if not paper:
                paper = Paper()

            for key, value in paper_info.items():
                if hasattr(paper, key):
                    setattr(paper, key, value)

            db.session.add(paper)
            db.session.commit()

        except Exception as e:
            logger.error(f"Error saving paper: {str(e)}")
            db.session.rollback()

    def _build_year_query(self, year_from: Optional[int], year_to: Optional[int]) -> str:
        """互換用に残しておくが、arXiv検索では未使用"""
        if year_from and year_to:
            return f"after:{year_from} before:{year_to}"
        elif year_from:
            return f"after:{year_from}"
        elif year_to:
            return f"before:{year_to}"
        return ""
