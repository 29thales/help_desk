# schemas/atendimento.py
# ============================================
# VALIDAÇÃO DE DADOS DE ATENDIMENTO (Pydantic)
# ============================================

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# ============================================
# SCHEMA DE CRIAÇÃO DE ATENDIMENTO
# ============================================

class AtendimentoCriar(BaseModel):
    """
    Dados necessários para REGISTRAR um atendimento
    """
    chamado_id: int
    tempo_despendido: int = Field(..., gt=0)  # Tempo em minutos, obrigatório e > 0
    descricao: str = Field(..., min_length=10)

# ============================================
# SCHEMA DE RESPOSTA DE ATENDIMENTO
# ============================================

class AtendimentoResposta(BaseModel):
    """
    Dados de um atendimento para RESPONDER ao navegador
    """
    id: int
    chamado_id: int
    atendente_id: int
    tempo_despendido: int
    descricao: str
    valor_cobrado: float
    data_atendimento: datetime
    criado_em: datetime
    
    class Config:
        from_attributes = True

print("✅ Schemas de Atendimento definidos com sucesso!")