import unittest
from unittest.mock import Mock, patch
from app import create_app, db
from app.models import Paper
from app.services.analysis_service import AnalysisService
from app.services.scholar_service import ScholarService
import json

class TestAnalysisService(unittest.TestCase):
    """データ分析サービスのテスト"""
    
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.analysis_service = AnalysisService()
        
        # テスト用の論文データを作成
        self.test_papers = [
            Paper(
                title="Machine Learning in Healthcare",
                authors=["John Doe", "Jane Smith"],
                abstract="This paper discusses ML applications in healthcare.",
                publication_year=2023,
                journal="Nature Medicine",
                citations=50
            ),
            Paper(
                title="Deep Learning for Medical Imaging",
                authors=["Jane Smith", "Bob Johnson"],
                abstract="A comprehensive review of deep learning techniques.",
                publication_year=2022,
                journal="Medical Image Analysis",
                citations=75
            ),
            Paper(
                title="AI Ethics in Healthcare",
                authors=["Alice Brown"],
                abstract="Ethical considerations for AI in medical applications.",
                publication_year=2023,
                journal="Nature Medicine",
                citations=25
            )
        ]
        
        for paper in self.test_papers:
            db.session.add(paper)
        db.session.commit()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_get_statistics(self):
        """統計情報取得のテスト"""
        stats = self.analysis_service.get_statistics(self.test_papers)
        
        self.assertEqual(stats['total_papers'], 3)
        self.assertEqual(len(stats['year_distribution']['years']), 2)
        self.assertEqual(stats['citation_stats']['total'], 150)
        self.assertEqual(stats['citation_stats']['mean'], 50.0)
    
    def test_extract_keywords(self):
        """キーワード抽出のテスト"""
        keywords = self.analysis_service.extract_keywords(self.test_papers, top_n=5)
        
        self.assertIsInstance(keywords, list)
        self.assertTrue(len(keywords) <= 5)
        # "healthcare" が頻出キーワードに含まれることを確認
        keyword_words = [kw[0] for kw in keywords]
        self.assertTrue(any('healthcare' in word.lower() for word in keyword_words))
    
    def test_find_topics(self):
        """トピックモデリングのテスト"""
        # 論文数が少ないため、トピック数を調整
        topics = self.analysis_service.find_topics(self.test_papers, n_topics=2)
        
        if 'error' not in topics:
            self.assertEqual(topics['n_topics'], 2)
            self.assertEqual(len(topics['topics']), 2)
            # 各トピックに単語が含まれることを確認
            for topic in topics['topics']:
                self.assertIn('words', topic)
                self.assertTrue(len(topic['words']) > 0)

class TestScholarService(unittest.TestCase):
    """Google Scholar連携サービスのテスト"""
    
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.scholar_service = ScholarService()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    @patch('app.services.scholar_service.scholarly')
    def test_search_papers(self, mock_scholarly):
        """論文検索のテスト"""
        # モックデータの設定
        mock_article = {
            'bib': {
                'title': 'Test Paper',
                'author': ['Test Author'],
                'abstract': 'Test abstract',
                'pub_year': '2023',
                'venue': 'Test Journal'
            },
            'scholar_id': 'test123',
            'num_citations': 10,
            'pub_url': 'http://example.com',
            'eprint_url': 'http://example.com/pdf'
        }
        
        mock_scholarly.search_pubs.return_value = [mock_article]
        
        # 検索実行
        results = self.scholar_service.search_papers('test query', max_results=1)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Test Paper')
        self.assertEqual(results[0]['citations'], 10)
    
    def test_build_year_query(self):
        """年範囲クエリ構築のテスト"""
        # 両方指定
        query = self.scholar_service._build_year_query(2020, 2023)
        self.assertEqual(query, "after:2020 before:2023")
        
        # 開始年のみ
        query = self.scholar_service._build_year_query(2020, None)
        self.assertEqual(query, "after:2020")
        
        # 終了年のみ
        query = self.scholar_service._build_year_query(None, 2023)
        self.assertEqual(query, "before:2023")

class TestAPIEndpoints(unittest.TestCase):
    """APIエンドポイントのテスト"""
    
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_search_api(self):
        """検索APIのテスト"""
        with patch('app.main.routes.scholar_service') as mock_service:
            mock_service.search_papers.return_value = [
                {
                    'id': 1,
                    'title': 'Test Paper',
                    'authors': ['Test Author'],
                    'publication_year': 2023,
                    'citations': 10
                }
            ]
            
            response = self.client.post('/api/search',
                data=json.dumps({
                    'query': 'machine learning',
                    'type': 'keyword',
                    'page': 1
                }),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data['success'])
            self.assertEqual(len(data['results']), 1)
    
    def test_statistics_api(self):
        """統計APIのテスト"""
        # テストデータを作成
        paper = Paper(
            title="Test Paper",
            authors=["Test Author"],
            publication_year=2023,
            citations=50
        )
        db.session.add(paper)
        db.session.commit()
        
        response = self.client.post('/api/statistics',
            data=json.dumps({'paper_ids': [paper.id]}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('statistics', data)
    
    def test_bookmark_api(self):
        """ブックマークAPIのテスト"""
        # テスト用の論文を作成
        paper = Paper(
            title="Test Paper",
            authors=["Test Author"],
            publication_year=2023
        )
        db.session.add(paper)
        db.session.commit()
        
        # ブックマーク追加
        response = self.client.post('/api/bookmark',
            data=json.dumps({
                'paper_id': paper.id,
                'note': 'Test bookmark',
                'tags': ['test', 'bookmark']
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])

if __name__ == '__main__':
    unittest.main()