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
