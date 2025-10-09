import pandas as pd
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from app.models import Paper
import re

# NLTKデータのダウンロード（初回のみ必要）
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')

class AnalysisService:
    """
    データマイニング処理を担当するサービスクラス
    """
    
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        # 学術論文特有のストップワードを追加
        self.stop_words.update([
            'paper', 'study', 'research', 'method', 'approach', 
            'result', 'conclusion', 'abstract', 'introduction'
        ])
    
    def get_statistics(self, papers: List[Paper]) -> Dict:
        """論文集合の統計情報を取得"""
        if not papers:
            return {}
        
        df = self._papers_to_dataframe(papers)
        
        stats = {
            'total_papers': len(papers),
            'year_distribution': self._get_year_distribution(df),
            'top_authors': self._get_top_authors(df),
            'citation_stats': self._get_citation_statistics(df),
            'publication_trend': self._get_publication_trend(df)
        }
        
        return stats
    
    def extract_keywords(self, papers: List[Paper], top_n: int = 20) -> List[Tuple[str, float]]:
        """頻出キーワードを抽出"""
        # タイトルとアブストラクトを結合
        texts = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract}" if paper.abstract else paper.title
            texts.append(text)
        
        if not texts:
            return []
        
        # TF-IDFベクトル化
        vectorizer = TfidfVectorizer(
            max_features=top_n * 2,
            stop_words='english',
            ngram_range=(1, 2),  # ユニグラムとバイグラム
            preprocessor=self._preprocess_text
        )
        
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()
            
            # 全文書での重要度を計算
            tfidf_scores = np.array(tfidf_matrix.sum(axis=0)).flatten()
            
            # スコアでソート
            top_indices = tfidf_scores.argsort()[-top_n:][::-1]
            
            keywords = [(feature_names[i], float(tfidf_scores[i])) for i in top_indices]
            
            return keywords
        except Exception as e:
            print(f"Error in keyword extraction: {e}")
            return []
    
    def find_topics(self, papers: List[Paper], n_topics: int = 5) -> Dict:
        """トピックモデリング（LDA）を実行"""
        texts = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract}" if paper.abstract else paper.title
            texts.append(text)
        
        if len(texts) < n_topics:
            return {'error': 'Not enough papers for topic modeling'}
        
        # ベクトル化
        vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            preprocessor=self._preprocess_text
        )
        
        doc_term_matrix = vectorizer.fit_transform(texts)
        
        # LDAモデル
        lda = LatentDirichletAllocation(
            n_components=n_topics,
            random_state=42,
            max_iter=10
        )
        
        lda.fit(doc_term_matrix)
        
        # トピックごとの重要単語を抽出
        feature_names = vectorizer.get_feature_names_out()
        topics = []
        
        for topic_idx, topic in enumerate(lda.components_):
            top_words_idx = topic.argsort()[-10:][::-1]
            top_words = [feature_names[i] for i in top_words_idx]
            topics.append({
                'topic_id': topic_idx,
                'words': top_words,
                'weights': [float(topic[i]) for i in top_words_idx]
            })
        
        return {'topics': topics, 'n_topics': n_topics}
    
    def get_co_occurrence_network(self, papers: List[Paper], min_count: int = 3) -> Dict:
        """共起ネットワークデータを生成"""
        # キーワードのペアをカウント
        co_occurrences = Counter()
        
        for paper in papers:
            text = self._preprocess_text(f"{paper.title} {paper.abstract}" if paper.abstract else paper.title)
            words = [w for w in word_tokenize(text.lower()) if w.isalpha() and len(w) > 3]
            words = [w for w in words if w not in self.stop_words]
            
            # 同じ論文内での単語ペアを作成
            unique_words = list(set(words))
            for i in range(len(unique_words)):
                for j in range(i + 1, len(unique_words)):
                    pair = tuple(sorted([unique_words[i], unique_words[j]]))
                    co_occurrences[pair] += 1
        
        # 最小出現回数でフィルタリング
        filtered_pairs = [(pair, count) for pair, count in co_occurrences.items() if count >= min_count]
        
        # ネットワークデータとして整形
        nodes = set()
        edges = []
        
        for (word1, word2), count in filtered_pairs:
            nodes.add(word1)
            nodes.add(word2)
            edges.append({
                'source': word1,
                'target': word2,
                'weight': count
            })
        
        return {
            'nodes': list(nodes),
            'edges': edges
        }
    
    def _papers_to_dataframe(self, papers: List[Paper]) -> pd.DataFrame:
        """論文リストをDataFrameに変換"""
        data = []
        for paper in papers:
            data.append({
                'title': paper.title,
                'authors': paper.authors,
                'year': paper.publication_year,
                'citations': paper.citations,
                'abstract': paper.abstract
            })
        return pd.DataFrame(data)
    
    def _get_year_distribution(self, df: pd.DataFrame) -> Dict:
        """年ごとの論文数分布"""
        year_counts = df['year'].value_counts().sort_index()
        return {
            'years': year_counts.index.tolist(),
            'counts': year_counts.values.tolist()
        }
    
    def _get_top_authors(self, df: pd.DataFrame, top_n: int = 10) -> List[Dict]:
        """トップ著者を取得"""
        all_authors = []
        for authors in df['authors'].dropna():
            if isinstance(authors, list):
                all_authors.extend(authors)
        
        author_counts = Counter(all_authors)
        top_authors = author_counts.most_common(top_n)
        
        return [{'name': author, 'count': count} for author, count in top_authors]

    
    def _preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        # 小文字化と記号の除去
        text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
        # 複数スペースを単一に
        text = re.sub(r'\s+', ' ', text)
        return text.strip()