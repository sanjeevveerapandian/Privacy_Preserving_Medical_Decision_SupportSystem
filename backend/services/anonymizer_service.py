import re

class AnonymizerService:
    def __init__(self):
        # Common PII patterns
        self.patterns = {
            'email': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE),
            'phone': re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\d{3}-\d{4}'),
            'id_card': re.compile(r'\b[A-Z]{1,2}\d{6,10}\b'),
            'dob': re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
            'age': re.compile(r'\b\d{1,2}\s*(?:years?|y/o|yo)\s*old\b', re.IGNORECASE),
        }
        
    def anonymize(self, text: str) -> tuple[str, dict]:
        """
        Anonymizes text by replacing PII with tokens.
        Returns (anonymized_text, mapping_to_restore)
        """
        mapping = {}
        anonymized_text = text
        
        # 1. Mask common patterns
        for pii_type, pattern in self.patterns.items():
            matches = pattern.finditer(anonymized_text)
            for i, match in enumerate(matches):
                val = match.group()
                token = f"[{pii_type.upper()}_{i+1}]"
                mapping[token] = val
                anonymized_text = anonymized_text.replace(val, token)
        
        # 2. Simple Name Heuristic 
        # (This is basic; in a production app we'd use SpaCy or similar NER)
        # For now, we'll look for common name prefixes
        name_prefixes = ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Patient:']
        for prefix in name_prefixes:
            name_pattern = re.compile(rf'{prefix}\s+([A-Z][a-z]+(\s+[A-Z][a-z]+)?)')
            matches = name_pattern.finditer(anonymized_text)
            for i, match in enumerate(matches):
                val = match.group(1)
                token = f"[PATIENT_NAME_{i+1}]"
                mapping[token] = val
                anonymized_text = anonymized_text.replace(val, token)

        return anonymized_text, mapping

    def restore(self, text: str, mapping: dict) -> str:
        """Restores PII from tokens using the provided mapping."""
        restored_text = text
        for token, original_val in mapping.items():
            restored_text = restored_text.replace(token, original_val)
        return restored_text

# Singleton instance
anonymizer = AnonymizerService()
