"""
Print Manager

Handles print-related functionality for the Noggin web interface:
- PDF generation from inspection records
- Print-friendly HTML generation
- Attachment image preparation for printing
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from io import BytesIO

logger = logging.getLogger(__name__)


class PrintManager:
    """Manages print and PDF generation for inspection records"""
    
    def __init__(self, config=None):
        self.config = config
        self.date_format = '%d %b %Y'
        self.datetime_format = '%d %b %Y %H:%M'
        
        if config:
            self.date_format = config.get('web_display', 'date_format', fallback=self.date_format)
            self.datetime_format = config.get('web_display', 'datetime_format', fallback=self.datetime_format)
    
    def format_date(self, dt: datetime) -> str:
        """Format datetime, hiding time if midnight"""
        if dt is None:
            return ''
        if isinstance(dt, str):
            return dt
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            return dt.strftime(self.date_format)
        return dt.strftime(self.datetime_format)
    
    def format_boolean(self, value: Any) -> str:
        """Format boolean value as Yes/No"""
        if value is None:
            return '-'
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        if isinstance(value, str):
            return 'Yes' if value.lower() in ('true', 'yes', '1') else 'No'
        return 'Yes' if value else 'No'
    
    def generate_print_html(self, inspection: Dict[str, Any], 
                           display_data: Dict[str, Any],
                           attachments: List[Dict[str, Any]],
                           type_label: str,
                           full_type_name: str) -> str:
        """
        Generate standalone HTML suitable for printing.
        This can be used with browser print or converted to PDF.
        """
        inspection_id = inspection.get('noggin_reference') or inspection.get('tip', 'Unknown')
        inspection_date = self.format_date(inspection.get('inspection_date'))
        
        # Build sections HTML
        sections_html = self._build_sections_html(display_data.get('sections', []))
        
        # Build attachments HTML (images only for print)
        images_html = self._build_images_html(attachments, inspection.get('tip'))
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{type_label} - {inspection_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: Arial, sans-serif; 
            font-size: 10pt; 
            line-height: 1.4;
            color: #333;
            padding: 20px;
        }}
        .header {{
            border-bottom: 3px solid #f2c438;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .header .type-badge {{
            background: #2c3e50;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 9pt;
            display: inline-block;
            margin-bottom: 5px;
        }}
        .header h1 {{
            font-size: 16pt;
            color: #2c3e50;
            margin: 5px 0;
        }}
        .header .subtitle {{
            color: #7f8c8d;
            font-size: 10pt;
        }}
        .section {{
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 4px;
            page-break-inside: avoid;
        }}
        .section-header {{
            background: #f8f9fa;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 10pt;
            border-bottom: 1px solid #ddd;
        }}
        .section-body {{
            padding: 10px 12px;
        }}
        .field-row {{
            display: flex;
            padding: 4px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .field-row:last-child {{
            border-bottom: none;
        }}
        .field-label {{
            width: 35%;
            font-weight: 600;
            color: #555;
            font-size: 9pt;
        }}
        .field-value {{
            width: 65%;
            font-size: 9pt;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 8pt;
            font-weight: 600;
        }}
        .badge-yes {{ background: #d4edda; color: #155724; }}
        .badge-no {{ background: #e2e3e5; color: #383d41; }}
        .images-section {{
            page-break-before: always;
        }}
        .images-section h2 {{
            font-size: 12pt;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #ddd;
        }}
        .image-container {{
            page-break-inside: avoid;
            margin-bottom: 20px;
            text-align: center;
        }}
        .image-container img {{
            max-width: 100%;
            max-height: 400px;
            border: 1px solid #ddd;
        }}
        .image-caption {{
            font-size: 9pt;
            color: #666;
            margin-top: 5px;
            font-style: italic;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            font-size: 8pt;
            color: #999;
            text-align: center;
        }}
        @media print {{
            body {{ padding: 0; }}
            .section {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="type-badge">{type_label}</span>
        <h1>{inspection_id}</h1>
        <div class="subtitle">{full_type_name}</div>
    </div>
    
    {sections_html}
    
    {images_html}
    
    <div class="footer">
        Generated on {datetime.now().strftime(self.datetime_format)} | Noggin Data Processor
    </div>
</body>
</html>"""
        
        return html
    
    def _build_sections_html(self, sections: List[Dict[str, Any]]) -> str:
        """Build HTML for all display sections"""
        html_parts = []
        
        for section in sections:
            if not section.get('fields'):
                continue
            
            fields_html = self._build_fields_html(section['fields'])
            
            html_parts.append(f"""
    <div class="section">
        <div class="section-header">{section['title']}</div>
        <div class="section-body">
            {fields_html}
        </div>
    </div>""")
        
        return '\n'.join(html_parts)
    
    def _build_fields_html(self, fields: List[Dict[str, Any]]) -> str:
        """Build HTML for field rows"""
        html_parts = []
        
        for field in fields:
            value = field.get('value', '-')
            
            if field.get('is_bool'):
                if field.get('bool_value') is True or value == 'Yes':
                    value = '<span class="badge badge-yes">Yes</span>'
                elif field.get('bool_value') is False or value == 'No':
                    value = '<span class="badge badge-no">No</span>'
                else:
                    value = '-'
            elif not value:
                value = '-'
            
            html_parts.append(f"""
            <div class="field-row">
                <div class="field-label">{field['label']}</div>
                <div class="field-value">{value}</div>
            </div>""")
        
        return '\n'.join(html_parts)
    
    def _build_images_html(self, attachments: List[Dict[str, Any]], tip: str) -> str:
        """Build HTML for image attachments section"""
        # Filter to image attachments only
        image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
        image_attachments = []
        
        for att in attachments:
            filename = att.get('filename', '')
            ext = filename.lower().split('.')[-1] if filename else ''
            if ext in image_extensions and att.get('attachment_status') == 'complete':
                image_attachments.append(att)
        
        if not image_attachments:
            return ''
        
        images_html = []
        for att in image_attachments:
            file_path = att.get('file_path', '')
            filename = att.get('filename', '')
            
            if file_path and os.path.exists(file_path):
                # For standalone HTML, we'd need to embed images as base64
                # For browser print, we can use the URL
                images_html.append(f"""
        <div class="image-container">
            <img src="/inspection/{tip}/attachment/{att['attachment_tip']}" alt="{filename}">
            <div class="image-caption">{filename}</div>
        </div>""")
        
        if not images_html:
            return ''
        
        return f"""
    <div class="images-section">
        <h2>Attachment Images</h2>
        {''.join(images_html)}
    </div>"""
    
    def generate_pdf(self, inspection: Dict[str, Any],
                    display_data: Dict[str, Any],
                    attachments: List[Dict[str, Any]],
                    type_label: str,
                    full_type_name: str) -> Optional[BytesIO]:
        """
        Generate PDF from inspection data.
        Requires weasyprint or similar library.
        Returns BytesIO object containing PDF data.
        """
        try:
            from weasyprint import HTML
            
            html_content = self.generate_print_html(
                inspection, display_data, attachments, 
                type_label, full_type_name
            )
            
            pdf_buffer = BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            
            return pdf_buffer
            
        except ImportError:
            logger.warning("weasyprint not installed - PDF generation unavailable")
            return None
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return None
    
    def prepare_attachment_images(self, attachments: List[Dict[str, Any]],
                                  max_width: int = 800,
                                  max_height: int = 600) -> List[Dict[str, Any]]:
        """
        Prepare attachment images for printing by resizing if necessary.
        Returns list of attachment dicts with added 'print_ready' flag.
        """
        image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
        prepared = []
        
        for att in attachments:
            att_copy = dict(att)
            filename = att.get('filename', '')
            ext = filename.lower().split('.')[-1] if filename else ''
            
            if ext in image_extensions and att.get('attachment_status') == 'complete':
                att_copy['is_image'] = True
                att_copy['print_ready'] = True
                
                # Check if image exists and is within size limits
                file_path = att.get('file_path')
                if file_path and os.path.exists(file_path):
                    try:
                        from PIL import Image
                        with Image.open(file_path) as img:
                            att_copy['image_width'] = img.width
                            att_copy['image_height'] = img.height
                            att_copy['needs_resize'] = (
                                img.width > max_width or img.height > max_height
                            )
                    except Exception:
                        att_copy['print_ready'] = False
                else:
                    att_copy['print_ready'] = False
            else:
                att_copy['is_image'] = False
                att_copy['print_ready'] = False
            
            prepared.append(att_copy)
        
        return prepared