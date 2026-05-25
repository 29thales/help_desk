# routes/chamados.py
# ============================================
# ROTAS DE CHAMADOS (CRUD)
# ============================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models.user import Usuario
from models.chamado import Chamado
from schemas.chamado import ChamadoCriar, ChamadoAtualizar, ChamadoResposta
from auth import obter_usuario_atual

# ============================================
# INICIALIZAR ROUTER
# ============================================

router = APIRouter()

# ============================================
# ROTA POST /criar - CRIAR NOVO CHAMADO
# ============================================

@router.post("/criar", response_model=ChamadoResposta)
async def criar_chamado(
    chamado_data: ChamadoCriar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Cria um novo chamado/ticket
    
    Args:
        chamado_data: Dados do chamado (título, descrição, etc)
        usuario_atual: Usuário logado (automático)
        db: Sessão do banco
        
    Returns:
        ChamadoResposta: Dados do chamado criado
    """
    # Cria novo chamado
    novo_chamado = Chamado(
        titulo=chamado_data.titulo,
        descricao=chamado_data.descricao,
        categoria=chamado_data.categoria,
        prioridade=chamado_data.prioridade,
        tempo_estimado=chamado_data.tempo_estimado,
        usuario_id=usuario_atual.id,
        valor_hora=usuario_atual.valor_hora,
        status=StatusChamado.ABERTO
    )
    
    db.add(novo_chamado)
    db.commit()
    db.refresh(novo_chamado)
    
    return ChamadoResposta.from_orm(novo_chamado)

# ============================================
# ROTA GET /listar - LISTAR CHAMADOS
# ============================================

@router.get("/listar", response_model=list[ChamadoResposta])
async def listar_chamados(
    status: str = None,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Lista todos os chamados do usuário ou admin vê todos
    
    Args:
        status: Filtrar por status (opcional)
        usuario_atual: Usuário logado
        db: Sessão do banco
        
    Returns:
        Lista de chamados
    """
    query = db.query(Chamado)
    
    # Se não for admin, mostra apenas seus chamados
    if not usuario_atual.eh_admin:
        query = query.filter(
            (Chamado.usuario_id == usuario_atual.id) |
            (Chamado.atendente_id == usuario_atual.id)
        )
    
    # Filtrar por status se fornecido
    if status:
        query = query.filter(Chamado.status == status)
    
    chamados = query.order_by(Chamado.criado_em.desc()).all()
    
    return [ChamadoResposta.from_orm(c) for c in chamados]

# ============================================
# ROTA GET /{id} - OBTER CHAMADO POR ID
# ============================================

@router.get("/{chamado_id}", response_model=ChamadoResposta)
async def obter_chamado(
    chamado_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obtém um chamado específico por ID
    """
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    
    if not chamado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado"
        )
    
    # Verifica permissão (admin, criador ou atendente)
    if not usuario_atual.eh_admin and \
       chamado.usuario_id != usuario_atual.id and \
       chamado.atendente_id != usuario_atual.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para acessar este chamado"
        )
    
    return ChamadoResposta.from_orm(chamado)

# ============================================
# ROTA PUT /{id} - ATUALIZAR CHAMADO
# ============================================

@router.put("/{chamado_id}", response_model=ChamadoResposta)
async def atualizar_chamado(
    chamado_id: int,
    chamado_data: ChamadoAtualizar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Atualiza um chamado
    """
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    
    if not chamado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado"
        )
    
    # Verifica permissão (admin ou criador)
    if not usuario_atual.eh_admin and chamado.usuario_id != usuario_atual.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para atualizar este chamado"
        )
    
    # Atualizar campos
    if chamado_data.titulo:
        chamado.titulo = chamado_data.titulo
    if chamado_data.descricao:
        chamado.descricao = chamado_data.descricao
    if chamado_data.status:
        chamado.status = chamado_data.status
        if chamado_data.status == StatusChamado.FINALIZADO:
            chamado.finalizado_em = datetime.utcnow()
    if chamado_data.prioridade:
        chamado.prioridade = chamado_data.prioridade
    if chamado_data.atendente_id:
        chamado.atendente_id = chamado_data.atendente_id
        if chamado.status == StatusChamado.ABERTO:
            chamado.status = StatusChamado.EM_ATENDIMENTO
    if chamado_data.tempo_estimado is not None:
        chamado.tempo_estimado = chamado_data.tempo_estimado
    
    db.commit()
    db.refresh(chamado)
    
    return ChamadoResposta.from_orm(chamado)

print("✅ Rotas de Chamados configuradas!")