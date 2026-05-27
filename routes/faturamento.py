from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from auth import obter_usuario_atual
from services.faturamento_service import FaturamentoService
from schemas.faturamento import ResumoMensal, DetalheCliente
from pydantic import BaseModel, EmailStr
from services.email_service import enviar_email_faturamento, montar_template_faturamento
from models.cliente import Cliente

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


# ============================================================
# ENVIO DE FATURAMENTO POR EMAIL
# ============================================================

class EnviarEmailFaturamentoInput(BaseModel):
    cliente_id: int
    ano: int
    mes: int
    destinatario: EmailStr
    assunto: str
    corpo: str


@router.get("/email-template/{cliente_id}")
def obter_template_email(
    cliente_id: int,
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    usuario_atual = Depends(obter_usuario_atual),
):
    """Retorna template padrao (assunto + corpo) e email do cliente
    pra preencher o modal de envio."""
    eh_admin = (
        getattr(usuario_atual, "tipo_usuario", None) == "admin"
        or getattr(usuario_atual, "is_admin", False)
    )
    if not eh_admin:
        raise HTTPException(status_code=403, detail="Apenas admins podem enviar email")

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    if not cliente.email:
        raise HTTPException(
            status_code=400,
            detail="Este cliente nao tem email cadastrado. Edite o cliente para incluir o email."
        )

    detalhe = FaturamentoService.obter_detalhe_cliente(db, cliente_id, ano, mes)
    template = montar_template_faturamento(detalhe)

    return {
        "destinatario": cliente.email,
        "assunto": template["assunto"],
        "corpo": template["corpo"],
        "quantidade_chamados": detalhe.get("quantidade_chamados", 0),
        "total_faturado": detalhe.get("total_faturado", 0),
    }


@router.post("/enviar-email")
def enviar_email(
    dados: EnviarEmailFaturamentoInput,
    db: Session = Depends(get_db),
    usuario_atual = Depends(obter_usuario_atual),
):
    """Envia o PDF de faturamento por email.
    Admin pode editar destinatario, assunto e corpo antes de enviar."""
    eh_admin = (
        getattr(usuario_atual, "tipo_usuario", None) == "admin"
        or getattr(usuario_atual, "is_admin", False)
    )
    if not eh_admin:
        raise HTTPException(status_code=403, detail="Apenas admins podem enviar email")

    cliente = db.query(Cliente).filter(Cliente.id == dados.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    try:
        response_pdf = FaturamentoService.gerar_pdf_cliente(db, dados.cliente_id, dados.ano, dados.mes)
        pdf_path = response_pdf.path
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {e}")

    nome_arquivo = f"faturamento_{cliente.nome.replace(' ', '_')}_{dados.ano}_{dados.mes:02d}.pdf"

    sucesso, mensagem = enviar_email_faturamento(
        destinatario=str(dados.destinatario),
        assunto=dados.assunto,
        corpo=dados.corpo,
        pdf_bytes=pdf_bytes,
        nome_arquivo_pdf=nome_arquivo,
        nome_remetente="RNS TECH",
    )

    if not sucesso:
        raise HTTPException(status_code=500, detail=mensagem)

    return {"sucesso": True, "mensagem": mensagem}
