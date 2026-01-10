"""
Processors Package

Provides modular, config-driven processing for all Noggin object types.

Main components:
- ObjectProcessor: Main processing orchestrator
- FieldProcessor: Config-driven field extraction
- ReportGenerator: Template-based report generation
- Base utilities: API client, attachment downloader, etc.

Usage:
    from processors import ObjectProcessor
    
    processor = ObjectProcessor(
        base_config_path='config/base_config.ini',
        specific_config_path='config/coupling_compliance_check_config.ini'
    )
    processor.run()
"""

from .object_processor import ObjectProcessor, create_processor
from .field_processor import FieldProcessor, DatabaseRecordManager
from .report_generator import ReportGenerator, DefaultReportGenerator, create_report_generator
from .base_processor import (
    GracefulShutdownHandler,
    APIClient,
    AttachmentDownloader,
    FolderManager,
    RetryManager,
    ProgressTracker,
    sanitise_filename,
    flatten_json,
    calculate_md5_hash,
    validate_attachment_file
)

__all__ = [
    # Main processor
    'ObjectProcessor',
    'create_processor',
    
    # Field processing
    'FieldProcessor',
    'DatabaseRecordManager',
    
    # Report generation
    'ReportGenerator',
    'DefaultReportGenerator',
    'create_report_generator',
    
    # Base utilities
    'GracefulShutdownHandler',
    'APIClient',
    'AttachmentDownloader',
    'FolderManager',
    'RetryManager',
    'ProgressTracker',
    
    # Helper functions
    'sanitise_filename',
    'flatten_json',
    'calculate_md5_hash',
    'validate_attachment_file',
]
