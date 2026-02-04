"""
Attachment Extractor Module

Extracts attachment URLs from Noggin API responses, handling various patterns:
- Simple 'attachments' array (LCD)
- Multiple named arrays (LCS: attachments + signature)
- Inline photo fields (CCC: ...PT1, ...PT2, ...PT3)
- Numbered observation arrays (SO: attachments1, attachments2, attachments3)

Supports config-driven stub overrides with auto-generation fallback.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class AttachmentInfo:
    """Represents a single attachment to be downloaded"""
    url: str
    field_name: str
    stub: str
    sequence_in_field: int
    attachment_tip: str

    def __repr__(self) -> str:
        return f"AttachmentInfo(stub={self.stub}, seq={self.sequence_in_field}, field={self.field_name})"


class AttachmentExtractor:
    """
    Extracts attachments from API response data with configurable stub mappings.
    
    Auto-detects fields containing /media/file URLs and generates filename stubs
    from field names, with optional config overrides.
    """
    
    MEDIA_URL_PATTERN = '/media/file'
    
    # Patterns to strip when generating stubs (order matters - process longer patterns first)
    STRIP_PATTERNS = [
        (r'PT(\d)$', r'-t\1'),             # PT1, PT2, PT3 -> -t1, -t2, -t3
        (r'PT$', '-t2'),                   # PT without number is typically trailer 2
        (r'YT(\d)$', ''),                  # YT1, YT2, YT3 -> remove (boolean field suffix)
        (r'^attachments(\d+)$', r'obs\1'), # attachments1 -> obs1 (for SO)
        (r'^attachments$', 'attachments'), # Keep simple attachments as-is
    ]
    
    # Common prefixes to strip for readability (only generic prefixes)
    STRIP_PREFIXES = [
        'contactBetweenThe',
        'isThe', 'hasThe', 'haveThe', 'areThe',
        'is', 'has', 'have', 'are',
    ]
    
    # Words to remove from middle of stub for brevity
    REMOVE_WORDS = [
        'fully', 'engaged', 'and', 'the', 'been', 'into', 'place',
    ]
    
    MAX_STUB_LENGTH = 30

    def __init__(self, config: 'ConfigLoader') -> None:
        self.config = config
        self.stub_overrides = self._load_stub_overrides()
        
    def _load_stub_overrides(self) -> Dict[str, str]:
        """Load attachment stub mappings from [attachments] config section"""
        overrides = {}
        
        if self.config.specific_config.has_section('attachments'):
            for field_name, stub in self.config.specific_config.items('attachments'):
                overrides[field_name] = stub
                logger.debug(f"Loaded attachment stub override: {field_name} -> {stub}")
        
        return overrides
    
    def extract_attachments(self, response_data: Dict[str, Any]) -> List[AttachmentInfo]:
        """
        Extract all attachments from API response.
        
        Args:
            response_data: The full API response payload
            
        Returns:
            List of AttachmentInfo objects ready for downloading
        """
        attachments: List[AttachmentInfo] = []
        
        for field_name, value in response_data.items():
            # Skip metadata fields
            if field_name.startswith('$'):
                continue
            
            urls = self._extract_urls_from_value(value)
            if not urls:
                continue
            
            stub = self._get_stub_for_field(field_name)
            
            for seq, url in enumerate(urls, 1):
                attachment_tip = self._extract_tip_from_url(url)
                attachments.append(AttachmentInfo(
                    url=url,
                    field_name=field_name,
                    stub=stub,
                    sequence_in_field=seq,
                    attachment_tip=attachment_tip
                ))
        
        if attachments:
            logger.debug(f"Extracted {len(attachments)} attachments from {len(set(a.field_name for a in attachments))} fields")
        
        return attachments
    
    def _extract_urls_from_value(self, value: Any) -> List[str]:
        """Extract media URLs from a field value (handles list or string)"""
        urls = []
        
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and self.MEDIA_URL_PATTERN in item:
                    urls.append(item)
        elif isinstance(value, str) and self.MEDIA_URL_PATTERN in value:
            urls.append(value)
        
        return urls
    
    def _extract_tip_from_url(self, url: str) -> str:
        """Extract the TIP hash from a media URL"""
        if 'tip=' in url:
            return url.split('tip=')[-1]
        return f'unknown_{hash(url) % 10000}'
    
    def _get_stub_for_field(self, field_name: str) -> str:
        """
        Get filename stub for a field, using config override or auto-generation.
        
        Priority:
        1. Explicit config override from [attachments] section
        2. Auto-generated from field name
        """
        if field_name in self.stub_overrides:
            return self.stub_overrides[field_name]
        
        return self._generate_stub(field_name)
    
    def _generate_stub(self, field_name: str) -> str:
        """
        Auto-generate a filename stub from a camelCase field name.
        
        Examples:
            contactBetweenTheSkidPlateTurntablePT1 -> skid-plate-turntable-t1
            attachments1 -> obs1
            signature -> signature
            isTheKingPinFullyEngagedPT1 -> king-pin-t1
        """
        stub = field_name
        
        # Apply pattern replacements first (handles suffixes like PT1, attachments1)
        for pattern, replacement in self.STRIP_PATTERNS:
            stub = re.sub(pattern, replacement, stub)
        
        # Strip common prefixes
        for prefix in self.STRIP_PREFIXES:
            if stub.startswith(prefix) and len(stub) > len(prefix):
                stub = stub[len(prefix):]
                stub = stub[0].lower() + stub[1:] if stub else stub
                break
        
        # Convert camelCase to kebab-case
        stub = self._camel_to_kebab(stub)
        
        # Remove filler words
        parts = stub.split('-')
        parts = [p for p in parts if p.lower() not in self.REMOVE_WORDS]
        stub = '-'.join(parts)
        
        # Clean up any double dashes or leading/trailing dashes
        stub = re.sub(r'-+', '-', stub)
        stub = stub.strip('-')
        
        # Enforce max length (preserve trailer suffix if present)
        if len(stub) > self.MAX_STUB_LENGTH:
            # Check for trailer suffix to preserve
            trailer_suffix = ''
            trailer_match = re.search(r'-t\d$', stub)
            if trailer_match:
                trailer_suffix = trailer_match.group()
                stub = stub[:trailer_match.start()]
            
            # Truncate at word boundary
            max_len = self.MAX_STUB_LENGTH - len(trailer_suffix)
            if len(stub) > max_len:
                truncated = stub[:max_len]
                last_dash = truncated.rfind('-')
                if last_dash > max_len // 2:
                    stub = truncated[:last_dash]
                else:
                    stub = truncated.rstrip('-')
            
            stub = stub + trailer_suffix
        
        return stub or 'attachment'
    
    def _camel_to_kebab(self, text: str) -> str:
        """Convert camelCase to kebab-case"""
        # Insert dash before uppercase letters, then lowercase everything
        result = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', text)
        # Handle sequences of uppercase (e.g., "XMLParser" -> "xml-parser")
        result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1-\2', result)
        return result.lower()
    
    def get_attachment_count(self, response_data: Dict[str, Any]) -> int:
        """Quick count of attachments without full extraction"""
        count = 0
        for field_name, value in response_data.items():
            if field_name.startswith('$'):
                continue
            count += len(self._extract_urls_from_value(value))
        return count


def create_attachment_extractor(config: 'ConfigLoader') -> AttachmentExtractor:
    """Factory function to create an AttachmentExtractor"""
    return AttachmentExtractor(config)