from flask import render_template, request, jsonify, current_app, send_file, make_response
from app.main import main
from app.models import Paper, SearchSession, Bookmark, db
from app.services.scholar_service import ScholarService
from app.services.analysis_service import AnalysisService
from app.services.unified_llm_service import UnifiedLLMService
from app.services.export_service import ExportService
import json
from datetime import datetime
import io

# サービスインスタンス
scholar_service = None
analysis_service = None
unified_llm_service = None
export_service = None

def get_services():
    """サービスインスタンスを取得（遅延初期化）"""
    global scholar_service, analysis_service, unified_llm_service, export_service
    if not scholar_service:
        scholar_service = ScholarService()
    if not analysis_service:
        analysis_service = AnalysisService()
    if not unified_llm_service:
        unified_llm_service = UnifiedLLMService()
    if not export_service:
        export_service = ExportService()
    return scholar_service, analysis_service, unified_llm_service, export_service

@main.route('/')
def index():
    """トップページ"""
    return render_template('index.html')

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
        search_type = data.get('type', 'keyword')  # keyword, author, title
        year_from = data.get('year_from')
        year_to = data.get('year_to')
        journal = data.get('journal')
        page = data.get('page', 1)
        per_page = current_app.config.get('ITEMS_PER_PAGE', 20)
        
        scholar, _, _ = get_services()
        
        # 検索実行
        if search_type == 'author':
            results = scholar.search_by_author(query)
        else:
            results = scholar.search_papers(query, year_from, year_to)
        
        # ジャーナルでフィルタリング
        if journal:
            results = [r for r in results if journal.lower() in r.get('journal', '').lower()]
        
        # ページング
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_results = results[start:end]
        
        # セッション保存（オプション）
        if data.get('save_session'):
            session = SearchSession(
                session_name=data.get('session_name', f"Search {datetime.now()}"),
                query=query,
                filters={'year_from': year_from, 'year_to': year_to, 'journal': journal},
                results_count=total
            )
            db.session.add(session)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'results': paginated_results,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/export/<export_type>', methods=['POST'])
def api_export(export_type):
    """データエクスポートAPI"""
    try:
        data = request.get_json()
        paper_ids = data.get('paper_ids', [])
        
        if not paper_ids:
            papers = Paper.query.limit(1000).all()
        else:
            papers = Paper.query.filter(Paper.id.in_(paper_ids)).all()
        
        _, _, _, export_service = get_services()
        
        if export_type == 'csv':
            output = export_service.export_to_csv(papers)
            response = make_response(output)
            response.headers['Content-Disposition'] = 'attachment; filename=papers.csv'
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            return response
        
        elif export_type == 'excel':
            # 統計情報も含める
            _, analysis, _, _ = get_services()
            stats = analysis.get_statistics(papers)
            
            output = export_service.export_to_excel(papers, stats)
            response = make_response(output)
            response.headers['Content-Disposition'] = 'attachment; filename=papers_analysis.xlsx'
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            return response
        
        elif export_type == 'bibtex':
            output = export_service.export_to_bibtex(papers)
            response = make_response(output)
            response.headers['Content-Disposition'] = 'attachment; filename=papers.bib'
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            return response
        
        elif export_type == 'json':
            output = export_service.export_to_json(papers)
            response = make_response(output)
            response.headers['Content-Disposition'] = 'attachment; filename=papers.json'
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        
        elif export_type == 'pdf':
            # 分析結果を取得
            _, analysis, _, _ = get_services()
            keywords = analysis.extract_keywords(papers, top_n=20)
            analysis_results = {
                'keywords': [{'word': w, 'score': s} for w, s in keywords]
            }
            
            output = export_service.generate_analysis_report_pdf(papers, analysis_results)
            response = make_response(output)
            response.headers['Content-Disposition'] = 'attachment; filename=analysis_report.pdf'
            response.headers['Content-Type'] = 'application/pdf'
            return response
        
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid export type'
            }), 400
    
    except Exception as e:
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

@main.route('/api/statistics', methods=['POST'])
def api_statistics():
    """統計情報API (F-006)"""
    try:
        data = request.get_json()
        paper_ids = data.get('paper_ids', [])
        
        if not paper_ids:
            papers = Paper.query.all()
        else:
            papers = Paper.query.filter(Paper.id.in_(paper_ids)).all()
        
        _, analysis, _ = get_services()
        stats = analysis.get_statistics(papers)
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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

@main.route('/api/llm/search', methods=['POST'])
def api_llm_search():
    """LLM特徴量検索API (F-008)"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        search_scope = data.get('scope', 'all')  # all, session, bookmarked
        
        # 検索範囲の論文を取得
        if search_scope == 'bookmarked':
            bookmarks = Bookmark.query.all()
            papers = [b.paper for b in bookmarks]
        elif search_scope == 'session' and data.get('session_id'):
            session = SearchSession.query.get(data['session_id'])
            papers = session.papers if session else []
        else:
            papers = Paper.query.limit(500).all()  # 処理時間を考慮
        
        _, _, llm, _ = get_services()
        
        # ベクトルインデックスを構築（LLMサービスの場合）
        if hasattr(llm, 'build_vector_index'):
            llm.build_vector_index(papers)
            
            # 検索実行
            if data.get('feature_extraction'):
                # 特徴抽出モード
                results = llm.extract_features(query, papers)
            else:
                # セマンティック検索モード
                results = llm.semantic_search(query, top_k=data.get('top_k', 10))
        else:
            # 統合LLMサービスを使用
            paper_dicts = [p.to_dict() for p in papers]
            results = llm.semantic_search(query, paper_dicts, top_k=data.get('top_k', 10))
            
            # 結果の形式を統一
            results = [{'paper': r['document'], 'relevance_score': r['similarity_score']} for r in results]
        
        return jsonify({
            'success': True,
            'results': results
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/llm/answer', methods=['POST'])
def api_llm_answer():
    """LLMによる質問応答API"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        paper_ids = data.get('paper_ids', [])
        
        papers = Paper.query.filter(Paper.id.in_(paper_ids)).all() if paper_ids else []
        
        _, _, llm, _ = get_services()
        
        if hasattr(llm, 'answer_question') and papers:
            # LLMサービスのメソッドを使用
            result = llm.answer_question(question, papers)
        else:
            # 統合LLMサービスを使用
            context = ""
            for paper in papers[:5]:
                context += f"Title: {paper.title}\n"
                if paper.abstract:
                    context += f"Abstract: {paper.abstract}\n"
                context += "\n"
            
            answer = llm.answer_question(question, context)
            result = {
                'answer': answer,
                'sources': [p.to_dict() for p in papers[:5]]
            }
        
        return jsonify({
            'success': True,
            'answer': result['answer'],
            'sources': result['sources']
        })
    
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