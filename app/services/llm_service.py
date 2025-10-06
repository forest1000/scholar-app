import os
import numpy as np
from typing import List, Dict, Optional
import openai
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.chains import RetrievalQA
from langchain_openai import OpenAI
from app.models import Paper, db
import json
import logging

logger = logging.getLogger(__name__)

class LLMService:
    """LLMとベクトル検索を用いた高度な検索機能を提供"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        openai.api_key = self.api_key
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.api_key)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.vector_store = None
    
    def build_vector_index(self, papers: List[Paper]) -> None:
        """論文のベクトルインデックスを構築"""
        if not papers:
            logger.warning("No papers provided for vector index building")
            return
        
        # 論文テキストを準備
        texts = []
        metadatas = []
        
        for paper in papers:
            # タイトルとアブストラクトを結合
            text = f"Title: {paper.title}\n"
            if paper.abstract:
                text += f"Abstract: {paper.abstract}\n"
            if paper.authors:
                text += f"Authors: {', '.join(paper.authors)}\n"
            if paper.publication_year:
                text += f"Year: {paper.publication_year}\n"
            
            texts.append(text)
            metadatas.append({
                'paper_id': paper.id,
                'title': paper.title,
                'year': paper.publication_year,
                'citations': paper.citations
            })
        
        # テキストを分割
        documents = self.text_splitter.create_documents(texts, metadatas)
        
        # ベクトルストアを作成
        self.vector_store = FAISS.from_documents(documents, self.embeddings)
        
        logger.info(f"Vector index built with {len(papers)} papers")
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """自然言語クエリによる意味的検索"""
        if not self.vector_store:
            logger.error("Vector index not built. Call build_vector_index first.")
            return []
        
        try:
            # 類似文書を検索
            docs = self.vector_store.similarity_search(query, k=top_k)
            
            # 結果を整形
            results = []
            paper_ids_seen = set()
            
            for doc in docs:
                paper_id = doc.metadata.get('paper_id')
                if paper_id and paper_id not in paper_ids_seen:
                    paper_ids_seen.add(paper_id)
                    paper = Paper.query.get(paper_id)
                    if paper:
                        results.append({
                            'paper': paper.to_dict(),
                            'relevance_score': 1.0  # FAISSは正規化されたスコアを返さないため
                        })
            
            return results
        
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []
    
    def answer_question(self, question: str, context_papers: List[Paper]) -> Dict:
        """論文を基に質問に回答"""
        if not context_papers:
            return {
                'answer': "No papers provided for context.",
                'sources': []
            }
        
        # コンテキストを構築
        context = self._build_context(context_papers[:5])  # 最大5論文まで
        
        # プロンプトを構築
        prompt = f"""Based on the following academic papers, please answer the question.

Context:
{context}

Question: {question}

