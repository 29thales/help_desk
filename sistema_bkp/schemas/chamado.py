# schemas/chamado.py
# ============================================
# VALIDAÇÃO DE DADOS DE CHAMADO (Pydantic)
# ============================================

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

# ============================================
# ENUMS DE STATUS E PRIORIDADE
# ============================================

class StatusChamado(str, Enum):
    ABERTO = "aberto"
    EM_ATENDIMENTO = "em_atendimento"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"

class PrioridadeChamado(str, Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    URGENTE = "urgente"

# ============================================
# SCHEMA DE CRIAÇÃO DE CHAMADO
# ============================================

class ChamadoCriar(BaseModel):
    """
    Dados necessários para CRIAR um chamado
    """
    titulo: str = Field(..., min_length=5, max_length=255)
    descricao: str = Field(..., min_length=10)
    categoria: Optional[str] = "geral"
    prioridade: Optional[PrioridadeChamado] = PrioridadeChamado.MEDIA
    tempo_estimado: Optional[int] = 0

# ============================================
# SCHEMA DE ATUALIZAÇÃO DE CHAMADO
# ============================================

class ChamadoAtualizar(BaseModel):
    """
    Dados para ATUALIZAR um chamado
    """
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[StatusChamado] = None
    prioridade: Optional[PrioridadeChamado] = None
    atendente_id: Optional[int] = None
    tempo_estimado: Optional[int] = None

# ============================================
# SCHEMA DE RESPOSTA DE CHAMADO
# ============================================

class ChamadoResposta(BaseModel):
    """
    Dados de um chamado para RESPONDER ao navegador
    """
    id: int
    titulo: str
    descricao: str
    categoria: str
    usuario_id: int
    atendente_id: Optional[int] = None
    status: StatusChamado
    prioridade: PrioridadeChamado
    tempo_estimado: int
    tempo_gasto: int
    valor_hora: float
    valor_total: float
    criado_em: datetime
    atualizado_em: datetime
    finalizado_em: Optional[datetime] = None
    
    class Config:
        from_attributes = True

print("✅ Schemas de Chamado definidos com sucesso!")