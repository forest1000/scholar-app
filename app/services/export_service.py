import pandas as pd
import io
from typing import List, Dict
from app.models import Paper
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import json

class ExportService:
    """データエクスポート機能を提供するサービス"""
    
    def export_to_csv(self, papers: List[Paper]) -> bytes:
        """論文リストをCSV形式でエクスポート"""
        data = []
        for paper in papers:
            data.append({
                'Title': paper.title,
                'Authors': '; '.join(paper.authors) if paper.authors else '',
                'Year': paper.publication_year,
                'Citations': paper.citations,
                'Abstract': paper.abstract,
                'URL': paper.url,
                'PDF Link': paper.pdf_link
            })
        
        df = pd.DataFrame(data)
        
        # バイトストリームに書き込み
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')  # BOM付きUTF-8
        output.seek(0)
        
        return output.getvalue()
    
    def export_to_excel(self, papers: List[Paper], statistics: Dict = None) -> bytes:
        """論文リストをExcel形式でエクスポート（統計情報付き）"""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 論文データシート
            paper_data = []
            for paper in papers:
                paper_data.append({
                    'ID': paper.id,
                    'Title': paper.title,
                    'Authors': '; '.join(paper.authors) if paper.authors else '',
                    'Year': paper.publication_year,
                    'Citations': paper.citations,
                    'Abstract': paper.abstract[:500] if paper.abstract else '',  # 長さ制限
                    'URL': paper.url,
                    'PDF Link': paper.pdf_link
                })
            
            df_papers = pd.DataFrame(paper_data)
            df_papers.to_excel(writer, sheet_name='Papers', index=False)
            
            # 統計情報シート（提供されている場合）
            if statistics:
                # 年次分布
                if 'year_distribution' in statistics:
                    df_year = pd.DataFrame({
                        'Year': statistics['year_distribution']['years'],
                        'Count': statistics['year_distribution']['counts']
                    })
                    df_year.to_excel(writer, sheet_name='Year Distribution', index=False)
                
                # 著者統計
                if 'top_authors' in statistics:
                    df_authors = pd.DataFrame(statistics['top_authors'])
                    df_authors.to_excel(writer, sheet_name='Top Authors', index=False)
            
            
            # フォーマット設定
            workbook = writer.book
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BD',
                'border': 1
            })
            
            # 各シートのヘッダーフォーマットを適用
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                worksheet.set_row(0, 20, header_format)
        
        output.seek(0)
        return output.getvalue()
    
    def export_to_bibtex(self, papers: List[Paper]) -> str:
        """論文リストをBibTeX形式でエクスポート"""
        bib_database = bibtexparser.bibdatabase.BibDatabase()
        
        for i, paper in enumerate(papers):
            entry = {
                'ENTRYTYPE': 'article',
                'ID': f'paper{paper.id or i}',
                'title': paper.title,
                'author': ' and '.join(paper.authors) if paper.authors else 'Unknown',
                'year': str(paper.publication_year) if paper.publication_year else '',
                'abstract': paper.abstract or '',
                'url': paper.url or '',
                'citations': str(paper.citations) if paper.citations else '0'
            }
            
            # 空の値を除去
            entry = {k: v for k, v in entry.items() if v}
            bib_database.entries.append(entry)
        
        writer = BibTexWriter()
        writer.indent = '  '
        return writer.write(bib_database)
    
    def generate_analysis_report_pdf(self, papers: List[Paper], analysis_results: Dict) -> bytes:
        """分析レポートをPDF形式で生成"""
        output = io.BytesIO()
        
        # PDF文書の作成
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # スタイルの設定
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1d1d1f'),
            spaceAfter=30,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=12,
        )
        
        # ストーリー（PDF内容）を構築
        story = []
        
        # タイトルページ
        story.append(Paragraph("学術論文分析レポート", title_style))
        story.append(Paragraph(f"生成日: {datetime.now().strftime('%Y年%m月%d日')}", styles['Normal']))
        story.append(Spacer(1, 0.5*inch))
        
        # サマリー
        story.append(Paragraph("1. サマリー", heading_style))
        summary_data = [
            ['項目', '値'],
            ['総論文数', str(len(papers))],
            ['期間', f"{min(p.publication_year for p in papers if p.publication_year)} - {max(p.publication_year for p in papers if p.publication_year)}"],
            ['総引用数', str(sum(p.citations for p in papers if p.citations))],
        ]
        
        t = Table(summary_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
        
        # キーワード分析
        if 'keywords' in analysis_results:
            story.append(Paragraph("2. 頻出キーワード", heading_style))
            keywords_data = [['キーワード', 'スコア']]
            for kw in analysis_results['keywords'][:10]:
                keywords_data.append([kw['word'], f"{kw['score']:.2f}"])
            
            t = Table(keywords_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(t)
            story.append(PageBreak())
        
        # トップ論文
        story.append(Paragraph("3. 引用数トップ10論文", heading_style))
        top_papers = sorted(papers, key=lambda x: x.citations or 0, reverse=True)[:10]
        
        for i, paper in enumerate(top_papers, 1):
            paper_text = f"<b>{i}. {paper.title}</b><br/>"
            paper_text += f"著者: {', '.join(paper.authors[:3]) if paper.authors else '不明'}<br/>"
            paper_text += f"年: {paper.publication_year}, 引用数: {paper.citations}<br/>"
             
            story.append(Paragraph(paper_text, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
        
        # PDFを生成
        doc.build(story)
        output.seek(0)
        
        return output.getvalue()
    
    def export_to_json(self, papers: List[Paper], include_embeddings: bool = False) -> str:
        """論文リストをJSON形式でエクスポート"""
        data = []
        
        for paper in papers:
            paper_dict = paper.to_dict()
            
            # 埋め込みベクトルの除外オプション
            if not include_embeddings and 'embedding' in paper_dict:
                del paper_dict['embedding']
            
            data.append(paper_dict)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def export_search_history(self, sessions: List['SearchSession']) -> bytes:
        """検索履歴をエクスポート"""
        data = []
        
        for session in sessions:
            data.append({
                'Session Name': session.session_name,
                'Query': session.query,
                'Date': session.created_at.strftime('%Y-%m-%d %H:%M:%S') if session.created_at else '',
                'Results Count': session.results_count,
                'Filters': json.dumps(session.filters) if session.filters else ''
            })
        
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return output.getvalue()
    
    def create_citation_network_data(self, papers: List[Paper]) -> Dict:
        """引用ネットワークデータを作成（将来の拡張用）"""
        # ノードデータ
        nodes = []
        for paper in papers:
            nodes.append({
                'id': paper.id,
                'label': paper.title[:50] + '...' if len(paper.title) > 50 else paper.title,
                'year': paper.publication_year,
                'citations': paper.citations,
                'authors': paper.authors
            })
        
        # エッジデータ（この例では仮のデータ）
        # 実際の実装では、論文間の引用関係を解析する必要がある
        edges = []
        
        return {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'total_papers': len(papers),
                'date_generated': datetime.now().isoformat()
            }
        }