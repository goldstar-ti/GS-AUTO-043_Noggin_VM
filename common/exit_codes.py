"""
Standardised exit codes for Noggin processing scripts

This module defines consistent exit codes used across all scripts in the Noggin
data processing pipeline. Exit codes are organised by category to make it easy
to identify the type of failure.

Usage:
    from common.exit_codes import EXIT_SUCCESS, EXIT_API_AUTH, EXIT_DB_WRITE
    
    def main() -> int:
        if auth_failed:
            logger.error("Authentication failed")
            return EXIT_API_AUTH
        
        if db_error:
            logger.error("Database write failed")
            return EXIT_DB_WRITE
            
        logger.info("Processing completed successfully")
        return EXIT_SUCCESS

Exit Code Ranges:
    0: Success
    1-10: Configuration & Setup errors
    11-20: Database operation errors
    21-30: File operation errors
    31-40: Network & API errors
    41-49: Media & hash operation errors
    50-59: Processing errors
    60-69: System errors
    70-79: Web application errors
    99: Unknown/unexpected errors

Examples by Script Type:
    
    SFTP Download:
        - EXIT_SFTP_ERROR: Cannot connect to SFTP server
        - EXIT_FILE_WRITE: Cannot save downloaded file
        - EXIT_DB_WRITE: Cannot log download in database
    
    Noggin Processor:
        - EXIT_API_AUTH: Invalid bearer token
        - EXIT_API_RESPONSE: Unexpected JSON structure
        - EXIT_ATTACHMENT_DOWNLOAD: Cannot download media
        - EXIT_HASH_RESOLUTION: Cannot resolve hash to text
        - EXIT_DB_WRITE: Cannot save inspection data
    
    Hash Lookup Sync:
        - EXIT_FILE_NOT_FOUND: Asset/site CSV not found
        - EXIT_DB_WRITE: Cannot update hash_lookup table
        - EXIT_DB_TRANSACTION: Batch insert failed
    
    Web Application:
        - EXIT_WEB_PORT_IN_USE: Port 5000 already in use
        - EXIT_WEB_SERVER: Flask failed to start
        - EXIT_DB_CONNECTION: Cannot connect to database
"""

from __future__ import annotations

; SUCCESS
EXIT_SUCCESS = 0

; CONFIGURATION & SETUP (1-10)
EXIT_CONFIG_ERROR = 1      ; Configuration file error or validation failure
EXIT_ARGS_ERROR = 2        ; Invalid command line arguments
EXIT_ENV_ERROR = 3         ; Environment setup error (paths, permissions)

; DATABASE OPERATIONS (11-20)
EXIT_DB_CONNECTION = 11    ; Database connection failure
EXIT_DB_READ = 12          ; Database read/SELECT query failure
EXIT_DB_WRITE = 13         ; Database write/INSERT/UPDATE/DELETE failure
EXIT_DB_TRANSACTION = 14   ; Transaction commit/rollback failure
EXIT_DB_SCHEMA = 15        ; Schema/table not found or invalid structure
EXIT_DB_DATA = 16          ; Data validation or integrity constraint violation

; FILE OPERATIONS (21-30)
EXIT_FILE_NOT_FOUND = 21   ; Required file not found
EXIT_FILE_READ = 22        ; File read error
EXIT_FILE_WRITE = 23       ; File write error
EXIT_FILE_PERMISSION = 24  ; File permission error

; NETWORK & API (31-40)
EXIT_NETWORK = 31          ; General network connection error
EXIT_API_AUTH = 32         ; API authentication/authorisation failure (invalid token, namespace)
EXIT_API_NOT_FOUND = 33    ; API endpoint not found (404)
EXIT_API_RATE_LIMIT = 34   ; API rate limit exceeded (429)
EXIT_API_SERVER = 35       ; API server error (500, 502, 503)
EXIT_API_RESPONSE = 36     ; API returned unexpected/invalid response format
EXIT_SFTP_ERROR = 37       ; SFTP connection/operation error
EXIT_TIMEOUT = 38          ; Operation timeout

; MEDIA & HASH OPERATIONS (41-49)
EXIT_ATTACHMENT_DOWNLOAD = 41  ; Attachment download or validation failed
EXIT_HASH_RESOLUTION = 42      ; Hash lookup failed or unresolved hash

; PROCESSING (50-59)
EXIT_PROCESSING_ERROR = 50 ; General processing error
EXIT_DATA_VALIDATION = 51  ; Data validation error
EXIT_NO_DATA = 52          ; No data to process (may not be error depending on context)

; SYSTEM (60-69)
EXIT_INTERRUPTED = 60      ; Interrupted by user (Ctrl+C)

; WEB APPLICATION (70-79)
EXIT_WEB_SERVER = 70       ; Web server failed to start
EXIT_WEB_PORT_IN_USE = 71  ; Port already in use
EXIT_WEB_TEMPLATE = 72     ; Template rendering error
EXIT_WEB_ROUTE = 73        ; Route handler error

; UNKNOWN (99)
EXIT_UNKNOWN = 99          ; Unknown/unexpected error


__all__ = [
    'EXIT_SUCCESS',
    'EXIT_CONFIG_ERROR',
    'EXIT_ARGS_ERROR',
    'EXIT_ENV_ERROR',
    'EXIT_DB_CONNECTION',
    'EXIT_DB_READ',
    'EXIT_DB_WRITE',
    'EXIT_DB_TRANSACTION',
    'EXIT_DB_SCHEMA',
    'EXIT_DB_DATA',
    'EXIT_FILE_NOT_FOUND',
    'EXIT_FILE_READ',
    'EXIT_FILE_WRITE',
    'EXIT_FILE_PERMISSION',
    'EXIT_NETWORK',
    'EXIT_API_AUTH',
    'EXIT_API_NOT_FOUND',
    'EXIT_API_RATE_LIMIT',
    'EXIT_API_SERVER',
    'EXIT_API_RESPONSE',
    'EXIT_SFTP_ERROR',
    'EXIT_TIMEOUT',
    'EXIT_ATTACHMENT_DOWNLOAD',
    'EXIT_HASH_RESOLUTION',
    'EXIT_PROCESSING_ERROR',
    'EXIT_DATA_VALIDATION',
    'EXIT_NO_DATA',
    'EXIT_INTERRUPTED',
    'EXIT_WEB_SERVER',
    'EXIT_WEB_PORT_IN_USE',
    'EXIT_WEB_TEMPLATE',
    'EXIT_WEB_ROUTE',
    'EXIT_UNKNOWN',
]