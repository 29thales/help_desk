from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from auth import obter_usuario_atual
from services.faturamento_service import FaturamentoService
from schemas.faturamento import ResumoMensal, DetalheCliente

router = APIRouter()

@router.get("/resumo", response_model=list[ResumoMensal])
def obter_resumo_mensal(
    ano: int = Query(...),
    mes: int = Query(...),
    cliente_id: int = Query(None),
    db: Session = Depends(get_db),
    usuario_atual = Depends(obter_usuario_atual)
):
    try:
        return FaturamentoService.obter_resumo_mensal(db, ano, mes, cliente_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter resumo mensal: {str(e)}")

@router.get("/detalhe/{cliente_id}", response_model=DetalheCliente)
def obter_detalhe_cliente(
    cliente_id: int,
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario_atual = Depends(obter_usuario_atual)
):
    try:
        return FaturamentoService.obter_detalhe_cliente(db, cliente_id, ano, mes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter detalhe do cliente: {str(e)}")

@router.get("/pdf")
def gerar_pdf_geral(
    ano: int = Query(...),
    mes: int = Query(...),
    cliente_id: int = Query(None),
    db: Session = Depends(get_db),
    usuario_atual = Depends(obter_usuario_atual)
):
    try:
        return FaturamentoService.gerar_pdf_geral(db, ano, mes, cliente_id)
    except ImportError:
        raise HTTPException(status_code=500, detail="Biblioteca reportlab não está instalada. Instale com 'pip install reportlab'.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF geral: {str(e)}")

@router.get("/pdf/{cliente_id}")
def gerar_pdf_cliente(
    cliente_id: int,
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario_atual = Depends(obter_usuario_atual)
):
    try:
        return FaturamentoService.gerar_pdf_cliente(db, cliente_id, ano, mes)
    except ImportError:
        raise HTTPException(status_code=500, detail="Biblioteca reportlab não está instalada. Instale com 'pip install reportlab'.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF do cliente: {str(e)}")