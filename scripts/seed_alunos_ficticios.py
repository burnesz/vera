"""
Gera dados FICTÍCIOS de uso da plataforma VERA por estudantes, sem nenhuma chamada ao LLM.

O que é gerado (pelos serviços reais da plataforma):
- Contas de estudantes fictícios (e-mail @ficticio.vera, senha padrão de demonstração).
- Simulados de 45 itens montados por `gerar_simulado_enem` (mesma amostragem estratificada da API).
- Tentativas submetidas por `submeter_tentativa_simulado`, que corrige os itens e atualiza
  `desempenho_habilidades` (RN-SIM03) exatamente como no uso real.
- Opcionalmente, um simulado pendente (gerado e ainda não respondido) por estudante.

O que NÃO é gerado (depende do LLM): feedbacks da Tutora VERA, sessões de chat e questões inéditas.
Se não houver questões inéditas validadas no banco, os simulados saem com 45 itens históricos.

Modelo de resposta: TRI de 3 parâmetros (modelo logístico usado pelo INEP), com os parâmetros
a, b e c de cada item histórico (`metadados.tri`):
    P(acerto) = c + (1 - c) / (1 + exp(-1.7 * a * (theta - b)))
Cada estudante tem um perfil: proficiência base (theta), deslocamentos por competência (C1–C7),
ganho de proficiência entre simulados e propensão a deixar itens em branco.

Uso:
    ./.venv/bin/python scripts/seed_alunos_ficticios.py              # cria os 5 perfis padrão
    ./.venv/bin/python scripts/seed_alunos_ficticios.py --recriar    # apaga e recria os fictícios
    ./.venv/bin/python scripts/seed_alunos_ficticios.py --limpar     # apenas apaga os fictícios
"""
import os
import sys
import math
import random
import logging
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.db.models  # noqa: F401 — registra todos os modelos no metadata
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.db.models.user import User
from app.db.models.habilidade import HabilidadeEnem
from app.db.models.simulado import Simulado
from app.db.models.history import DesempenhoHabilidade
from app.db.models.questao_inedita import QuestaoInedita
from app.schemas.simulado import RespostaItemInput
from app.services import simulado_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vera.scripts.seed_alunos_ficticios")
logging.getLogger("vera.services.simulado").setLevel(logging.WARNING)

EMAIL_DOMAIN = "ficticio.vera"
SENHA_PADRAO = "aluno123"
LETRAS = ["A", "B", "C", "D", "E"]
D_LOGISTICO = 1.7

# Parâmetros neutros para itens sem TRI (ex.: questões inéditas)
TRI_PADRAO = (1.0, 1.0, 0.2)


@dataclass
class PerfilAluno:
    nome: str
    slug: str
    descricao: str
    theta_base: float
    # Deslocamento de proficiência por competência (1..7); ausente = 0
    ajuste_competencia: Dict[int, float] = field(default_factory=dict)
    ganho_por_simulado: float = 0.1
    prob_branco: float = 0.02
    num_simulados: int = 4
    deixa_pendente: bool = False


PERFIS_PADRAO: List[PerfilAluno] = [
    PerfilAluno(
        nome="Camila Nogueira", slug="camila.nogueira",
        descricao="Avançada e estável; leve dificuldade em geometria espacial (C2).",
        theta_base=2.3, ajuste_competencia={2: -0.6}, ganho_por_simulado=0.05,
        prob_branco=0.005, num_simulados=5,
    ),
    PerfilAluno(
        nome="Lucas Ferreira", slug="lucas.ferreira",
        descricao="Mediano com evolução consistente entre os simulados.",
        theta_base=1.1, ganho_por_simulado=0.2, prob_branco=0.02, num_simulados=5,
        deixa_pendente=True,
    ),
    PerfilAluno(
        nome="Mariana Costa", slug="mariana.costa",
        descricao="Forte em números (C1) e álgebra (C5); fraca em geometria (C2) e grandezas (C3).",
        theta_base=1.4, ajuste_competencia={1: 0.7, 5: 0.8, 2: -1.2, 3: -0.9},
        ganho_por_simulado=0.1, prob_branco=0.01, num_simulados=4,
    ),
    PerfilAluno(
        nome="Pedro Henrique Silva", slug="pedro.silva",
        descricao="Iniciante; muitos itens em branco no fim da prova.",
        theta_base=0.2, ajuste_competencia={6: 0.4}, ganho_por_simulado=0.15,
        prob_branco=0.08, num_simulados=3, deixa_pendente=True,
    ),
    PerfilAluno(
        nome="Juliana Rocha", slug="juliana.rocha",
        descricao="Boa em estatística e probabilidade (C6, C7); fraca em funções e álgebra (C5).",
        theta_base=1.3, ajuste_competencia={6: 0.9, 7: 0.8, 5: -1.1, 4: -0.5},
        ganho_por_simulado=0.12, prob_branco=0.015, num_simulados=4,
    ),
]