Please provide a comprehensive answer based on the papers provided. If the papers don't contain relevant information, say so clearly."""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful research assistant that answers questions based on academic papers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            # ソース論文を特定
            sources = [p.to_dict() for p in context_papers[:5]]
            
            return {
                'answer': answer,
                'sources': sources
            }
        
        except Exception as e:
            logger.error(f"Error in answer_question: {str(e)}")
            return {
                'answer': "An error occurred while processing your question.",
                'sources': []
            }
    
    def extract_features(self, query: str, papers: List[Paper]) -> List[Dict]:
        """自然言語クエリに基づいて論文から特徴を抽出"""
        if not papers:
            return []
        
        # プロンプトエンジニアリング
        system_prompt = """You are an expert at analyzing academic papers and extracting specific features based on user queries.
        When given a query and paper information, identify papers that match the requested criteria and explain why."""
        
        results = []
        
        for paper in papers[:20]:  # 処理時間を考慮して最大20件
            paper_text = self._paper_to_text(paper)
            
            user_prompt = f"""Query: {query}

Paper Information:
{paper_text}

Does this paper match the query? If yes, explain specifically which aspects of the paper relate to the query.
If no, simply say "No match".

Response format:
Match: Yes/No
Explanation: [Your explanation]
Relevance Score: [0-10]"""
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                
                response_text = response.choices[0].message.content
                
                # レスポンスをパース
                if "Match: Yes" in response_text:
                    # スコアを抽出
                    score = 5  # デフォルトスコア
                    try:
                        score_line = [line for line in response_text.split('\n') if 'Relevance Score:' in line][0]
                        score = int(score_line.split(':')[-1].strip())
                    except:
                        pass
                    
                    # 説明を抽出
                    explanation = ""
                    try:
                        explanation_start = response_text.find("Explanation:") + len("Explanation:")
                        explanation_end = response_text.find("Relevance Score:")
                        explanation = response_text[explanation_start:explanation_end].strip()
                    except:
                        explanation = "Relevant to query"
                    
                    results.append({
                        'paper': paper.to_dict(),
                        'relevance_score': score / 10.0,
                        'explanation': explanation
                    })
            
            except Exception as e:
                logger.error(f"Error processing paper {paper.id}: {str(e)}")
                continue
        
        # スコアでソート
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results
    
    def generate_summary(self, papers: List[Paper]) -> str:
        """複数論文の要約を生成"""
        if not papers:
            return "No papers to summarize."
        
        # コンテキストを構築（最大10論文）
        context = self._build_context(papers[:10])
        
        prompt = f"""Please provide a comprehensive summary of the following academic papers, highlighting:
1. Main research themes
2. Key findings and contributions
3. Common methodologies
4. Future research directions mentioned

Papers:
{context}

Summary:"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at synthesizing academic research."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Error generating summary."
    
    def save_embeddings(self, paper: Paper) -> None:
        """論文の埋め込みを計算して保存"""
        try:
            text = self._paper_to_text(paper)
            embedding = self.embeddings.embed_query(text)
            
            # JSONとして保存（PostgreSQLのJSON型を使用）
            paper.embedding = embedding
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error saving embeddings for paper {paper.id}: {str(e)}")
            db.session.rollback()
    
    def find_similar_papers(self, paper_id: int, top_k: int = 5) -> List[Dict]:
        """類似論文を検索"""
        paper = Paper.query.get(paper_id)
        if not paper or not paper.embedding:
            return []
        
        # 全論文の埋め込みを取得
        all_papers = Paper.query.filter(Paper.embedding.isnot(None)).all()
        if len(all_papers) < 2:
            return []
        
        # コサイン類似度を計算
        target_embedding = np.array(paper.embedding)
        similarities = []
        
        for p in all_papers:
            if p.id == paper_id:
                continue
            
            embedding = np.array(p.embedding)
            similarity = np.dot(target_embedding, embedding) / (np.linalg.norm(target_embedding) * np.linalg.norm(embedding))
            similarities.append((p, similarity))
        
        # 類似度でソート
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 上位k件を返す
        results = []
        for p, score in similarities[:top_k]:
            results.append({
                'paper': p.to_dict(),
                'similarity_score': float(score)
            })
        
        return results
    
    def _build_context(self, papers: List[Paper]) -> str:
        """論文リストからコンテキスト文字列を構築"""
        context_parts = []
        
        for i, paper in enumerate(papers):
            context_parts.append(f"Paper {i+1}:")
            context_parts.append(f"Title: {paper.title}")
            if paper.authors:
                context_parts.append(f"Authors: {', '.join(paper.authors)}")
            if paper.publication_year:
                context_parts.append(f"Year: {paper.publication_year}")
            if paper.abstract:
                context_parts.append(f"Abstract: {paper.abstract[:500]}...")  # 長さ制限
            context_parts.append("")  # 空行
        
        return "\n".join(context_parts)
    
    def _paper_to_text(self, paper: Paper) -> str:
        """論文オブジェクトをテキストに変換"""
        parts = [f"Title: {paper.title}"]
        
        if paper.abstract:
            parts.append(f"Abstract: {paper.abstract}")
        if paper.authors:
            parts.append(f"Authors: {', '.join(paper.authors)}")
        if paper.publication_year:
            parts.append(f"Year: {paper.publication_year}")
        
        return "\n".join(parts)