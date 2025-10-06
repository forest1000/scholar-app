from celery import Celery
from flask import current_app
from app.models import Paper, db
from app.services.scholar_service import ScholarService
from app.services.llm_service import LLMService
import logging

logger = logging.getLogger(__name__)

def make_celery(app):
    """FlaskアプリケーションからCeleryインスタンスを作成"""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        """Flask アプリケーションコンテキストでタスクを実行"""
        abstract = True
        
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Celeryインスタンスは app/__init__.py で初期化される
celery = Celery(__name__)

@celery.task(bind=True, max_retries=3)
def fetch_papers_batch(self, query, year_from=None, year_to=None, max_results=100):
    """バッチで論文を取得するタスク"""
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': max_results})
        
        scholar_service = ScholarService()
        results = []
        batch_size = 20
        
        for i in range(0, max_results, batch_size):
            current_batch = scholar_service.search_papers(
                query=query,
                year_from=year_from,
                year_to=year_to,
                max_results=min(batch_size, max_results - i)
            )
            results.extend(current_batch)
            
            # 進捗更新
            self.update_state(
                state='PROGRESS',
                meta={'current': len(results), 'total': max_results}
            )
        
        return {
            'status': 'success',
            'results': results,
            'total': len(results)
        }
    
    except Exception as e:
        logger.error(f"Error in fetch_papers_batch: {str(e)}")
        # リトライ
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True)
def process_embeddings_batch(self, paper_ids):
    """論文の埋め込みをバッチで処理"""
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': len(paper_ids)})
        
        llm_service = LLMService()
        processed = 0
        
        for paper_id in paper_ids:
            paper = Paper.query.get(paper_id)
            if paper:
                llm_service.save_embeddings(paper)
                processed += 1
                
                # 進捗更新
                self.update_state(
                    state='PROGRESS',
                    meta={'current': processed, 'total': len(paper_ids)}
                )
        
        return {
            'status': 'success',
            'processed': processed,
            'total': len(paper_ids)
        }
    
    except Exception as e:
        logger.error(f"Error in process_embeddings_batch: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

@celery.task(bind=True)
def generate_research_report(self, paper_ids, report_type='summary'):
    """研究レポートを生成"""
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Loading papers...'})
        
        papers = Paper.query.filter(Paper.id.in_(paper_ids)).all()
        if not papers:
            return {'status': 'error', 'error': 'No papers found'}
        
        llm_service = LLMService()
        
        if report_type == 'summary':
            self.update_state(state='PROGRESS', meta={'status': 'Generating summary...'})
            content = llm_service.generate_summary(papers)
            
        elif report_type == 'trends':
            self.update_state(state='PROGRESS', meta={'status': 'Analyzing trends...'})
            # トレンド分析の実装
            content = _analyze_research_trends(papers)
            
        elif report_type == 'gaps':
            self.update_state(state='PROGRESS', meta={'status': 'Identifying research gaps...'})
            # 研究ギャップ分析の実装
            content = _identify_research_gaps(papers)
        
        else:
            return {'status': 'error', 'error': 'Invalid report type'}
        
        return {
            'status': 'success',
            'report_type': report_type,
            'content': content,
            'paper_count': len(papers)
        }
    
    except Exception as e:
        logger.error(f"Error in generate_research_report: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

@celery.task
def cleanup_old_sessions(days=30):
    """古い検索セッションをクリーンアップ"""
    from datetime import datetime, timedelta
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 保存されていない古いセッションを削除
        deleted = SearchSession.query.filter(
            SearchSession.created_at < cutoff_date,
            SearchSession.is_saved == False
        ).delete()
        
        db.session.commit()
        
        logger.info(f"Cleaned up {deleted} old search sessions")
        return {'deleted': deleted}
    
    except Exception as e:
        logger.error(f"Error in cleanup_old_sessions: {str(e)}")
        db.session.rollback()
        return {'error': str(e)}

@celery.task
def update_citation_counts():
    """論文の引用数を更新"""
    try:
        scholar_service = ScholarService()
        papers = Paper.query.filter(Paper.updated_at < datetime.utcnow() - timedelta(days=7)).all()
        
        updated = 0
        for paper in papers:
            if paper.scholar_id:
                # Google Scholarから最新の引用数を取得
                # 実装は省略（APIレート制限を考慮）
                updated += 1
        
        return {'updated': updated}
    
    except Exception as e:
        logger.error(f"Error in update_citation_counts: {str(e)}")
        return {'error': str(e)}

def _analyze_research_trends(papers):
    """研究トレンドを分析（仮実装）"""
    # 実際の実装では、年次推移、キーワードの変化、
    # 新しい研究方向などを分析
    return "Research trends analysis placeholder"

def _identify_research_gaps(papers):
    """研究ギャップを特定（仮実装）"""
    # 実際の実装では、未解決の問題、
    # 研究されていない領域などを特定
    return "Research gaps analysis placeholder"

# Celery Beat スケジュール設定
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'cleanup-old-sessions': {
        'task': 'app.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=2, minute=0),  # 毎日午前2時
    },
    'update-citation-counts': {
        'task': 'app.tasks.update_citation_counts',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # 毎週日曜日午前3時
    },
}