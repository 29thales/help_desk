from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, time


# === CHAMADO ===

class ChamadoCriar(BaseModel):
    titulo: str
    descricao: str
    categoria: str = "geral"
    prioridade: str = "media"
    cliente_id: Optional[int] = None
    tipo_servico: str = "suporte_usuario"  # "suporte_usuario" ou "suporte_tecnico"

    # Para suporte técnico: OU informa servico_id (escolheu do catálogo)
    # OU servico_tecnico (nome livre para personalizado)
    servico_id: Optional[int] = None
    servico_tecnico: Optional[str] = None


class ChamadoAtualizar(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    prioridade: Optional[str] = None
    status: Optional[str] = None
    cliente_id: Optional[int] = None
    tipo_servico: Optional[str] = None
    servico_id: Optional[int] = None
    servico_tecnico: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_termino: Optional[datetime] = None


class HistoricoResposta(BaseModel):
    id: int
    chamado_id: int
    usuario_id: int
    usuario_nome: Optional[str] = None
    descricao: str
    tempo_minutos: int = 0
    data_atendimento: Optional[datetime] = None
    hora_inicio: Optional[time] = None
    hora_termino: Optional[time] = None
    criado_em: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True


class ChamadoResposta(BaseModel):
    id: int
    numero: str
    titulo: str
    descricao: str
    categoria: str
    prioridade: str
    status: str
    tipo_servico: str = "suporte_usuario"
    servico_id: Optional[int] = None
    servico_tecnico: Optional[str] = None
    servico_tecnico_nome: Optional[str] = None
    cliente_id: Optional[int] = None
    cliente_nome: Optional[str] = None
    solicitante_id: int
    data_inicio: Optional[datetime] = None
    data_termino: Optional[datetime] = None
    tempo_gasto_minutos: int = 0
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None
    historicos: List[HistoricoResposta] = []

    class Config:
        orm_mode = True
        from_attributes = True


# === HISTÓRICO ===

class HistoricoCriar(BaseModel):
    descricao: str
    tempo_minutos: int = 0
    data_atendimento: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_termino: Optional[time] = None


class HistoricoAtualizar(BaseModel):
    descricao: Optional[str] = None
    tempo_minutos: Optional[int] = None
    data_atendimento: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_termino: Optional[time] = None
