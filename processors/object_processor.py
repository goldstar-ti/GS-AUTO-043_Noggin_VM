"""
Object Processor Module

Main processing orchestrator that coordinates:
- API requests via APIClient
- Field extraction via FieldProcessor
- Report generation via ReportGenerator
- Attachment downloading via AttachmentDownloader
- Database operations via DatabaseRecordManager

This is the generic processor used by all object type scripts.
Each object type script just specifies which config file to use.
"""

from __future__ import annotations
import csv
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .base_processor import (
    GracefulShutdownHandler,
    APIClient,
    AttachmentDownloader,
    FolderManager,
    RetryManager,
    ProgressTracker,
    sanitise_filename
)
from .field_processor import FieldProcessor, DatabaseRecordManager
from .report_generator import create_report_generator

logger: logging.Logger = logging.getLogger(__name__)


class ObjectProcessor:
    """
    Generic object processor for any Noggin inspection type
    
    Usage:
        processor = ObjectProcessor(
            base_config_path='config/base_config.ini',
            specific_config_path='config/coupling_compliance_check_config.ini'
        )
        processor.run()
    """
    
    def __init__(self, base_config_path: str, specific_config_path: str) -> None:
        # Import here to avoid circular imports
        from common import (
            ConfigLoader, LoggerManager, DatabaseConnectionManager,
            HashManager, CircuitBreaker
        )
        
        # Load configuration
        self.config: ConfigLoader = ConfigLoader(base_config_path, specific_config_path)
        
        # Get object type info
        obj_config = self.config.get_object_type_config()
        self.object_type: str = obj_config['object_type']
        self.abbreviation: str = obj_config['abbreviation']
        self.endpoint_template: str = obj_config['endpoint']
        
        # Generate session ID
        self.session_id: str = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.abbreviation}_{str(uuid.uuid4())[:8].upper()}"
        
        # Set up logging
        self.logger_manager: LoggerManager = LoggerManager(
            self.config, 
            script_name=f"processor_{self.abbreviation.lower()}"
        )
        self.logger_manager.configure_application_logger()
        self.session_logger = self.logger_manager.create_session_logger(self.session_id)
        
        # Database connection
        self.db_manager: DatabaseConnectionManager = DatabaseConnectionManager(self.config)
        
        # Hash manager
        self.hash_manager: HashManager = HashManager(self.config, self.db_manager)
        
        # Circuit breaker
        self.circuit_breaker: CircuitBreaker = CircuitBreaker(self.config)
        
        # API client
        self.api_client: APIClient = APIClient(self.config, self.circuit_breaker)
        
        # Field processor
        self.field_processor: FieldProcessor = FieldProcessor(self.config, self.hash_manager)
        
        # Database record manager
        self.record_manager: DatabaseRecordManager = DatabaseRecordManager(
            self.db_manager, self.field_processor
        )
        
        # Report generator
        self.report_generator = create_report_generator(self.config, self.hash_manager)
        
        # Folder manager
        self.folder_manager: FolderManager = FolderManager(self.config, self.abbreviation)
        
        # Attachment downloader
        self.attachment_downloader: AttachmentDownloader = AttachmentDownloader(
            self.config, self.db_manager, self.api_client
        )
        
        # Retry manager
        self.retry_manager: RetryManager = RetryManager(self.config)
        
        # Shutdown handler
        self.shutdown_handler: GracefulShutdownHandler = GracefulShutdownHandler(
            self.db_manager, logger, self._on_shutdown
        )
        
        # Processing settings
        self.attachment_pause: int = self.config.getint('processing', 'attachment_pause')
        self.base_url: str = self.config.get('api', 'base_url')
        
        # Log startup
        self._log_startup()
    
    def _log_startup(self) -> None:
        """Log startup information"""
        logger.info("=" * 80)
        logger.info(f"NOGGIN PROCESSOR - {self.object_type.upper()}")
        logger.info("=" * 80)
        logger.info(f"Session ID:       {self.session_id}")
        logger.info(f"Object Type:      {self.object_type}")
        logger.info(f"Abbreviation:     {self.abbreviation}")
        logger.info(f"Base Output Path: {self.folder_manager.base_path}")
        logger.info("=" * 80)
        
        # Session logger header
        output_patterns = self.config.get_output_patterns()
        header = output_patterns.get('session_log_header', 
            'TIMESTAMP\tTIP\tINSPECTION_ID\tATTACHMENTS_COUNT\tATTACHMENT_FILENAMES')
        
        self.session_logger.info(f"SESSION START: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.session_logger.info(f"SESSION ID: {self.session_id}")
        self.session_logger.info(f"OBJECT TYPE: {self.object_type}")
        self.session_logger.info("")
        self.session_logger.info(header)
    
    def _on_shutdown(self) -> None:
        """Callback when shutdown is triggered"""
        logger.info("Shutdown callback triggered")
    
    def run(self, csv_file_path: Optional[str] = None, 
            batch_size: int = 10,
            from_database: bool = False) -> int:
        """
        Main processing entry point
        
        Args:
            csv_file_path: Path to CSV file with TIPs (if not using database)
            batch_size: Number of TIPs to process per batch
            from_database: If True, get TIPs from database instead of CSV
            
        Returns:
            Number of TIPs processed
        """
        if from_database:
            return self._run_from_database(batch_size)
        elif csv_file_path:
            return self._run_from_csv(csv_file_path)
        else:
            # Default: look for tip.csv in input folder
            input_folder = Path(self.config.get('paths', 'input_folder_path'))
            default_csv = input_folder / f"{self.abbreviation.lower()}_tips.csv"
            
            if not default_csv.exists():
                default_csv = input_folder / "tip.csv"
            
            if default_csv.exists():
                return self._run_from_csv(str(default_csv))
            else:
                logger.warning(f"No CSV file found and from_database=False")
                return 0
    
    def _run_from_csv(self, csv_file_path: str) -> int:
        """Process TIPs from CSV file"""
        csv_path = Path(csv_file_path)
        
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return 0
        
        # Count TIPs
        total_count = self._count_tips_in_csv(csv_path)
        logger.info(f"Found {total_count} TIPs in {csv_path}")
        
        if total_count == 0:
            logger.warning("No TIPs to process")
            return 0
        
        # Progress tracker
        progress = ProgressTracker(total_count)
        
        # Process TIPs
        processed_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Find TIP column (case-insensitive)
            tip_column = None
            for col in reader.fieldnames or []:
                if col.lower() == 'tip':
                    tip_column = col
                    break
            
            if not tip_column:
                logger.error("No 'tip' column found in CSV")
                return 0
            
            for row in reader:
                if not self.shutdown_handler.should_continue():
                    logger.info("Shutdown requested, stopping processing")
                    break
                
                tip_value = row.get(tip_column, '').strip()
                
                if not tip_value:
                    continue
                
                self.shutdown_handler.set_current_tip(tip_value)
                
                success = self._process_single_tip(tip_value)
                
                if success:
                    processed_count += 1
                    progress.increment()
                
                if progress.should_log_progress():
                    progress.log_progress()
        
        self.shutdown_handler.set_current_tip(None)
        
        # Log summary
        reason = "interrupted" if not self.shutdown_handler.should_continue() else "complete"
        progress.log_shutdown_summary(reason)
        
        return processed_count
    
    def _run_from_database(self, batch_size: int = 10) -> int:
        """Process TIPs from database queue"""
        processed_count = 0
        
        while self.shutdown_handler.should_continue():
            # Get batch of TIPs
            tips = self.record_manager.get_tips_to_process(self.abbreviation, batch_size)
            
            if not tips:
                logger.info("No TIPs to process in queue")
                break
            
            for tip_record in tips:
                if not self.shutdown_handler.should_continue():
                    break
                
                tip_value = tip_record['tip']
                self.shutdown_handler.set_current_tip(tip_value)
                
                success = self._process_single_tip(tip_value)
                
                if success:
                    processed_count += 1
        
        self.shutdown_handler.set_current_tip(None)
        
        return processed_count
    
    def _process_single_tip(self, tip_value: str) -> bool:
        """
        Process a single TIP
        
        Returns:
            True if processed successfully (or non-retriable error)
        """
        logger.info(f"Processing TIP: {tip_value}")
        
        # Build API URL
        request_url = self.base_url + self.endpoint_template.replace('$tip', tip_value)
        
        try:
            # Circuit breaker check
            from common import CircuitBreakerError
            
            try:
                self.circuit_breaker.before_request()
            except CircuitBreakerError as e:
                logger.warning(f"Circuit breaker open: {e}")
                return False
            
            # Make API request
            response = self.api_client.make_request(request_url, tip_value)
            
            if response.status_code == 200:
                self.circuit_breaker.record_success()
                return self._handle_successful_response(response, tip_value)
            
            elif response.status_code == 429:
                # Rate limited
                self.circuit_breaker.record_failure()
                sleep_time = self.api_client.too_many_requests_sleep
                logger.warning(f"Rate limited, sleeping {sleep_time}s")
                time.sleep(sleep_time)
                return False
            
            elif response.status_code == 404:
                # Not found - mark as permanent failure
                error_msg = self.api_client.handle_error(response, tip_value, request_url)
                logger.warning(error_msg)
                self.record_manager.update_processing_status(tip_value, 'not_found', error_msg)
                return True  # Don't retry 404s
            
            else:
                # Other error
                self.circuit_breaker.record_failure()
                error_msg = self.api_client.handle_error(response, tip_value, request_url)
                logger.error(error_msg)
                self._handle_api_error(tip_value, error_msg)
                return False
        
        except Exception as e:
            error_msg = f"Exception processing TIP {tip_value}: {e}"
            logger.error(error_msg, exc_info=True)
            self._handle_api_error(tip_value, error_msg)
            return False
    
    def _handle_successful_response(self, response, tip_value: str) -> bool:
        """Handle successful API response"""
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for TIP {tip_value}: {e}")
            self.record_manager.update_processing_status(tip_value, 'api_error', f"Invalid JSON: {e}")
            return False
        
        # Extract inspection ID
        inspection_id = self.field_processor.extract_inspection_id(response_data) or tip_value[:16]
        
        # Insert/update database record
        try:
            self.record_manager.insert_or_update_record(response_data, tip_value)
        except Exception as e:
            logger.error(f"Failed to insert record for TIP {tip_value}: {e}")
            return False
        
        # Process attachments and generate report
        self._process_attachments_and_report(response_data, inspection_id, tip_value)
        
        return True
    
    def _process_attachments_and_report(self, response_data: Dict[str, Any],
                                        inspection_id: str, tip_value: str) -> None:
        """Process attachments and generate report"""
        # Get date for folder creation
        date_str = response_data.get('date', '')
        
        # Create inspection folder
        inspection_folder = self.folder_manager.create_inspection_folder(date_str, inspection_id)
        
        # Generate and save report
        report = self.report_generator.generate_report(response_data, inspection_id)
        self.report_generator.save_report(report, inspection_folder, inspection_id)
        
        # Process attachments
        attachments = response_data.get('attachments', [])
        
        if not attachments:
            logger.info(f"No attachments for {inspection_id}")
            self._log_session_record(tip_value, inspection_id, 0, [])
            self.record_manager.update_attachment_counts(tip_value, 0, 0, True)
            self.record_manager.update_processing_status(tip_value, 'complete')
            return
        
        logger.info(f"Processing {len(attachments)} attachments for {inspection_id}")
        
        # Download attachments
        successful_downloads = 0
        attachment_filenames: List[str] = []
        
        for i, attachment_url in enumerate(attachments, 1):
            if not self.shutdown_handler.should_continue():
                logger.warning(f"Shutdown during attachment {i}/{len(attachments)}")
                break
            
            # Extract attachment TIP
            attachment_tip = attachment_url.split('tip=')[-1] if 'tip=' in attachment_url else f'unknown_{i}'
            
            # Construct filename
            filename = self.folder_manager.construct_attachment_filename(
                inspection_id, date_str, i
            )
            
            # Download
            success, retry_count, file_size_mb, error_msg = self.attachment_downloader.download(
                attachment_url, filename, inspection_id, attachment_tip,
                inspection_folder, tip_value, i
            )
            
            if success:
                successful_downloads += 1
                attachment_filenames.append(filename)
            
            # Pause between attachments
            if self.attachment_pause > 0 and i < len(attachments):
                time.sleep(self.attachment_pause)
        
        # Determine final status
        if not self.shutdown_handler.should_continue():
            final_status = 'interrupted'
        elif successful_downloads == len(attachments):
            final_status = 'complete'
        elif successful_downloads > 0:
            final_status = 'partial'
        else:
            final_status = 'failed'
        
        # Update database
        all_complete = successful_downloads == len(attachments)
        self.record_manager.update_attachment_counts(
            tip_value, len(attachments), successful_downloads, all_complete
        )
        self.record_manager.update_processing_status(tip_value, final_status)
        
        # Log to session
        self._log_session_record(tip_value, inspection_id, successful_downloads, attachment_filenames)
        
        logger.info(f"Completed {inspection_id}: {successful_downloads}/{len(attachments)} attachments")
    
    def _handle_api_error(self, tip_value: str, error_msg: str) -> None:
        """Handle API error with retry logic"""
        # Get current retry count
        result = self.db_manager.execute_query_dict(
            "SELECT retry_count FROM noggin_data WHERE tip = %s",
            (tip_value,)
        )
        
        current_retry = result[0]['retry_count'] if result else 0
        new_retry = current_retry + 1
        
        if self.retry_manager.should_retry(new_retry):
            next_retry = self.retry_manager.calculate_next_retry_time(new_retry)
            self.record_manager.update_retry_info(tip_value, new_retry, next_retry)
            self.record_manager.update_processing_status(tip_value, 'api_error', error_msg)
            logger.info(f"Scheduled retry {new_retry} for TIP {tip_value} at {next_retry}")
        else:
            self.record_manager.mark_permanently_failed(tip_value, f"Max retries exceeded: {error_msg}")
            logger.warning(f"TIP {tip_value} permanently failed after {new_retry} retries")
        
        # Record error
        self.record_manager.record_processing_error(
            tip_value, 'api_error', error_msg,
            {'retry_count': new_retry}
        )
    
    def _log_session_record(self, tip_value: str, inspection_id: str,
                           attachment_count: int, filenames: List[str]) -> None:
        """Log to session log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        filenames_str = ";".join(filenames) if filenames else "NONE"
        
        self.session_logger.info(
            f"{timestamp}\t{tip_value}\t{inspection_id}\t{attachment_count}\t{filenames_str}"
        )
    
    def _count_tips_in_csv(self, csv_path: Path) -> int:
        """Count valid TIPs in CSV file"""
        count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            tip_column = None
            for col in reader.fieldnames or []:
                if col.lower() == 'tip':
                    tip_column = col
                    break
            
            if not tip_column:
                return 0
            
            for row in reader:
                if row.get(tip_column, '').strip():
                    count += 1
        
        return count
    
    def process_single(self, tip_value: str) -> bool:
        """Process a single TIP (for testing or manual processing)"""
        return self._process_single_tip(tip_value)


def create_processor(base_config: str, specific_config: str) -> ObjectProcessor:
    """Factory function to create an ObjectProcessor"""
    return ObjectProcessor(base_config, specific_config)