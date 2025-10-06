import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModelInfo:
    """モデル情報を格納するデータクラス"""
    model_id: str
    name: str
    params_billion: float
    precision: str
    quantization: Optional[str]
    language: str
    task: str
    min_vram_gb: float
    recommended_vram_gb: float
    description: str
    
    def to_dict(self):
        return self.__dict__

class LocalModelManager:
    """ローカルLLMモデルの管理を担当するクラス"""
    
    # 日本語対応モデルのカタログ
    JAPANESE_MODELS = [
        ModelInfo(
            model_id="rinna/japanese-gpt-neox-3.6b",
            name="Rinna GPT-NeoX 3.6B",
            params_billion=3.6,
            precision="fp16",
            quantization=None,
            language="ja",
            task="text-generation",
            min_vram_gb=8,
            recommended_vram_gb=10,
            description="Rinnaによる日本語GPTモデル（3.6B）"
        ),
        ModelInfo(
            model_id="cyberagent/open-calm-7b",
            name="OpenCALM 7B",
            params_billion=7,
            precision="fp16",
            quantization=None,
            language="ja",
            task="text-generation",
            min_vram_gb=14,
            recommended_vram_gb=16,
            description="サイバーエージェントの日本語LLM（7B）"
        ),
        ModelInfo(
            model_id="stabilityai/japanese-stablelm-base-alpha-7b",
            name="Japanese StableLM Alpha 7B",
            params_billion=7,
            precision="fp16",
            quantization=None,
            language="ja",
            task="text-generation",
            min_vram_gb=14,
            recommended_vram_gb=16,
            description="Stability AIの日本語言語モデル（7B）"
        ),
        ModelInfo(
            model_id="elyza/ELYZA-japanese-Llama-2-7b",
            name="ELYZA Llama-2 7B",
            params_billion=7,
            precision="fp16",
            quantization=None,
            language="ja",
            task="text-generation",
            min_vram_gb=14,
            recommended_vram_gb=16,
            description="ELYZAによる日本語Llama 2モデル（7B）"
        ),
        ModelInfo(
            model_id="rinna/japanese-gpt-neox-3.6b-instruction",
            name="Rinna GPT-NeoX 3.6B Instruction",
            params_billion=3.6,
            precision="fp16",
            quantization=None,
            language="ja",
            task="text-generation",
            min_vram_gb=8,
            recommended_vram_gb=10,
            description="指示追従型のRinna GPTモデル（3.6B）"
        ),
        # 量子化モデルの例
        ModelInfo(
            model_id="mmnga/cyberagent-open-calm-7b-gguf",
            name="OpenCALM 7B (GGUF/int4)",
            params_billion=7,
            precision="int4",
            quantization="gguf",
            language="ja",
            task="text-generation",
            min_vram_gb=4,
            recommended_vram_gb=6,
            description="OpenCALMの4bit量子化版"
        )
    ]
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or os.path.expanduser("~/.cache/scholar_app/models"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hf_api = HfApi()
        self.loaded_models = {}  # model_id -> (model, tokenizer)のキャッシュ
    
    def get_compatible_models(self, available_vram_gb: float) -> List[ModelInfo]:
        """利用可能なVRAMに基づいて互換性のあるモデルをフィルタリング"""
        compatible_models = []
        
        for model in self.JAPANESE_MODELS:
            if available_vram_gb >= model.min_vram_gb:
                # 推奨VRAMも満たしているかチェック
                model_dict = model.to_dict()
                model_dict['compatibility_status'] = 'optimal' if available_vram_gb >= model.recommended_vram_gb else 'minimal'
                compatible_models.append(model_dict)
        
        # 推奨VRAMでソート（降順）
        compatible_models.sort(
            key=lambda x: (
                x['compatibility_status'] == 'optimal',
                x['params_billion']
            ), 
            reverse=True
        )
        
        return compatible_models
    
    def is_model_cached(self, model_id: str) -> bool:
        """モデルがローカルにキャッシュされているかチェック"""
        model_path = self.cache_dir / model_id.replace("/", "_")
        return model_path.exists() and any(model_path.iterdir())
    
    def get_cached_models(self) -> List[Dict]:
        """キャッシュされているモデルのリストを取得"""
        cached_models = []
        
        for model_info in self.JAPANESE_MODELS:
            if self.is_model_cached(model_info.model_id):
                model_dict = model_info.to_dict()
                model_path = self.cache_dir / model_info.model_id.replace("/", "_")
                
                # キャッシュサイズを計算
                total_size = sum(
                    f.stat().st_size for f in model_path.rglob("*") if f.is_file()
                )
                model_dict['cache_size_gb'] = round(total_size / (1024**3), 2)
                
                cached_models.append(model_dict)
        
        return cached_models
    
    def download_model(self, model_id: str, progress_callback=None) -> bool:
        """Hugging Faceからモデルをダウンロード"""
        try:
            model_path = self.cache_dir / model_id.replace("/", "_")
            
            logger.info(f"Downloading model {model_id} to {model_path}")
            
            # スナップショットダウンロード（全ファイル）
            snapshot_download(
                repo_id=model_id,
                cache_dir=str(self.cache_dir),
                local_dir=str(model_path),
                local_dir_use_symlinks=False,
                resume_download=True
            )
            
            logger.info(f"Model {model_id} downloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading model {model_id}: {str(e)}")
            return False
    
    def load_model(self, model_id: str, device: str = "cuda") -> tuple:
        """モデルとトークナイザーをロード"""
        # 既にロード済みの場合はキャッシュから返す
        if model_id in self.loaded_models:
            return self.loaded_models[model_id]
        
        try:
            model_path = self.cache_dir / model_id.replace("/", "_")
            
            if not model_path.exists():
                raise ValueError(f"Model {model_id} not found in cache. Please download first.")
            
            # デバイスの設定
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                device = "cpu"
            
            # トークナイザーのロード
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                trust_remote_code=True
            )
            
            # モデルのロード（メモリ効率を考慮）
            model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True
            )
            
            if device == "cpu":
                model = model.to(device)
            
            # キャッシュに保存
            self.loaded_models[model_id] = (model, tokenizer)
            
            logger.info(f"Model {model_id} loaded successfully on {device}")
            return model, tokenizer
            
        except Exception as e:
            logger.error(f"Error loading model {model_id}: {str(e)}")
            raise
    
    def unload_model(self, model_id: str):
        """メモリからモデルをアンロード"""
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]
            
            # ガベージコレクションとCUDAメモリのクリア
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(f"Model {model_id} unloaded from memory")
    
    def clear_cache(self, model_id: Optional[str] = None):
        """モデルキャッシュをクリア"""
        if model_id:
            # 特定のモデルのみクリア
            model_path = self.cache_dir / model_id.replace("/", "_")
            if model_path.exists():
                import shutil
                shutil.rmtree(model_path)
                logger.info(f"Cleared cache for model {model_id}")
        else:
            # 全キャッシュをクリア
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cleared all model cache")
    
    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """モデルIDから詳細情報を取得"""
        for model in self.JAPANESE_MODELS:
            if model.model_id == model_id:
                return model
        return None
    
    def estimate_download_size(self, model_id: str) -> float:
        """モデルのダウンロードサイズを推定（GB）"""
        model_info = self.get_model_info(model_id)
        if not model_info:
            return 0.0
        
        # 簡易的な推定（パラメータ数 × 精度によるバイト数 × 1.2）
        bytes_per_param = {
            'fp32': 4,
            'fp16': 2,
            'int8': 1,
            'int4': 0.5
        }
        
        base_size_gb = model_info.params_billion * bytes_per_param.get(
            model_info.precision, 2
        )
        
        # トークナイザーや設定ファイルのオーバーヘッド
        return round(base_size_gb * 1.2, 2)