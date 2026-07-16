"""Local PII Scrubbing Layer.

Runs 100% locally to detect and mask Personally Identifiable Information (PII)
before any data is sent to cloud models. Ensures enterprise data compliance.
"""

import re
import logging
from typing import Dict, Tuple

logger = logging.getLogger("neelvak_kernel")

class PIIScrubber:
    """Detects, masks, and restores PII in text using regex heuristics."""

    def __init__(self):
        # Simplified regex patterns for prototype phase
        self.patterns = {
            "EMAIL": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
            "PHONE": r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
            "CREDIT_CARD": r'\b(?:\d[ -]*?){13,16}\b'
        }

    def scrub(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Scrub PII from text and return the masked text + a restoration map.
        
        Args:
            text: Raw input text.
            
        Returns:
            Tuple of (scrubbed_text, masking_map)
            e.g., ("Contact [EMAIL_0]", {"[EMAIL_0]": "john@example.com"})
        """
        if not text:
            return text, {}

        scrubbed_text = text
        masking_map: Dict[str, str] = {}
        
        # We need to process patterns carefully to avoid overlapping matches
        # For a robust implementation, a library like Presidio is better,
        # but this regex heuristic is sufficient for the prototype.
        
        for pii_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, scrubbed_text)
            
            # Process in reverse so string replacement doesn't shift indices
            for i, match in enumerate(reversed(list(matches))):
                original_val = match.group(0)
                # Skip if it looks like we already masked it (e.g., [EMAIL_0])
                if original_val.startswith("[") and original_val.endswith("]"):
                    continue
                    
                placeholder = f"[{pii_type}_{len(masking_map)}]"
                masking_map[placeholder] = original_val
                
                start, end = match.span()
                scrubbed_text = scrubbed_text[:start] + placeholder + scrubbed_text[end:]

        if masking_map:
            logger.info(f"PIIScrubber: Masked {len(masking_map)} PII entities.")
            
        return scrubbed_text, masking_map

    def restore(self, text: str, masking_map: Dict[str, str]) -> str:
        """Restore original PII data into a scrubbed text.
        
        Args:
            text: Text containing placeholders like [EMAIL_0].
            masking_map: The map returned by scrub().
            
        Returns:
            Text with original PII restored.
        """
        if not text or not masking_map:
            return text

        restored_text = text
        for placeholder, original_val in masking_map.items():
            # Simply replace all occurrences of the placeholder
            restored_text = restored_text.replace(placeholder, original_val)
            
        return restored_text
