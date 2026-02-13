import os
import zipfile
import logging
import io
from email.message import EmailMessage
from datetime import datetime
from typing import List, Dict

class EmailManager:
    def __init__(self, temp_dir='/tmp/noggin_exports'):
        self.logger = logging.getLogger(__name__)
        self.temp_dir = temp_dir
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

    def generate_inspection_eml(self, inspection_data: Dict, attachments: List[Dict]) -> io.BytesIO:
        """
        Generates an EML file with a ZIP attachment containing the inspection files.
        """
        try:
            msg = EmailMessage()
            
            # Extract metadata
            insp_id = inspection_data.get('id', 'Unknown')
            insp_type = inspection_data.get('type_label', 'Inspection')
            
            # Headers
            msg['Subject'] = f"{insp_type} Export - {insp_id}"
            msg['From'] = "noreply@noggin-system.local"
            msg['To'] = "user@noggin-system.local" # Placeholder
            msg['Date'] = datetime.now()

            # Body
            body_content = f"""
            {insp_type} Export
            ----------------------------------------
            ID: {insp_id}
            Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            The original attachments for this record are included in the attached ZIP file.
            """
            msg.set_content(body_content)

            # Create ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for att in attachments:
                    file_path = att.get('file_path')
                    filename = att.get('filename')
                    
                    if file_path and os.path.exists(file_path):
                        try:
                            # Add file to zip
                            zip_file.write(file_path, arcname=filename)
                        except Exception as zip_err:
                            self.logger.warning(f"Could not zip file {file_path}: {zip_err}")
                    else:
                        self.logger.warning(f"Attachment file missing: {file_path}")
            
            zip_buffer.seek(0)

            # Attach ZIP to Email
            msg.add_attachment(
                zip_buffer.read(),
                maintype='application',
                subtype='zip',
                filename=f"{insp_id}_attachments.zip"
            )

            # Return EML bytes
            eml_buffer = io.BytesIO(msg.as_bytes())
            eml_buffer.seek(0)
            return eml_buffer

        except Exception as e:
            self.logger.error(f"Error generating EML: {e}")
            raise