def _normalizar_param(valor: Optional[float]) -> Optional[float]:
    """
    Corrige parâmetros TRI que perderam o separador decimal no CSV de origem
    (ex.: 3423 -> 3.423, 153 -> 0.153). Os originais do INEP têm 3+ casas decimais.
    """
    if valor is None:
        return None
    return valor / 1000.0 if float(valor).is_integer() else float(valor)


def _parametros_tri(questao) -> Tuple[float, float, float]:
    metadados = getattr(questao, "metadados", None) or {}
    tri = metadados.get("tri") if isinstance(metadados, dict) else None
    if not tri:
        return TRI_PADRAO
    a = _normalizar_param(tri.get("param_a"))
    b = _normalizar_param(tri.get("param_b"))
    c = _normalizar_param(tri.get("param_c"))
    if a is None or b is None or c is None or not (0 < a < 10) or not (0 <= c < 1):
        return TRI_PADRAO
    return a, b, c


def _prob_acerto(theta: float, a: float, b: float, c: float) -> float:
    return c + (1.0 - c) / (1.0 + math.exp(-D_LOGISTICO * a * (theta - b)))


def _gerar_respostas(
    rng: random.Random,
    simulado: Simulado,
    perfil: PerfilAluno,
    indice_simulado: int,
    competencia_por_hab: Dict[str, int],
    ruido_habilidade: Dict[str, float],
) -> List[RespostaItemInput]:
    respostas: List[RespostaItemInput] = []
    itens = sorted(simulado.itens, key=lambda it: it.ordem)
    total = len(itens)
    theta_simulado = perfil.theta_base + perfil.ganho_por_simulado * indice_simulado

    for item in itens:
        questao = item.questao_enem if item.origem_questao == "enem" else item.questao_inedita
        hab = questao.habilidade_codigo
        comp = competencia_por_hab.get(hab, 0)
        theta = theta_simulado + perfil.ajuste_competencia.get(comp, 0.0) + ruido_habilidade.get(hab, 0.0)

        # Cansaço: mais itens em branco nos 10 últimos itens da prova
        prob_branco = perfil.prob_branco * (3.0 if item.ordem > total - 10 else 1.0)
        if rng.random() < prob_branco:
            marcada = "X"
        else:
            a, b, c = _parametros_tri(questao)
            gabarito = questao.gabarito.strip().upper()
            if rng.random() < _prob_acerto(theta, a, b, c):
                marcada = gabarito
            else:
                marcada = rng.choice([letra for letra in LETRAS if letra != gabarito])

        respostas.append(
            RespostaItemInput(
                simulado_item_id=item.id,
                questao_id=questao.id,
                alternativa_selecionada=marcada,
                alternativa_marcada=marcada,
            )
        )
    return respostas


def _reescrever_datas(db, simulado: Simulado, tentativa, inicio: datetime, duracao: timedelta) -> None:
    """Distribui as datas no passado para que o histórico pareça uso real ao longo de semanas."""
    simulado.created_at = inicio - timedelta(minutes=2)
    tentativa.started_at = inicio
    tentativa.completed_at = inicio + duracao
    respostas = sorted(tentativa.respostas, key=lambda r: r.answered_at or inicio)
    passo = duracao / max(len(respostas), 1)
    for i, resposta in enumerate(respostas, start=1):
        resposta.answered_at = inicio + passo * i


def limpar_ficticios(db) -> int:
    usuarios = db.query(User).filter(User.email.like(f"%@{EMAIL_DOMAIN}")).all()
    if not usuarios:
        return 0
    ids = [u.id for u in usuarios]
    # Simulados não são apagados em cascata pelo usuário; itens e tentativas sim (pelo simulado).
    for simulado in db.query(Simulado).filter(Simulado.user_id.in_(ids)).all():
        db.delete(simulado)
    db.flush()
    for usuario in usuarios:
        db.delete(usuario)
    db.commit()
    return len(usuarios)


