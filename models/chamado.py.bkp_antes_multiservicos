# models/chamado.py

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Time
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Chamado(Base):
    __tablename__ = "chamados"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(20), unique=True, nullable=False)
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=False)
    categoria = Column(String(50), default="geral", nullable=False)
    prioridade = Column(String(20), default="media", nullable=False)

    # Status: 'aberto' | 'atribuido' | 'em_atendimento' | 'finalizado'
    # 'atribuido' adicionado na Fase 1 (entre aberto e em_atendimento)
    status = Column(String(20), default="aberto", nullable=False)

    # Tipo de serviço: "suporte_usuario" ou "suporte_tecnico"
    tipo_servico = Column(String(30), default="suporte_usuario", nullable=False)

    # ============ SERVIÇO TÉCNICO ============
    servico_id = Column(Integer, ForeignKey("servicos_tecnicos.id"), nullable=True)
    servico = relationship("ServicoTecnico")

    # Mantido para compatibilidade com chamados antigos e serviços personalizados
    servico_tecnico = Column(String(150), nullable=True)

    valor_fixo = Column(Float, default=0.0, nullable=False)

    # Datas
    data_inicio = Column(DateTime, nullable=True)
    data_termino = Column(DateTime, nullable=True)

    # Tempo e valor
    tempo_gasto_minutos = Column(Integer, default=0, nullable=False)
    valor_total = Column(Float, default=0.0, nullable=False)

    # Vínculo com Cliente (empresa)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    cliente = relationship("Cliente", back_populates="chamados")

    # Vínculo com Usuário Solicitante
    solicitante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario_solicitante = relationship(
        "Usuario",
        back_populates="chamados_solicitados",
        foreign_keys=[solicitante_id],
    )

    # ============ FASE 1 - TÉCNICO ATRIBUÍDO ============
    tecnico_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    tecnico = relationship(
        "Usuario",
        back_populates="chamados_atendendo",
        foreign_keys=[tecnico_id],
    )

    # Motivo da última devolução (se houver). Texto livre.
    motivo_devolucao = Column(Text, nullable=True)

    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Histórico de atendimentos
    historicos = relationship(
        "HistoricoChamado",
        back_populates="chamado",
        order_by="desc(HistoricoChamado.criado_em)",
    )

    # Auditoria de transferências
    transferencias = relationship(
        "ChamadoTransferencia",
        back_populates="chamado",
        order_by="desc(ChamadoTransferencia.criado_em)",
    )

    def __repr__(self):
        return f"<Chamado(id={self.id}, numero='{self.numero}', status='{self.status}', tecnico_id={self.tecnico_id})>"


class HistoricoChamado(Base):
    """Cada entrada é um registro do que foi feito no chamado"""
    __tablename__ = "historico_chamados"

    id = Column(Integer, primary_key=True, index=True)
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    descricao = Column(Text, nullable=False)
    tempo_minutos = Column(Integer, default=0, nullable=False)

    # Campos de data/hora real do atendimento
    data_atendimento = Column(DateTime, nullable=True)
    hora_inicio = Column(Time, nullable=True)
    hora_termino = Column(Time, nullable=True)

    criado_em = Column(DateTime, default=datetime.now, nullable=False)

    chamado = relationship("Chamado", back_populates="historicos")
    usuario = relationship("Usuario")

    def __repr__(self):
        return f"<HistoricoChamado(id={self.id}, chamado_id={self.chamado_id})>"


# ============================================
# FASE 1 - AUDITORIA DE TRANSFERÊNCIAS
# ============================================

class ChamadoTransferencia(Base):
    """
    Registro histórico de transferências de chamados entre técnicos.
    Toda vez que admin/técnico transfere ou devolve um chamado,
    grava uma linha aqui — para auditoria.
    """
    __tablename__ = "chamado_transferencias"

    id = Column(Integer, primary_key=True, index=True)
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=False, index=True)

    # Quem detinha antes (None se chamado estava aberto sem técnico)
    de_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    # Pra quem foi transferido (None se foi devolvido pra fila aberta)
    para_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    motivo = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.now, nullable=False)

    # Relacionamentos
    chamado = relationship("Chamado", back_populates="transferencias")
    de_usuario = relationship("Usuario", foreign_keys=[de_usuario_id])
    para_usuario = relationship("Usuario", foreign_keys=[para_usuario_id])

    def __repr__(self):
        return (
            f"<ChamadoTransferencia(chamado_id={self.chamado_id}, "
            f"{self.de_usuario_id}→{self.para_usuario_id})>"
        )
