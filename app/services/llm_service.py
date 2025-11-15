import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter
from app.database import db
from app.models import Bookmark
import json
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class FeatureSearchService:
    """
    HuggingFaceEmbeddingsとFAISSを用いたAI特徴量検索サービス
    OpenAIを使わずにローカルで動作
    """
    
    def __init__(self):
        # HuggingFace Embeddingsの初期化（日本語対応の多言語モデル）
        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-large",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'},
            encode_kwargs={'normalize_embeddings': True}  # コサイン類似度計算のため正規化
        )
        
        self.text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        self.vector_store = None
        self.paper_id_mapping = {}  # vector_store のインデックスとpaper_idのマッピング
        
        # 要約生成用のモデル（日本語対応）
        try:
            if torch.cuda.is_available():
                # GPUが使える場合は日本語モデルを使用
                self.summarizer_model_name = "sonoisa/t5-base-japanese"
                self.tokenizer = AutoTokenizer.from_pretrained(self.summarizer_model_name)
                self.summarizer_model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.summarizer_model_name
                ).to('cuda')
            else:
                # CPUの場合は軽量な英語モデル
                self.summarizer = pipeline(
                    "summarization",
                    model="sshleifer/distilbart-cnn-12-6",
                    device=-1
                )
                self.summarizer_model = None
        except Exception as e:
            logger.warning(f"Failed to load summarizer model: {e}")
            self.summarizer = None
            self.summarizer_model = None
    
    def perform_ai_feature_search(self, query: str, papers, top_k: int = 10) -> Dict:
        """
        AI特徴検索のメイン処理
        
        1. 論文フェッチ：どのようなタイプの論文が欲しいか入力、検索ベクトルを取得
        2. 各論文のsammaryに対して、LLMのembeddingを適用して、中間表現を獲得
        3. 検索ベクトルと中間表現のコサイン類似度を計算して、上位K個を選択して表示
        4. 上位k個のサマリーに対して、(i)論文の背景(ii)手法、新規性　の要約を出力
        """
        
        if not papers:
            return {
                'status': 'error',
                'message': 'No papers provided for search'
            }
        
        logger.info(f"Starting AI feature search with query: {query}")
        
        # 1. 検索ベクトルを取得
        query_embedding = self._get_query_embedding(query)
        
        # 2. 各論文のsummaryに対してembeddingを適用
        paper_embeddings = self._get_paper_embeddings(papers)
        
        # 3. コサイン類似度を計算して上位K個を選択
        top_papers = self._select_top_k_papers(
            query_embedding, 
            papers, 
            paper_embeddings, 
            top_k
        )
        
        # 4. 上位K個の論文に対して詳細な要約を生成
        summarized_papers = self._generate_summaries(top_papers)
        
        return {
            'status': 'success',
            'query': query,
            'total_papers': len(papers),
            'selected_papers': len(summarized_papers),
            'results': summarized_papers
        }
    
    def _get_query_embedding(self, query: str) -> np.ndarray:
        """検索クエリのベクトル表現を取得"""
        # クエリの前処理（検索用のプレフィックスを追加）
        processed_query = f"query: {query}"
        
        # ベクトル化
        query_embedding = self.embeddings.embed_query(processed_query)
        return np.array(query_embedding)
    
    def _get_paper_embeddings(self, papers: List[Bookmark]) -> Dict[int, np.ndarray]:
        """各論文のベクトル表現を取得"""
        paper_embeddings = {}
        
        for paper in papers:
            # 論文のテキストを構築（タイトル + アブストラクト）
            paper_text = self._construct_paper_text(paper)
            
            # passage用のプレフィックスを追加
            processed_text = f"passage: {paper_text}"
            
            # ベクトル化
            embedding = self.embeddings.embed_query(processed_text)
            paper_embeddings[paper.id] = np.array(embedding)
        
        logger.info(f"Generated embeddings for {len(paper_embeddings)} papers")
        return paper_embeddings
    
    def _construct_paper_text(self, paper: Bookmark) -> str:
        """論文の検索用テキストを構築"""
        parts = []
        
        if paper.title:
            parts.append(f"Title: {paper.title}")
        
        if paper.abstract:
            # アブストラクトが長すぎる場合は最初の部分だけを使用
            abstract_text = paper.abstract[:2000] if len(paper.abstract) > 2000 else paper.abstract
            parts.append(f"Abstract: {abstract_text}")
        
        if paper.authors:
            authors_str = ", ".join(paper.authors) if isinstance(paper.authors, list) else str(paper.authors)
            parts.append(f"Authors: {authors_str}")
        
        if paper.publication_year:
            parts.append(f"Year: {paper.publication_year}")
        
        return "\n".join(parts)
    
    def _select_top_k_papers(
        self, 
        query_embedding: np.ndarray, 
        papers: List[Bookmark], 
        paper_embeddings: Dict[int, np.ndarray],
        top_k: int
    ) -> List[Tuple[List, float]]:
        """コサイン類似度に基づいて上位K個の論文を選択"""
        
        similarities = []
        
        for paper in papers:
            if paper.id in paper_embeddings:
                # コサイン類似度を計算
                paper_embedding = paper_embeddings[paper.id]
                similarity = cosine_similarity(
                    query_embedding.reshape(1, -1),
                    paper_embedding.reshape(1, -1)
                )[0][0]
                
                similarities.append((paper, float(similarity)))
        
        # 類似度でソート（降順）
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 上位K個を返す
        top_papers = similarities[:top_k]
        
        logger.info(f"Selected top {len(top_papers)} papers from {len(similarities)} candidates")
        return top_papers
    
    def _generate_summaries(self, top_papers: List[Tuple[List, float]]) -> List[Dict]:
        """選択された論文の詳細な要約を生成"""
        summarized_papers = []
        
        for paper, similarity_score in top_papers:
            summary_info = {
                'paper_id': paper.id,
                'title': paper.title,
                'authors': paper.authors,
                'year': paper.publication_year,
                'similarity_score': similarity_score,
                'url': paper.url,
                'pdf_link': paper.pdf_link
            }
            
            # 論文の要約を生成
            if paper.abstract:
                analysis = self._analyze_paper(paper)
                summary_info.update(analysis)
            else:
                summary_info.update({
                    'background': 'Abstract not available',
                    'methodology': 'Abstract not available',
                    'novelty': 'Abstract not available'
                })
            
            summarized_papers.append(summary_info)
        
        return summarized_papers
    
    def _analyze_paper(self, paper: Bookmark) -> Dict[str, str]:
        """論文の背景、手法、新規性を分析"""
        
        if not paper.abstract:
            return {
                'background': 'No abstract available',
                'methodology': 'No abstract available',
                'novelty': 'No abstract available'
            }
        
        abstract = paper.abstract
        
        # 簡易的なルールベースの分析
        # 実際のプロジェクトでは、より高度なNLP技術を使用することを推奨
        
        analysis = {
            'background': self._extract_background(abstract),
            'methodology': self._extract_methodology(abstract),
            'novelty': self._extract_novelty(abstract)
        }
        
        return analysis
    
    def _extract_background(self, abstract: str) -> str:
        """論文の背景を抽出"""
        # 背景に関連するキーワード
        background_keywords = [
            'background', 'motivation', 'problem', 'challenge', 
            'existing', 'previous', 'current', 'traditional'
        ]
        
        sentences = abstract.split('.')
        background_sentences = []
        
        for sent in sentences[:3]:  # 最初の3文をチェック
            sent_lower = sent.lower()
            if any(keyword in sent_lower for keyword in background_keywords):
                background_sentences.append(sent.strip())
        
        if background_sentences:
            return '. '.join(background_sentences) + '.'
        else:
            # デフォルトで最初の文を背景として使用
            return sentences[0].strip() + '.' if sentences else 'Background information not found.'
    
    def _extract_methodology(self, abstract: str) -> str:
        """論文の手法を抽出"""
        # 手法に関連するキーワード
        method_keywords = [
            'method', 'approach', 'technique', 'algorithm', 
            'model', 'framework', 'propose', 'present',
            'develop', 'introduce', 'design', 'implement'
        ]
        
        sentences = abstract.split('.')
        method_sentences = []
        
        for sent in sentences:
            sent_lower = sent.lower()
            if any(keyword in sent_lower for keyword in method_keywords):
                method_sentences.append(sent.strip())
                if len(method_sentences) >= 2:  # 最大2文まで
                    break
        
        if method_sentences:
            return '. '.join(method_sentences) + '.'
        else:
            return 'Methodology information not explicitly stated.'
    
    def _extract_novelty(self, abstract: str) -> str:
        """論文の新規性を抽出"""
        # 新規性に関連するキーワード
        novelty_keywords = [
            'novel', 'new', 'first', 'unique', 'original',
            'innovative', 'contribution', 'advance', 'improve',
            'outperform', 'better', 'superior', 'efficient'
        ]
        
        sentences = abstract.split('.')
        novelty_sentences = []
        
        for sent in sentences:
            sent_lower = sent.lower()
            if any(keyword in sent_lower for keyword in novelty_keywords):
                novelty_sentences.append(sent.strip())
                if len(novelty_sentences) >= 2:  # 最大2文まで
                    break
        
        if novelty_sentences:
            return '. '.join(novelty_sentences) + '.'
        else:
            return 'Novelty or contribution not explicitly stated.'
    
    def save_bookmarked_papers(self, paper_ids: List[int], user_id: Optional[int] = None) -> Dict:
        """ブックマークがついた論文をデータベースに保存"""
        saved_count = 0
        errors = []
        
        for paper_id in paper_ids:
            try:
                paper = Paper.query.get(paper_id)
                if not paper:
                    errors.append(f"Paper {paper_id} not found")
                    continue
                
                # 既存のブックマークをチェック
                existing_bookmark = Bookmark.query.filter_by(paper_id=paper_id).first()
                
                if not existing_bookmark:
                    bookmark = Bookmark(
                        paper_id=paper_id,
                        note="AI Feature Search Result",
                        tags=["ai-search", "featured"],
                        created_at=datetime.utcnow()
                    )
                    db.session.add(bookmark)
                    saved_count += 1
                
            except Exception as e:
                errors.append(f"Error saving paper {paper_id}: {str(e)}")
                logger.error(f"Error saving bookmark for paper {paper_id}: {e}")
        
        try:
            db.session.commit()
            logger.info(f"Saved {saved_count} bookmarks")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error committing bookmarks: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
        
        return {
            'status': 'success',
            'saved_count': saved_count,
            'errors': errors if errors else None
        }
    
    def build_vector_index(self, papers: List[Bookmark]) -> None:
        """論文のベクトルインデックスを構築（FAISSを使用）"""
        if not papers:
            logger.warning("No papers provided for vector index building")
            return
        
        # ドキュメントを準備
        documents = []
        self.paper_id_mapping = {}
        
        for idx, paper in enumerate(papers):
            text = self._construct_paper_text(paper)
            doc = Document(
                page_content=text,
                metadata={
                    'paper_id': paper.id,
                    'title': paper.title,
                    'year': paper.publication_year
                }
            )
            documents.append(doc)
            self.paper_id_mapping[idx] = paper.id
        
        # ベクトルストアを作成
        self.vector_store = FAISS.from_documents(
            documents, 
            self.embeddings
        )
        
        logger.info(f"Vector index built with {len(papers)} papers")
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """FAISSを使用したセマンティック検索"""
        if not self.vector_store:
            logger.error("Vector index not built. Call build_vector_index first.")
            return []
        
        try:
            # 類似文書を検索
            docs_with_scores = self.vector_store.similarity_search_with_score(
                query, 
                k=top_k
            )
            
            # 結果を整形
            results = []
            
            for doc, score in docs_with_scores:
                paper_id = doc.metadata.get('paper_id')
                paper = Paper.query.get(paper_id)
                
                if paper:
                    results.append({
                        'paper': paper.to_dict(),
                        'relevance_score': float(1 - score)  # FAISSは距離を返すので変換
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []