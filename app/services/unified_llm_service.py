from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from langchain_core.language_models.llms import LLM
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.llms import HuggingFacePipeline
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from transformers import pipeline
import torch
import logging
from app.services.local_model_manager import LocalModelManager
from app.services.gpu_detector import GPUDetector

logger = logging.getLogger(__name__)

class LLMBackend(ABC):
    """LLMバックエンドの抽象基底クラス"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """テキスト生成"""
        pass
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """テキストの埋め込み表現を生成"""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict:
        """バックエンド情報を取得"""
        pass

class OpenAIBackend(LLMBackend):
    """OpenAI APIを使用するバックエンド"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.llm = OpenAI(
            openai_api_key=api_key,
            model_name=model,
            temperature=0.7,
            max_tokens=1000
        )
        self.embeddings = OpenAIEmbeddings(openai_api_key=api_key)
    
    def generate(self, prompt: str, **kwargs) -> str:
        return self.llm(prompt)
    
    def embed(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)
    
    def get_info(self) -> Dict:
        return {
            'type': 'openai',
            'model': self.model,
            'status': 'ready'
        }

class LocalGPUBackend(LLMBackend):
    """ローカルGPUを使用するバックエンド"""
    
    def __init__(self, model_id: str, device: str = "cuda"):
        self.model_id = model_id
        self.device = device
        self.model_manager = LocalModelManager()
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.embeddings = None
        
    def load_model(self):
        """モデルをロード"""
        if not self.model:
            self.model, self.tokenizer = self.model_manager.load_model(
                self.model_id, 
                self.device
            )
            
            # テキスト生成パイプラインの作成
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            
            # 埋め込みモデルの作成
            self.embeddings = HuggingFaceEmbeddings(
                model_name="intfloat/multilingual-e5-large",
                model_kwargs={'device': self.device}
            )
    
    def generate(self, prompt: str, **kwargs) -> str:
        if not self.pipeline:
            self.load_model()
        
        # 生成パラメータの設定
        generation_kwargs = {
            'max_length': kwargs.get('max_length', 512),
            'temperature': kwargs.get('temperature', 0.7),
            'do_sample': True,
            'top_p': kwargs.get('top_p', 0.9),
            'pad_token_id': self.tokenizer.pad_token_id,
            'eos_token_id': self.tokenizer.eos_token_id,
        }
        
        # テキスト生成
        outputs = self.pipeline(prompt, **generation_kwargs)
        return outputs[0]['generated_text'][len(prompt):]
    
    def embed(self, text: str) -> List[float]:
        if not self.embeddings:
            self.load_model()
        return self.embeddings.embed_query(text)
    
    def get_info(self) -> Dict:
        model_info = self.model_manager.get_model_info(self.model_id)
        return {
            'type': 'local_gpu',
            'model': self.model_id,
            'device': self.device,
            'status': 'loaded' if self.model else 'unloaded',
            'params_billion': model_info.params_billion if model_info else None,
            'precision': model_info.precision if model_info else None
        }

