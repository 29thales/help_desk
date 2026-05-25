# routes/atendimentos.py
# ============================================
# ROTAS DE ATENDIMENTOS (REGISTROS TÉCNICOS)
# ============================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models.user import Usuario
from models.chamado import Chamado
from models.atendimento import Atendimento
from schemas.atendimento import AtendimentoCriar, AtendimentoResposta
from auth import obter_usuario_atual

# ============================================
# INICIALIZAR ROUTER
# ============================================

router = APIRouter()

# ============================================
# ROTA POST /registrar - REGISTRAR ATENDIMENTO
# ============================================

@router.post("/registrar", response_model=AtendimentoResposta)
async def registrar_atendimento(
    atendimento_data: AtendimentoCriar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Registra um novo atendimento técnico em um chamado
    
    Automáticamente:
    - Calcula o valor cobrado (tempo × valor_hora do atendente)
    - Atualiza o tempo_gasto do chamado
    - Atualiza o valor_total do chamado
    """
    # Verifica se o chamado existe
    chamado = db.query(Chamado).filter(Chamado.id == atendimento_data.chamado_id).first()
    
    if not chamado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado"
        )
    
    # Verifica permissão (admin ou atendente do chamado)
    if not usuario_atual.eh_admin and chamado.atendente_id != usuario_atual.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não está atribuído a este chamado"
        )
    
    # Calcula valor cobrado
    valor_cobrado = (atendimento_data.tempo_despendido / 60) * usuario_atual.valor_hora
    
    # Cria novo atendimento
    novo_atendimento = Atendimento(
        chamado_id=atendimento_data.chamado_id,
        atendente_id=usuario_atual.id,
        tempo_despendido=atendimento_data.tempo_despendido,
        descricao=atendimento_data.descricao,
        valor_cobrado=valor_cobrado
    )
    
    # Atualiza chamado
    chamado.tempo_gasto += atendimento_data.tempo_despendido
    chamado.valor_total += valor_cobrado
    
    # Se for o primeiro atendimento, marca como em_atendimento
    if chamado.status == "aberto":
        chamado.status = StatusChamado.EM_ATENDIMENTO
    
    db.add(novo_atendimento)
    db.commit()
    db.refresh(novo_atendimento)
    
    return AtendimentoResposta.from_orm(novo_atendimento)

# ============================================
# ROTA GET /chamado/{chamado_id} - LISTAR ATENDIMENTOS
# ============================================

@router.get("/chamado/{chamado_id}", response_model=list[AtendimentoResposta])
async def listar_atendimentos(
    chamado_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Lista todos os atendimentos de um chamado específico
    """
    # Verifica se o chamado existe e permissão
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    
    if not chamado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado"
        )
    
    if not usuario_atual.eh_admin and \
       chamado.usuario_id != usuario_atual.id and \
       chamado.atendente_id != usuario_atual.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão"
        )
    
    # Lista atendimentos
    atendimentos = db.query(Atendimento)\
        .filter(Atendimento.chamado_id == chamado_id)\
        .order_by(Atendimento.data_atendimento.desc())\
        .all()
    
    return [AtendimentoResposta.from_orm(a) for a in atendimentos]

print("✅ Rotas de Atendimentos configuradas!")