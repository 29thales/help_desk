# models/fechamento_comissao.py

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class FechamentoComissao(Base):
    __tablename__ = "fechamento_comissao"
    __table_args__ = (
        UniqueConstraint("tecnico_id", "ano", "mes", name="uq_fechamento_tecnico_periodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tecnico_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)

    # Percentual que foi efetivamente aplicado (pode diferir do perfil do técnico)
    percentual_aplicado = Column(Float, nullable=False)
    valor_base = Column(Float, nullable=False, default=0.0)
    valor_comissao = Column(Float, nullable=False, default=0.0)
    quantidade_chamados = Column(Integer, nullable=False, default=0)

    observacoes = Column(Text, nullable=True)
    fechado_em = Column(DateTime, nullable=False, default=datetime.now)
    fechado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    tecnico = relationship("Usuario", foreign_keys=[tecnico_id])
    fechado_por = relationship("Usuario", foreign_keys=[fechado_por_id])

    def __repr__(self):
        return f"<FechamentoComissao(tec={self.tecnico_id}, {self.ano}-{self.mes:02d}, R$ {self.valor_comissao})>"
