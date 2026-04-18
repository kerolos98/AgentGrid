import re
def parse_doc(doc: str):
    meta = {}
    meta["description"]=doc.strip()
    return meta