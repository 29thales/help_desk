from pydantic import BaseModel
from typing import Optional, List


class ResumoMensal(BaseModel):
    cliente_id: int
    nome: str
    empresa: Optional[str]
    quantidade_chamados: int
    total_minutos: int
    total_horas: float
    total_horas_formatado: str
    total_faturado: float
    total_unidades: int = 0
    resumo_formatado: Optional[str] = None

    class Config:
        from_attributes = True


class ChamadoDetalhe(BaseModel):
    numero: str
    titulo: str
    tipo_servico: str
    status: str
    data_faturamento: str
    tempo_gasto_minutos: int
    valor_total: float

    class Config:
        from_attributes = True


class DetalheCliente(BaseModel):
    cliente_id: int
    nome: str
    empresa: Optional[str]
    ano: int
    mes: int
    quantidade_chamados: int
    total_minutos: int
    total_horas: float
    total_horas_formatado: str
    total_faturado: float
    chamados: List[ChamadoDetalhe]
    total_unidades: int = 0
    resumo_formatado: Optional[str] = None

    class Config:
        from_attributes = True
