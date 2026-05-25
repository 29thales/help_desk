# routes/comissao.py
#
# Endpoints da Fase 4 - Comissão mensal dos técnicos.
# TUDO restrito a admin.

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from auth import obter_usuario_atual
from models.user import Usuario
from services import comissao_service

router = APIRouter()


# =========== HELPERS ===========

def _exigir_admin(u: Usuario):
    if not (getattr(u, "tipo_usuario", None) == "admin" or getattr(u, "is_admin", False)):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")


def _validar_periodo(ano: int, mes: int):
    if mes < 1 or mes > 12:
        raise HTTPException(status_code=400, detail="Mês inválido (1-12)")
    if ano < 2020 or ano > 2100:
        raise HTTPException(status_code=400, detail="Ano inválido")


# =========== SCHEMAS ===========

class FecharMesInput(BaseModel):
    ano: int
    mes: int
    # {tecnico_id: percentual} — keys podem vir como str (JSON) ou int
    percentuais: dict = {}
    observacoes: dict = {}  # {tecnico_id: "texto"}


# =========== ENDPOINTS ===========

@router.get("/previa")
async def previa_comissao(
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Retorna preview (ou dados do fechamento se já existir)."""
    _exigir_admin(usuario)
    _validar_periodo(ano, mes)
    return comissao_service.calcular_previa(db, ano, mes)


@router.post("/fechar")
async def fechar(
    dados: FecharMesInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Fecha o mês. Grava em fechamento_comissao."""
    _exigir_admin(usuario)
    _validar_periodo(dados.ano, dados.mes)

    try:
        return comissao_service.fechar_mes(
            db,
            ano=dados.ano,
            mes=dados.mes,
            percentuais_customizados=dados.percentuais or {},
            admin_id=usuario.id,
            observacoes_por_tecnico=dados.observacoes or {},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/fechamento")
async def reabrir(
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Reabre o mês, remove todos os registros de fechamento."""
    _exigir_admin(usuario)
    _validar_periodo(ano, mes)

    n = comissao_service.reabrir_mes(db, ano, mes)
    return {"mensagem": f"Mês reaberto. {n} registro(s) de fechamento removido(s).", "removidos": n}


@router.get("/pdf")
async def pdf_consolidado(
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """PDF consolidado com todos os técnicos da competência."""
    _exigir_admin(usuario)
    _validar_periodo(ano, mes)

    try:
        pdf_bytes = comissao_service.gerar_pdf_consolidado(db, ano, mes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    filename = f"comissao_{ano}_{mes:02d}_consolidado.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf/{tecnico_id}")
async def pdf_individual(
    tecnico_id: int,
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """PDF individual de um técnico."""
    _exigir_admin(usuario)
    _validar_periodo(ano, mes)

    try:
        pdf_bytes = comissao_service.gerar_pdf_individual(db, tecnico_id, ano, mes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    filename = f"comissao_{ano}_{mes:02d}_tec_{tecnico_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/dashboard-total")
async def total_mes_atual(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Endpoint leve pra o card do dashboard admin: soma a comissão do mês atual."""
    _exigir_admin(usuario)

    hoje = datetime.now()
    previa = comissao_service.calcular_previa(db, hoje.year, hoje.month)
    return {
        "ano": hoje.year,
        "mes": hoje.month,
        "total_comissao": previa["total_comissao"],
        "total_chamados": previa["total_chamados"],
        "fechado": previa["fechado"],
        "tecnicos_count": len(previa["tecnicos"]),
    }
