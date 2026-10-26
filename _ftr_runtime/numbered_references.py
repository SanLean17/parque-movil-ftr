"""Bounded enumerations: a new explicit family ends the previous list.

Only spans are recognized; the inspector's text is never rewritten.
"""
import re

FAMILIES = (
    (r'amortiguador(?:es)?', r'a', 'a', 8),
    (r'pulmon(?:es)?\s+(?:(?:de|del)\s+)?frenos?', r'p[ \t]*\.?[ \t]*f', 'pf', 6),
    (r'pulmon(?:es)?\s+(?:de\s+)?suspension', r'p[ \t]*\.?[ \t]*s', 'ps', 6),
    (r'neumaticos?', r'r', 'r', 8),
    (r'crucetas?', r'cr', 'cr', 3),
)
GAP = r'(?:[ \t]*[._-][ \t]*|[ \t]+)'
CONDITION = r'(?:suelt[oa]s?|suleto|floj[oa]s?|pinchad[oa]s?|con\s+juego)'

def enumeration(name, short, limit=None):
    number = r'\d+(?:\.\d+)?' if limit is None else '[1-'+str(limit)+']'
    head = '(?:'+name+'(?:'+GAP+'|[ \t]+'+CONDITION+'[ \t]+)|'+short+r'[ \t]*[.,_-]?[ \t]*)'
    repeat = '(?:(?:'+name+')'+GAP+'|'+short+r'[ \t]*[.,_-]?[ \t]*)?'
    return head+number+'(?:[ \t]*(?:,|_|-|y)[ \t]*'+repeat+number+r')*(?!\w|[.,]\d)'

TOKENS = [(re.compile(r'\b'+enumeration(name,short)+r'\b'), family, maximum) for name,short,family,maximum in FAMILIES]
CODE_TOKEN = r'\b(?:'+'|'.join(enumeration(name,short) for name,short,_,_ in FAMILIES)+r')\b'

def pattern(family):
    name,short,_,maximum=next(row for row in FAMILIES if row[2]==family)
    return enumeration(name,short,maximum)

def references(text):
    for token,family,maximum in TOKENS:
        if token.fullmatch(text):
            numbers=re.findall(r'\d+(?:\.\d+)?',text)
            if any(not n.isdigit() or not 1<=int(n)<=maximum for n in numbers):return None
            if family=='ps' and any(int(n)==5 for n in numbers):return None  # PS5 has not been confirmed.
            return list(dict.fromkeys(family+str(int(n)) for n in numbers))
    return None
