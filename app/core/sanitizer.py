"""
Utilitários de sanitização de strings e metadados para garantir
conformidade estrita com UTF-8 (remoção de surrogates e null bytes).
"""
from typing import Any


def sanitize_utf8_string(val: Any) -> str:
    """
    Remove caracteres surrogates inválidos para UTF-8 (U+D800 a U+DFFF)
    e caracteres nulos (\\x00), prevenindo falhas na serialização do orjson
    e na persistência em bancos de dados.
    """
    if val is None:
        return ""
    if not isinstance(val, str):
        val = str(val)
    # Substitui null bytes e descarta pontos de código surrogates isolados
    clean = val.replace("\x00", " ")
    return clean.encode("utf-8", "ignore").decode("utf-8", "ignore").strip()


def sanitize_metadata(data: Any) -> Any:
    """
    Sanitiza recursivamente dicionários, listas e strings para garantir
    conformidade com UTF-8 estrito antes de enviar ao Pinecone/orjson.
    Preserva tipos primitivos numéricos e booleanos.
    """
    if isinstance(data, str):
        return sanitize_utf8_string(data)
    elif isinstance(data, dict):
        return {sanitize_utf8_string(k): sanitize_metadata(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_metadata(item) for item in data]
    return data
