from flask import render_template, request, jsonify, current_app, send_file, make_response
from app.main import main
from app.database import db
from app.models import Bookmark
from app.services.scholar_service import ScholarService
from app.services.llm_service import FeatureSearchService
import json
from datetime import datetime
import io
from typing import Optional, List 
import logging

logger = logging.getLogger(__name__)

# サービスインスタンス
scholar_service = None
analysis_service = None
feature_search_service = None

def get_services():
    """サービスインスタンスを取得（遅延初期化）"""
    global scholar_service, analysis_service, feature_search_service, export_service
    if not scholar_service:
        scholar_service = ScholarService()
    if not analysis_service:
        analysis_service = AnalysisService()
    if not feature_search_service:
        feature_search_service = FeatureSearchService()
    return scholar_service, analysis_service, feature_search_service

@main.route('/')
def index():
    """トップページ"""
    try:
        return render_template('index.html')
    except Exception:
        current_app.logger.exception("Template render failed")
        raise

@main.route('/search')
def search_page():
    """検索ページ"""
    return render_template('search.html')

@main.route('/llm-config')
def llm_config_page():
    """LLM設定ページ"""
    return render_template('llm_config.html')

@main.route('/api/search', methods=['POST'])
def api_search():
    """論文検索API (F-001, F-002, F-003)"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        search_type = data.get('type', 'keyword')  # keyword, author
        year_from = data.get('year_from')
        year_to = data.get('year_to')
        page = data.get('page', 1)
        per_page = current_app.config.get('ITEMS_PER_PAGE', 20)
        
        scholar, _, _ = get_services()
        
        # 検索実行
        if search_type == 'author':
            results = scholar.search_by_author(query)
        else:
            results = scholar.search_papers(query, year_from, year_to)

        # ページング
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_results = results[start:end]
        
        # 検索結果を論文として保存
        saved_papers = []
        for result in paginated_results:
            paper = _save_or_update_paper(result)
            if paper:
                saved_papers.append(paper)
        
        return jsonify({
            'success': True,
            'results': paginated_results,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page
        })
    
    except Exception as e:
        logger.error(f"Error in api_search: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/llm/feature-search', methods=['POST'])
def api_feature_search():
    """AI特徴量検索API - 完全な実装"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        search_scope = data.get('scope', 'all')  # all, session, bookmarked
        top_k = data.get('top_k', 10)
        save_bookmarks = data.get('save_bookmarks', False)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query is required'
            }), 400
        
        logger.info(f"Starting AI feature search with query: {query}")
        
        # 検索範囲の論文を取得
        papers = _get_papers_by_scope(search_scope, data.get('session_id'))
        
        if not papers:
            return jsonify({
                'success': False,
                'error': 'No papers found in the specified scope'
            }), 404
        
        logger.info(f"Found {len(papers)} papers in scope: {search_scope}")
        
        # FeatureSearchServiceを取得
        _, _, feature_service = get_services()
        
        # AI特徴検索を実行
        search_results = feature_service.perform_ai_feature_search(
            query=query,
            papers=papers,
            top_k=top_k
        )
        
        if search_results['status'] != 'success':
            return jsonify({
                'success': False,
                'error': search_results.get('message', 'Feature search failed')
            }), 500
        
        # ブックマークを保存
        if save_bookmarks and search_results.get('results'):
            paper_ids = [r['paper_id'] for r in search_results['results']]
            bookmark_result = feature_service.save_bookmarked_papers(paper_ids)
            search_results['bookmark_status'] = bookmark_result
        
        return jsonify({
            'success': True,
            'query': query,
            'scope': search_scope,
            'total_papers_searched': search_results['total_papers'],
            'results_count': search_results['selected_papers'],
            'results': search_results['results'],
            'bookmark_status': search_results.get('bookmark_status')
        })
    
    except Exception as e:
        logger.error(f"Error in api_feature_search: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/llm/analyze-papers', methods=['POST'])
def api_analyze_papers():
    """選択した論文の詳細分析API"""
    try:
        data = request.get_json()
        paper_ids = data.get('paper_ids', [])
        
        if not paper_ids:
            return jsonify({
                'success': False,
                'error': 'No paper IDs provided'
            }), 400
        
        papers = Paper.query.filter(Paper.id.in_(paper_ids)).all()
        
        if not papers:
            return jsonify({
                'success': False,
                'error': 'Papers not found'
            }), 404
        
        _, _, feature_service = get_services()
        
        # 各論文の詳細分析を実行
        analyzed_papers = []
        for paper in papers:
            analysis = feature_service._analyze_paper(paper)
            analyzed_papers.append({
                'paper_id': paper.id,
                'title': paper.title,
                'analysis': analysis
            })
        
        return jsonify({
            'success': True,
            'analyzed_count': len(analyzed_papers),
            'results': analyzed_papers
        })
    
    except Exception as e:
        logger.error(f"Error in api_analyze_papers: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/paper/<int:paper_id>')
def api_paper_detail(paper_id):
    """論文詳細API (F-005)"""
    try:
        paper = Paper.query.get_or_404(paper_id)
        return jsonify({
            'success': True,
            'paper': paper.to_dict()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    
@main.route('/api/mining', methods=['POST'])
def api_mining():
    """データマイニングAPI (F-007)"""
    try:
        data = request.get_json()
        paper_ids = data.get('paper_ids', [])
        mining_type = data.get('type', 'keywords')  # keywords, topics, network
        
        if not paper_ids:
            papers = Paper.query.limit(100).all()
        else:
            papers = Paper.query.filter(Paper.id.in_(paper_ids)).all()
        
        _, analysis, _ = get_services()
        
        if mining_type == 'keywords':
            results = analysis.extract_keywords(papers, top_n=data.get('top_n', 20))
            return jsonify({
                'success': True,
                'keywords': [{'word': word, 'score': score} for word, score in results]
            })
        
        elif mining_type == 'topics':
            results = analysis.find_topics(papers, n_topics=data.get('n_topics', 5))
            return jsonify({
                'success': True,
                'topics': results
            })
        
        elif mining_type == 'network':
            results = analysis.get_co_occurrence_network(papers, min_count=data.get('min_count', 3))
            return jsonify({
                'success': True,
                'network': results
            })
        
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid mining type'
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/bookmark', methods=['POST'])
def api_bookmark():
    """ブックマーク追加API (F-009)"""
    try:
        data = request.get_json()
        paper_id = data.get('paper_id')
        note = data.get('note', '')
        tags = data.get('tags', [])
        
        # 既存のブックマークをチェック
        existing = Bookmark.query.filter_by(paper_id=paper_id).first()
        if existing:
            # 更新
            existing.note = note
            existing.tags = tags
        else:
            # 新規作成
            bookmark = Bookmark(
                paper_id=paper_id,
                note=note,
                tags=tags
            )
            db.session.add(bookmark)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bookmark saved successfully'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/bookmarks')
def api_bookmarks():
    """ブックマーク一覧API"""
    try:
        bookmarks = Bookmark.query.all()
        results = []
        
        for bookmark in bookmarks:
            result = {
                'id': bookmark.id,
                'paper': bookmark.paper.to_dict(),
                'note': bookmark.note,
                'tags': bookmark.tags,
                'created_at': bookmark.created_at.isoformat()
            }
            results.append(result)
        
        return jsonify({
            'success': True,
            'bookmarks': results
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/sessions')
def api_sessions():
    """検索セッション一覧API"""
    try:
        sessions = SearchSession.query.order_by(SearchSession.created_at.desc()).all()
        results = []
        
        for session in sessions:
            results.append({
                'id': session.id,
                'name': session.session_name,
                'query': session.query,
                'filters': session.filters,
                'results_count': session.results_count,
                'created_at': session.created_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'sessions': results
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ヘルパー関数

def _get_papers_by_scope(scope: str, session_id: Optional[int] = None) -> List[Bookmark]:
    """指定されたスコープに基づいて論文を取得"""
    papers = []
    
    """
    if scope == 'bookmarked':
        bookmarks = Bookmark.query.all()
        papers = [b.paper for b in bookmarks]
    """
    
    return papers

def _save_or_update_paper(paper_data: dict):
    """論文データを保存または更新"""
    try:
        paper = Paper.query.filter_by(scholar_id=paper_data.get('scholar_id')).first()
        
        if not paper:
            paper = Paper()
        
        # データを設定
        for key, value in paper_data.items():
            if hasattr(paper, key):
                setattr(paper, key, value)
        
        db.session.add(paper)
        db.session.commit()
        
        return paper
    
    except Exception as e:
        logger.error(f"Error saving paper: {str(e)}")
        db.session.rollback()
        return None