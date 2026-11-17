"""
Cliente do serviço de questões inéditas (repositório questoes-ineditas-enem, app/api.py).

A geração saiu da plataforma: este cliente só repassa os pedidos do administrador ao serviço. As questões
aprovadas entram no acervo da VERA (tabela questoes_ineditas) pela rota de importação de app/api/v1/admin_ineditas.py.
"""
from typing import Any, Dict, List, Optional, Union

import httpx

from app.core.config import settings


class ServicoQuestoesIndisponivel(Exception):
    """O serviço de questões não respondeu (fora do ar ou fora do tempo limite)."""


class ErroServicoQuestoes(Exception):
    """O serviço respondeu com erro; status e detalhe são repassados ao administrador."""

    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def _chamar(metodo: str, caminho: str, json: Optional[dict] = None) -> Any:
    cabecalhos = {"X-API-Key": settings.QUESTOES_API_KEY} if settings.QUESTOES_API_KEY else {}
    url = settings.QUESTOES_API_URL.rstrip("/") + caminho
    try:
        resposta = httpx.request(metodo, url, json=json, headers=cabecalhos,
                                 timeout=settings.QUESTOES_API_TIMEOUT_SECONDS)
    except httpx.HTTPError as e:
        raise ServicoQuestoesIndisponivel(f"Serviço de questões indisponível em {settings.QUESTOES_API_URL}.") from e
    if resposta.status_code >= 400:
        try:
            detalhe = resposta.json().get("detail", resposta.text)
        except ValueError:
            detalhe = resposta.text
        raise ErroServicoQuestoes(resposta.status_code, detalhe)
    return resposta.json()


def saude() -> Dict[str, Any]:
    return _chamar("GET", "/health")


def habilidades() -> List[Dict[str, str]]:
    return _chamar("GET", "/habilidades")


def criar_lote(habilidades: Union[str, List[str]], quantidade: int, max_tentativas: int) -> Dict[str, Any]:
    return _chamar("POST", "/lotes", {"habilidades": habilidades, "quantidade": quantidade,
                                      "max_tentativas": max_tentativas})


def consultar_lote(lote_id: str) -> Dict[str, Any]:
    return _chamar("GET", f"/lotes/{lote_id}")


def cancelar_lote(lote_id: str) -> Dict[str, Any]:
    return _chamar("POST", f"/lotes/{lote_id}/cancelar")
