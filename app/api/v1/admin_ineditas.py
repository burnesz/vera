"""
Rotas de administrador para gerar questões inéditas no serviço externo e trazê-las ao acervo da VERA.

Todas exigem perfil 'admin'. Os pedidos são repassados ao serviço de questões (app/services/questoes_api_client.py);
a importação grava as questões aprovadas em questoes_ineditas com o mesmo id que têm no serviço, o que a torna
idempotente. A partir daí os simulados podem sorteá-las (simulado_service.gerar_simulado_enem).
"""
import uuid
from functools import wraps
from typing import Any, Dict, List, Literal, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.questao_inedita import QuestaoInedita
from app.db.session import get_db
from app.services import questoes_api_client as servico

router = APIRouter(dependencies=[Depends(require_admin)])


class LoteRequest(BaseModel):
    habilidades: Union[Literal["all"], List[str]]
    quantidade: int = Field(1, ge=1, le=10)
    max_tentativas: int = Field(5, ge=1, le=10)


class ImportarRequest(BaseModel):
    lote_id: str
    questao_ids: List[str] = Field(..., min_length=1)


def _repassa_erros(rota):
    """Serviço fora do ar vira 503; erro do serviço mantém o status e o detalhe."""
    @wraps(rota)
    def envoltorio(*args, **kwargs):
        try:
            return rota(*args, **kwargs)
        except servico.ServicoQuestoesIndisponivel as e:
            raise HTTPException(status_code=503, detail=str(e))
        except servico.ErroServicoQuestoes as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
    return envoltorio


def _ids_no_acervo(db: Session, ids: List[str]) -> set:
    uuids = []
    for i in ids:
        try:
            uuids.append(uuid.UUID(i))
        except ValueError:
            continue
    if not uuids:
        return set()
    return {str(i) for (i,) in db.query(QuestaoInedita.id).filter(QuestaoInedita.id.in_(uuids)).all()}


@router.get("/saude")
@_repassa_erros
def saude() -> Dict[str, Any]:
    return servico.saude()


@router.get("/habilidades")
@_repassa_erros
def habilidades() -> List[Dict[str, str]]:
    return servico.habilidades()


@router.post("/lotes", status_code=202)
@_repassa_erros
def criar_lote(req: LoteRequest) -> Dict[str, Any]:
    return servico.criar_lote(req.habilidades, req.quantidade, req.max_tentativas)


@router.get("/lotes/{lote_id}")
@_repassa_erros
def consultar_lote(lote_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    lote = servico.consultar_lote(lote_id)
    aprovadas = [p["questao"]["id"] for p in lote["pedidos"] if p.get("questao")]
    no_acervo = _ids_no_acervo(db, aprovadas)
    for p in lote["pedidos"]:
        if p.get("questao"):
            p["questao"]["no_acervo"] = p["questao"]["id"] in no_acervo
    return lote


@router.post("/lotes/{lote_id}/cancelar")
@_repassa_erros
def cancelar_lote(lote_id: str) -> Dict[str, Any]:
    return servico.cancelar_lote(lote_id)


@router.post("/importar")
@_repassa_erros
def importar(req: ImportarRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Grava no acervo as questões aprovadas do lote; ids já presentes são pulados."""
    lote = servico.consultar_lote(req.lote_id)
    aprovadas = {p["questao"]["id"]: p["questao"] for p in lote["pedidos"]
                 if p.get("status") == "aprovada" and p.get("questao")}
    fora = [i for i in req.questao_ids if i not in aprovadas]
    if fora:
        raise HTTPException(status_code=409, detail=f"Questões não aprovadas neste lote: {', '.join(fora)}.")

    ja_existiam = _ids_no_acervo(db, req.questao_ids)
    importadas = []
    for qid in dict.fromkeys(req.questao_ids):
        if qid in ja_existiam:
            continue
        q = aprovadas[qid]
        if not (q.get("enunciado") and q.get("justificativa") and q.get("gabarito") in list("ABCDE")
                and sorted(q.get("alternativas") or {}) == list("ABCDE")):
            raise HTTPException(status_code=422, detail=f"Questão {qid} incompleta; nada foi importado.")
        if not db.get(HabilidadeEnem, q["habilidade_codigo"]):
            raise HTTPException(status_code=422, detail=f"Habilidade {q['habilidade_codigo']} não cadastrada.")
        db.add(QuestaoInedita(
            id=uuid.UUID(qid), habilidade_codigo=q["habilidade_codigo"], enunciado=q["enunciado"],
            alternativas=q["alternativas"], gabarito=q["gabarito"], justificativa=q["justificativa"],
            thought_scratchpad=q.get("thought_scratchpad"), is_validated=True,
        ))
        importadas.append(qid)
    db.commit()
    return {"importadas": importadas, "ja_existiam": sorted(ja_existiam)}
