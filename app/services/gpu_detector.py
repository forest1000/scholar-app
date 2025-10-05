import torch
import platform
import psutil
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GPUInfo:
    """GPU情報を格納するデータクラス"""
    index: int
    name: str
    total_memory_mb: int
    free_memory_mb: int
    cuda_capability: tuple
    is_available: bool

class GPUDetector:
    """GPU環境を検出し、利用可能なリソースを判定するクラス"""
    
    def __init__(self):
        self.has_cuda = torch.cuda.is_available()
        self.device_count = torch.cuda.device_count() if self.has_cuda else 0
        
    def detect_gpu_environment(self) -> Dict:
        """GPU環境の詳細情報を取得"""
        environment_info = {
            'platform': platform.system(),
            'python_version': platform.python_version(),
            'torch_version': torch.__version__,
            'cuda_available': self.has_cuda,
            'cuda_version': torch.version.cuda if self.has_cuda else None,
            'gpu_count': self.device_count,
            'gpus': [],
            'cpu_info': self._get_cpu_info(),
            'recommendations': []
        }
        
        if self.has_cuda:
            for i in range(self.device_count):
                gpu_info = self._get_gpu_info(i)
                environment_info['gpus'].append(gpu_info.__dict__)
            
            # 推奨事項の追加
            environment_info['recommendations'] = self._generate_recommendations(
                environment_info['gpus']
            )
        else:
            environment_info['recommendations'].append(
                "CUDA対応GPUが検出されませんでした。CPU実行モードで動作します。"
            )
        
        return environment_info
    
    def _get_gpu_info(self, device_index: int) -> GPUInfo:
        """特定のGPUの詳細情報を取得"""
        torch.cuda.set_device(device_index)
        
        # GPU名の取得
        name = torch.cuda.get_device_name(device_index)
        
        # メモリ情報の取得（MB単位）
        total_memory = torch.cuda.get_device_properties(device_index).total_memory
        total_memory_mb = total_memory // (1024 * 1024)
        
        # 空きメモリの取得
        free_memory = total_memory - torch.cuda.memory_allocated(device_index)
        free_memory_mb = free_memory // (1024 * 1024)
        
        # CUDA Compute Capabilityの取得
        capability = torch.cuda.get_device_capability(device_index)
        
        return GPUInfo(
            index=device_index,
            name=name,
            total_memory_mb=total_memory_mb,
            free_memory_mb=free_memory_mb,
            cuda_capability=capability,
            is_available=True
        )
    
    def _get_cpu_info(self) -> Dict:
        """CPU情報を取得"""
        return {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'memory_gb': round(psutil.virtual_memory().total / (1024**3), 2)
        }
    
    def _generate_recommendations(self, gpus: List[Dict]) -> List[str]:
        """GPU環境に基づく推奨事項を生成"""
        recommendations = []
        
        for gpu in gpus:
            vram_gb = gpu['total_memory_mb'] / 1024
            
            if vram_gb >= 24:
                recommendations.append(
                    f"GPU {gpu['index']} ({gpu['name']}): "
                    f"大規模モデル（13B-70Bパラメータ）の実行が可能です。"
                )
            elif vram_gb >= 16:
                recommendations.append(
                    f"GPU {gpu['index']} ({gpu['name']}): "
                    f"中規模モデル（7B-13Bパラメータ）の実行が可能です。"
                )
            elif vram_gb >= 8:
                recommendations.append(
                    f"GPU {gpu['index']} ({gpu['name']}): "
                    f"小規模モデル（3B-7Bパラメータ）または量子化モデルの実行が可能です。"
                )
            else:
                recommendations.append(
                    f"GPU {gpu['index']} ({gpu['name']}): "
                    f"VRAMが限られているため、量子化モデルの使用を推奨します。"
                )
        
        return recommendations
    
    def estimate_model_memory_requirement(self, 
                                        model_params_billion: float,
                                        precision: str = 'fp16',
                                        quantization: Optional[str] = None) -> Dict:
        """モデルのメモリ要件を推定"""
        # 基本的なメモリ計算（パラメータ数 × バイト数）
        bytes_per_param = {
            'fp32': 4,
            'fp16': 2,
            'int8': 1,
            'int4': 0.5
        }
        
        if quantization:
            precision = quantization
        
        base_memory_gb = model_params_billion * bytes_per_param.get(precision, 2)
        
        # オーバーヘッド（勾配、アクティベーション等）を考慮
        # 推論のみの場合は1.2倍、学習の場合は3-4倍必要
        overhead_factor = 1.2
        total_memory_gb = base_memory_gb * overhead_factor
        
        return {
            'model_params_billion': model_params_billion,
            'precision': precision,
            'base_memory_gb': round(base_memory_gb, 2),
            'total_memory_gb': round(total_memory_gb, 2),
            'overhead_factor': overhead_factor
        }
    
    def check_model_compatibility(self, model_params_billion: float,
                                precision: str = 'fp16',
                                device_index: int = 0) -> Dict:
        """特定のモデルがGPUで実行可能かチェック"""
        if not self.has_cuda or device_index >= self.device_count:
            return {
                'compatible': False,
                'reason': 'CUDA対応GPUが利用できません'
            }
        
        gpu_info = self._get_gpu_info(device_index)
        memory_req = self.estimate_model_memory_requirement(
            model_params_billion, precision
        )
        
        # 空きメモリの80%を利用可能とする（安全マージン）
        available_memory_gb = (gpu_info.free_memory_mb * 0.8) / 1024
        required_memory_gb = memory_req['total_memory_gb']
        
        compatible = available_memory_gb >= required_memory_gb
        
        return {
            'compatible': compatible,
            'gpu_name': gpu_info.name,
            'available_memory_gb': round(available_memory_gb, 2),
            'required_memory_gb': required_memory_gb,
            'reason': 'メモリ十分' if compatible else 'メモリ不足',
            'recommendation': self._get_compatibility_recommendation(
                available_memory_gb, required_memory_gb, model_params_billion
            )
        }
    
    def _get_compatibility_recommendation(self, 
                                        available_gb: float, 
                                        required_gb: float,
                                        model_params_billion: float) -> str:
        """互換性に基づく推奨事項を生成"""
        if available_gb >= required_gb:
            return "このモデルは問題なく実行できます。"
        else:
            shortage = required_gb - available_gb
            if shortage <= 2:
                return "メモリがわずかに不足しています。他のアプリケーションを終了してください。"
            elif model_params_billion > 7:
                return "より小さなモデルまたは量子化版の使用を検討してください。"
            else:
                return "int8またはint4量子化版の使用を強く推奨します。"