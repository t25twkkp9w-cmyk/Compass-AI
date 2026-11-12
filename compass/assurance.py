"""Bounded defense layers. Pattern checks are mitigations, not complete classifiers."""
import base64
import json
import os
import re
import secrets
import unicodedata

# Restricted values are synthetic fixtures or recognizable credential/SSN shapes.
# Email addresses and tool names are not inherently forbidden.
SENSITIVE = [
    re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),
    re.compile(r'\b\d{3}[- ]\d{2}[- ]\d{4}\b'),
    re.compile(r'\bASSURANCE-SECRET-[A-Za-z0-9_-]+\b',re.I),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*'),
]
INSTRUCTIONS = [
    re.compile(r'(?is)\b(?:system override|developer message)\s*:'),
    re.compile(r'(?is)\bignore\s+(?:all\s+)?(?:previous instructions|company policy|system instructions)'),
    re.compile(r'(?is)\b(?:disclose|print|output|reveal)\b.{0,100}\b(?:private key|api key|ASSURANCE-INJECTION-SUCCESS)\b'),
]

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text) if unicodedata.category(c)!='Cf')

def suspicious_evidence(text):
    candidates=[normalize(text)]
    # Bounded decoding for inspection only; decoded text is never executed.
    for token in re.findall(r'[A-Za-z0-9+/]{24,}={0,2}',candidates[0])[:20]:
        if len(token)>16000:continue
        try:candidates.append(base64.b64decode(token,validate=True).decode('utf-8'))
        except (ValueError,UnicodeError):pass
    return any(pattern.search(candidate) for candidate in candidates for pattern in INSTRUCTIONS)

def filter_evidence(items):
    safe=[];removed=[]
    for item in items:
        if suspicious_evidence(item.get('text','')):removed.append(item['citation_id'])
        else:safe.append(item)
    return safe,removed

def screen_payload(value):
    """Recursively sanitize strings, including evidence, echoes, and dictionary keys."""
    hits=0
    def walk(item):
        nonlocal hits
        if isinstance(item,str):
            cleaned=normalize(item)
            for pattern in SENSITIVE:
                cleaned,n=pattern.subn('[REDACTED]',cleaned);hits+=n
            return cleaned
        if isinstance(item,dict):return {walk(k):walk(v) for k,v in item.items()}
        if isinstance(item,list):return [walk(v) for v in item]
        return item
    return walk(value),hits

def token_actor(token):
    """Controlled demo credentials supplied out of band; no self-selected roles."""
    if not token or len(token)>512:return None
    try:mapping=json.loads(os.getenv('COMPASS_TEST_TOKENS','{}'))
    except (ValueError,TypeError):return None
    if not isinstance(mapping,dict):return None
    for candidate,actor in mapping.items():
        if isinstance(candidate,str) and len(candidate)>=32 and isinstance(actor,str) and secrets.compare_digest(token,candidate):return actor
    return None