class UnifiedLLMService:
    """統合LLMサービス - 外部APIとローカルGPUを統一的に扱う"""
    
    def __init__(self):
        self.backend: Optional[LLMBackend] = None
        self.backend_type: Optional[str] = None
        self.gpu_detector = GPUDetector()
        self.model_manager = LocalModelManager()
    
    def set_backend(self, backend_type: str, **config):
        """バックエンドを設定"""
        if backend_type == 'openai':
            api_key = config.get('api_key')
            if not api_key:
                raise ValueError("OpenAI API key is required")
            
            self.backend = OpenAIBackend(
                api_key=api_key,
                model=config.get('model', 'gpt-4')
            )
            self.backend_type = 'openai'
            
        elif backend_type == 'local_gpu':
            model_id = config.get('model_id')
            if not model_id:
                raise ValueError("Model ID is required for local GPU backend")
            
            # GPUの利用可能性をチェック
            gpu_env = self.gpu_detector.detect_gpu_environment()
            if not gpu_env['cuda_available']:
                logger.warning("CUDA not available, falling back to CPU mode")
                device = "cpu"
            else:
                device = config.get('device', 'cuda')
            
            self.backend = LocalGPUBackend(model_id=model_id, device=device)
            self.backend_type = 'local_gpu'
            
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")
    
    def get_current_backend_info(self) -> Dict:
        """現在のバックエンド情報を取得"""
        if not self.backend:
            return {'status': 'not_configured'}
        
        info = self.backend.get_info()
        info['backend_type'] = self.backend_type
        return info
    
    def get_available_backends(self) -> Dict:
        """利用可能なバックエンドのリストを取得"""
        backends = {
            'openai': {
                'available': True,
                'models': ['gpt-4', 'gpt-3.5-turbo'],
                'requires_api_key': True
            }
        }
        
        # GPU環境をチェック
        gpu_env = self.gpu_detector.detect_gpu_environment()
        
        if gpu_env['cuda_available'] and gpu_env['gpus']:
            # 最大のVRAMを持つGPUを取得
            max_vram_gpu = max(gpu_env['gpus'], key=lambda x: x['total_memory_mb'])
            available_vram_gb = max_vram_gpu['total_memory_mb'] / 1024
            
            # 互換性のあるモデルを取得
            compatible_models = self.model_manager.get_compatible_models(available_vram_gb)
            
            backends['local_gpu'] = {
                'available': True,
                'gpu_info': max_vram_gpu,
                'compatible_models': compatible_models,
                'cached_models': self.model_manager.get_cached_models()
            }
        else:
            backends['local_gpu'] = {
                'available': False,
                'reason': 'No CUDA-capable GPU detected',
                'cpu_fallback': True
            }
        
        return backends
    
    def generate_text(self, prompt: str, **kwargs) -> str:
        """テキスト生成（バックエンドに依存しない）"""
        if not self.backend:
            raise RuntimeError("Backend not configured. Call set_backend first.")
        
        return self.backend.generate(prompt, **kwargs)
    
    def embed_text(self, text: str) -> List[float]:
        """テキスト埋め込み（バックエンドに依存しない）"""
        if not self.backend:
            raise RuntimeError("Backend not configured. Call set_backend first.")
        
        return self.backend.embed(text)
    
    def semantic_search(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        """意味的類似度検索"""
        if not self.backend:
            raise RuntimeError("Backend not configured. Call set_backend first.")
        
        # クエリの埋め込みを取得
        query_embedding = self.embed_text(query)
        
        # 各文書の埋め込みを取得し、類似度を計算
        results = []
        for doc in documents:
            doc_text = f"{doc.get('title', '')} {doc.get('abstract', '')}"
            doc_embedding = self.embed_text(doc_text)
            
            # コサイン類似度の計算
            similarity = self._cosine_similarity(query_embedding, doc_embedding)
            
            results.append({
                'document': doc,
                'similarity_score': similarity
            })
        
        # スコアでソート
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return results[:top_k]
    
    def answer_question(self, question: str, context: str, **kwargs) -> str:
        """コンテキストに基づいて質問に回答"""
        # プロンプトテンプレート
        if self.backend_type == 'openai':
            prompt = f"""Based on the following context, please answer the question.

Context: {context}

Question: {question}

Answer:"""
        else:
            # ローカルモデル用のプロンプト（日本語）
            prompt = f"""以下の文脈に基づいて、質問に答えてください。

文脈: {context}

質問: {question}

回答:"""
        
        return self.generate_text(prompt, **kwargs)
    
    def summarize(self, text: str, max_length: int = 200) -> str:
        """テキストの要約"""
        if self.backend_type == 'openai':
            prompt = f"""Please summarize the following text in about {max_length} words:

{text}

Summary:"""
        else:
            prompt = f"""以下のテキストを{max_length}字程度で要約してください：

{text}

要約："""
        
        return self.generate_text(prompt, max_new_tokens=max_length)
    
    def download_model(self, model_id: str) -> bool:
        """モデルをダウンロード（ローカルバックエンド用）"""
        return self.model_manager.download_model(model_id)
    
    def clear_model_cache(self, model_id: Optional[str] = None):
        """モデルキャッシュをクリア"""
        self.model_manager.clear_cache(model_id)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """コサイン類似度を計算"""
        import numpy as np
        
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))


# LangChain統合用のカスタムLLMクラス
class UnifiedLangChainLLM(LLM):
    """LangChainと統合するためのカスタムLLMクラス"""
    
    unified_service: UnifiedLLMService
    
    def __init__(self, unified_service: UnifiedLLMService):
        super().__init__()
        self.unified_service = unified_service
    
    @property
    def _llm_type(self) -> str:
        return "unified_llm"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        """LLMを呼び出す"""
        return self.unified_service.generate_text(prompt)
    
    @property
    def _identifying_params(self) -> Dict[str, any]:
        """LLMの識別パラメータ"""
        return self.unified_service.get_current_backend_info()