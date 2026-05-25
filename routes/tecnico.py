# routes/tecnico.py
#
# Endpoints específicos da área do técnico (Fase 2).
# Nunca expõe valores financeiros — só tempo/unidades.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from database import get_db
from auth import obter_usuario_atual
from models.user import Usuario
from models.chamado import Chamado, HistoricoChamado

router = APIRouter()


def _exigir_tecnico_ou_admin(usuario: Usuario):
    tipo = getattr(usuario, "tipo_usuario", None)
    if tipo not in ("tecnico", "admin") and not getattr(usuario, "is_admin", False):
        raise HTTPException(status_code=403, detail="Acesso restrito a técnicos")


@router.get("/resumo")
async def resumo_tecnico(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Estatísticas pessoais do técnico logado:
    - Quantos chamados atribuídos/em atendimento/finalizados ele tem
    - Tempo total trabalhado (em minutos)
    - Tamanho da fila aberta (só se for elegível)
    """
    _exigir_tecnico_ou_admin(usuario)

    # Quando admin acessa, mostra a visão geral dele mesmo como se fosse técnico
    # (mas admin dificilmente vai usar essa tela). Se quiser, pode ignorar pro admin.
    meus = db.query(Chamado).filter(Chamado.tecnico_id == usuario.id)

    total_meus = meus.count()
    atribuidos = meus.filter(Chamado.status == "atribuido").count()
    em_atendimento = meus.filter(Chamado.status == "em_atendimento").count()
    finalizados = meus.filter(Chamado.status == "finalizado").count()

    # Tempo total gasto nos chamados dele (soma do histórico onde ele é o autor)
    minutos_trabalhados = db.query(func.sum(HistoricoChamado.tempo_minutos)).filter(
        HistoricoChamado.usuario_id == usuario.id
    ).scalar() or 0

    # Fila aberta — só se o técnico puder ver
    fila_aberta_count = None
    pode_ver_fila = bool(getattr(usuario, "pode_ver_fila_aberta", False)) or \
        (getattr(usuario, "tipo_usuario", None) == "admin")
    if pode_ver_fila:
        fila_aberta_count = db.query(Chamado).filter(
            Chamado.status == "aberto",
            Chamado.tecnico_id.is_(None),
        ).count()

    return {
        "usuario_id": usuario.id,
        "nome": usuario.nome,
        "total_meus": total_meus,
        "atribuidos": atribuidos,
        "em_atendimento": em_atendimento,
        "finalizados": finalizados,
        "minutos_trabalhados": int(minutos_trabalhados),
        "pode_ver_fila_aberta": pode_ver_fila,
        "fila_aberta_count": fila_aberta_count,
    }
