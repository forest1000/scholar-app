from flask import Blueprint, request, jsonify, current_app
from app.services.unified_llm_service import UnifiedLLMService
from app.services.gpu_detector import GPUDetector
from app.services.local_model_manager import LocalModelManager
import logging

logger = logging.getLogger(__name__)

# Blueprintの定義
llm_bp = Blueprint('llm', __name__, url_prefix='/api/llm')
"""
llm_routes.py - LLM設定関連のAPIエンドポイントを提供

get_backends: 利用可能なバックエンドの取得
get_gpu_info: GPU環境の情報取得
get_compatible_models: 現在の環境で動作可能なモデルの取得
configure_backend: LLMバックエンドの設定
get_backend_status: 現在のバックエンドの状態取得
download_model: モデルのダウンロード
clear_model_cache: モデルキャッシュのクリア
check_model_compatibility: 特定モデルの互換性チェック
"""

# グローバルなサービスインスタンス
unified_llm_service = UnifiedLLMService()
gpu_detector = GPUDetector()
model_manager = LocalModelManager()

@llm_bp.route('/backends', methods=['GET'])
def get_backends():
    """利用可能なバックエンドの情報を取得"""
    try:
        backends = unified_llm_service.get_available_backends()
        return jsonify({
            'success': True,
            'backends': backends
        })
    except Exception as e:
        logger.error(f"Error getting backends: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/gpu-info', methods=['GET'])
def get_gpu_info():
    """GPU環境の詳細情報を取得"""
    try:
        gpu_info = gpu_detector.detect_gpu_environment()
        return jsonify({
            'success': True,
            'gpu_info': gpu_info
        })
    except Exception as e:
        logger.error(f"Error detecting GPU: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/models/compatible', methods=['GET'])
def get_compatible_models():
    """現在の環境で動作可能なモデルのリストを取得"""
    try:
        # GPU情報を取得
        gpu_env = gpu_detector.detect_gpu_environment()
        
        if gpu_env['cuda_available'] and gpu_env['gpus']:
            # 最大のVRAMを持つGPUを使用
            max_vram_gpu = max(gpu_env['gpus'], key=lambda x: x['total_memory_mb'])
            available_vram_gb = max_vram_gpu['total_memory_mb'] / 1024
            
            compatible_models = model_manager.get_compatible_models(available_vram_gb)
            
            # キャッシュ状態を追加
            for model in compatible_models:
                model['is_cached'] = model_manager.is_model_cached(model['model_id'])
                if not model['is_cached']:
                    model['download_size_gb'] = model_manager.estimate_download_size(
                        model['model_id']
                    )
            
            return jsonify({
                'success': True,
                'gpu_name': max_vram_gpu['name'],
                'available_vram_gb': round(available_vram_gb, 2),
                'models': compatible_models
            })
        else:
            return jsonify({
                'success': True,
                'gpu_name': None,
                'available_vram_gb': 0,
                'models': [],
                'message': 'No CUDA-capable GPU detected. CPU mode only.'
            })
    
    except Exception as e:
        logger.error(f"Error getting compatible models: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/backend/configure', methods=['POST'])
def configure_backend():
    """LLMバックエンドを設定"""
    try:
        data = request.get_json()
        backend_type = data.get('backend_type')
        config = data.get('config', {})
        
        # 現在のアプリケーション設定から必要な情報を取得
        if backend_type == 'openai' and 'api_key' not in config:
            config['api_key'] = current_app.config.get('OPENAI_API_KEY')
        
        unified_llm_service.set_backend(backend_type, **config)
        
        return jsonify({
            'success': True,
            'backend_info': unified_llm_service.get_current_backend_info()
        })
    
    except Exception as e:
        logger.error(f"Error configuring backend: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/backend/status', methods=['GET'])
def get_backend_status():
    """現在のバックエンドの状態を取得"""
    try:
        info = unified_llm_service.get_current_backend_info()
        return jsonify({
            'success': True,
            'backend_info': info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/models/download', methods=['POST'])
def download_model():
    """モデルをダウンロード"""
    try:
        data = request.get_json()
        model_id = data.get('model_id')
        
        if not model_id:
            return jsonify({
                'success': False,
                'error': 'model_id is required'
            }), 400
        
        # バックグラウンドタスクとして実行することも可能
        success = unified_llm_service.download_model(model_id)
        
        return jsonify({
            'success': success,
            'message': f'Model {model_id} download {"completed" if success else "failed"}'
        })
    
    except Exception as e:
        logger.error(f"Error downloading model: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/models/cache', methods=['DELETE'])
def clear_model_cache():
    """モデルキャッシュをクリア"""
    try:
        model_id = request.args.get('model_id')
        unified_llm_service.clear_model_cache(model_id)
        
        return jsonify({
            'success': True,
            'message': f'Cache cleared for {model_id if model_id else "all models"}'
        })
    
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/models/check-compatibility', methods=['POST'])
def check_model_compatibility():
    """特定のモデルの互換性をチェック"""
    try:
        data = request.get_json()
        model_id = data.get('model_id')
        
        # モデル情報を取得
        model_info = model_manager.get_model_info(model_id)
        if not model_info:
            return jsonify({
                'success': False,
                'error': 'Model not found'
            }), 404
        
        # GPU互換性をチェック
        compatibility_info = gpu_detector.check_model_compatibility(
            model_info.params_billion,
            model_info.precision
        )
        
        return jsonify({
            'success': True,
            'model_info': model_info.to_dict(),
            'compatibility': compatibility_info
        })
    
    except Exception as e:
        logger.error(f"Error checking compatibility: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500