def criar_aluno(db, rng: random.Random, perfil: PerfilAluno, competencia_por_hab: Dict[str, int], agora: datetime) -> User:
    # Intervalo de 5 a 9 dias entre simulados, terminando nos últimos dias
    intervalos = [rng.randint(5, 9) for _ in range(perfil.num_simulados)]
    primeiro = agora - timedelta(days=sum(intervalos)) - timedelta(days=rng.randint(1, 3))

    usuario = User(
        nome=perfil.nome,
        email=f"{perfil.slug}@{EMAIL_DOMAIN}",
        hashed_password=get_password_hash(SENHA_PADRAO),
        role="student",
        is_ativo=True,
    )
    db.add(usuario)
    db.commit()
    usuario.created_at = primeiro - timedelta(days=1)

    # Variação individual por habilidade (fixa para o aluno), para que as lacunas não sejam só por competência
    ruido_habilidade = {hab: rng.gauss(0.0, 0.35) for hab in competencia_por_hab}

    data = primeiro
    for indice in range(perfil.num_simulados):
        data_inicio = data.replace(hour=rng.choice([9, 14, 19]), minute=rng.randint(0, 59), second=0, microsecond=0)
        simulado = simulado_service.gerar_simulado_enem(
            db,
            titulo=f"Simulado ENEM Matemática #{indice + 1}",
            tipo="geral_45",
            user_id=usuario.id,
        )
        respostas = _gerar_respostas(rng, simulado, perfil, indice, competencia_por_hab, ruido_habilidade)
        tentativa = simulado_service.submeter_tentativa_simulado(db, simulado.id, usuario.id, respostas)
        duracao = timedelta(minutes=rng.randint(110, 210))
        _reescrever_datas(db, simulado, tentativa, data_inicio, duracao)
        db.commit()
        logger.info(
            f"  {perfil.nome}: simulado #{indice + 1} em {data_inicio:%d/%m} — "
            f"{tentativa.total_acertos}/{tentativa.total_itens} ({tentativa.score_percentual:.1f}%)"
        )
        data += timedelta(days=intervalos[indice])

    ultima_data = data - timedelta(days=intervalos[-1])
    for desempenho in db.query(DesempenhoHabilidade).filter(DesempenhoHabilidade.user_id == usuario.id):
        desempenho.updated_at = ultima_data

    if perfil.deixa_pendente:
        pendente = simulado_service.gerar_simulado_enem(
            db,
            titulo=f"Simulado ENEM Matemática #{perfil.num_simulados + 1}",
            tipo="geral_45",
            user_id=usuario.id,
        )
        pendente.created_at = agora - timedelta(hours=rng.randint(2, 30))
        logger.info(f"  {perfil.nome}: simulado #{perfil.num_simulados + 1} gerado e deixado pendente")

    db.commit()
    return usuario


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera estudantes e simulados fictícios (sem LLM).")
    parser.add_argument("--alunos", type=int, default=len(PERFIS_PADRAO),
                        help=f"Quantidade de estudantes (1 a {len(PERFIS_PADRAO)}; padrão: todos os perfis)")
    parser.add_argument("--seed", type=int, default=42, help="Semente para reprodutibilidade (padrão 42)")
    parser.add_argument("--recriar", action="store_true", help="Apaga os fictícios existentes antes de gerar")
    parser.add_argument("--limpar", action="store_true", help="Apenas apaga os dados fictícios e sai")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.limpar or args.recriar:
            removidos = limpar_ficticios(db)
            logger.info(f"{removidos} estudante(s) fictício(s) removido(s) com simulados, tentativas e desempenho.")
            if args.limpar:
                return

        existentes = db.query(User).filter(User.email.like(f"%@{EMAIL_DOMAIN}")).count()
        if existentes:
            logger.error(f"Já existem {existentes} estudante(s) @{EMAIL_DOMAIN}. Use --recriar para substituí-los.")
            sys.exit(1)

        competencia_por_hab = {h.codigo: h.competencia for h in db.query(HabilidadeEnem).all()}
        if not competencia_por_hab:
            logger.error("Tabela de habilidades vazia. Rode antes: ./.venv/bin/python scripts/seed_questoes.py")
            sys.exit(1)

        ineditas = db.query(QuestaoInedita).filter(QuestaoInedita.is_validated == True).count()  # noqa: E712
        if not ineditas:
            logger.warning("Nenhuma questão inédita validada no banco: os simulados terão 45 itens históricos.")

        # gerar_simulado_enem usa o módulo random global; semeá-lo torna os cadernos reprodutíveis
        random.seed(args.seed)
        rng = random.Random(args.seed)
        agora = datetime.now(timezone.utc)

        perfis = PERFIS_PADRAO[: max(1, min(args.alunos, len(PERFIS_PADRAO)))]
        for perfil in perfis:
            logger.info(f"Criando {perfil.nome} ({perfil.descricao})")
            criar_aluno(db, rng, perfil, competencia_por_hab, agora)

        logger.info(
            f"Concluído: {len(perfis)} estudante(s) fictício(s). Login: <slug>@{EMAIL_DOMAIN} / senha '{SENHA_PADRAO}'."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
