from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, time, timedelta
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models.user import Usuario
from models.chamado import Chamado, HistoricoChamado, ChamadoTransferencia
from models.cliente import Cliente
from models.servico_tecnico import ServicoTecnico
from schemas.chamado import (
    ChamadoCriar, ChamadoAtualizar, ChamadoResposta,
    HistoricoCriar, HistoricoAtualizar, HistoricoResposta
)
from auth import obter_usuario_atual

router = APIRouter()


# =================== HELPERS ===================

def gerar_numero(db: Session) -> str:
    ultimo = db.query(func.max(Chamado.id)).scalar() or 0
    return f"CHM-{ultimo + 1:04d}"


def _serializar_historico(h: HistoricoChamado) -> dict:
    return {
        "id": h.id,
        "chamado_id": h.chamado_id,
        "usuario_id": h.usuario_id,
        "usuario_nome": h.usuario.nome if h.usuario else None,
        "descricao": h.descricao,
        "tempo_minutos": h.tempo_minutos or 0,
        "data_atendimento": h.data_atendimento.isoformat() if h.data_atendimento else None,
        "hora_inicio": h.hora_inicio.strftime("%H:%M") if h.hora_inicio else None,
        "hora_termino": h.hora_termino.strftime("%H:%M") if h.hora_termino else None,
        "criado_em": h.criado_em.isoformat() if h.criado_em else None,
    }


def serializar_chamado(chamado: Chamado, usuario: Usuario = None) -> dict:
    historicos = [_serializar_historico(h) for h in chamado.historicos]

    # Resolução do nome do serviço
    servico_nome = None
    if chamado.servico:
        servico_nome = chamado.servico.nome
    elif chamado.servico_tecnico:
        # Chamado com serviço personalizado (texto livre) ou vindo de dados antigos
        servico_nome = chamado.servico_tecnico

    # Esconde valor se o usuário não for admin (técnicos/clientes nunca veem R$)
    pode_ver_valor = True
    if usuario is not None:
        eh_admin = (
            getattr(usuario, "tipo_usuario", None) == "admin"
            or getattr(usuario, "is_admin", False)
        )
        if not eh_admin:
            pode_ver_valor = False

    # Origem do chamado: derivado do tipo_usuario do solicitante
    # (admin/tecnico/cliente) — usado pra badge "🌐 Portal" e filtro
    origem = None
    if chamado.usuario_solicitante:
        origem = getattr(chamado.usuario_solicitante, "tipo_usuario", None)

    dados = {
        "id": chamado.id,
        "numero": chamado.numero,
        "titulo": chamado.titulo,
        "descricao": chamado.descricao,
        "categoria": chamado.categoria,
        "prioridade": chamado.prioridade,
        "status": chamado.status,
        "tipo_servico": chamado.tipo_servico or "suporte_usuario",
        "servico_id": chamado.servico_id,
        "servico_tecnico": chamado.servico_tecnico,
        "servico_tecnico_nome": servico_nome,
        "cliente_id": chamado.cliente_id,
        "cliente_nome": chamado.cliente.nome if chamado.cliente else None,
        "solicitante_id": chamado.solicitante_id,
        "solicitante_nome": chamado.usuario_solicitante.nome if chamado.usuario_solicitante else None,
        "origem": origem,
        "tecnico_id": chamado.tecnico_id,
        "tecnico_nome": chamado.tecnico.nome if chamado.tecnico else None,
        "motivo_devolucao": chamado.motivo_devolucao,
        "data_inicio": chamado.data_inicio.isoformat() if chamado.data_inicio else None,
        "data_termino": chamado.data_termino.isoformat() if chamado.data_termino else None,
        "tempo_gasto_minutos": chamado.tempo_gasto_minutos or 0,
        "criado_em": chamado.criado_em.isoformat() if chamado.criado_em else None,
        "atualizado_em": chamado.atualizado_em.isoformat() if chamado.atualizado_em else None,
        "historicos": historicos,
    }

    if pode_ver_valor:
        dados["valor_fixo"] = chamado.valor_fixo or 0.0
        dados["valor_total"] = chamado.valor_total or 0.0
        # Valor padrão sugerido do serviço (para modal de finalização)
        dados["servico_valor_padrao"] = chamado.servico.valor_padrao if chamado.servico else 0.0
        # Valor/hora do cliente
        dados["cliente_valor_hora"] = float(chamado.cliente.valor_hora) if chamado.cliente and chamado.cliente.valor_hora else 0.0

    return dados


def calcular_valor_por_tempo(minutos: int, valor_hora: float) -> float:
    """
    Regra de cobrança (NÃO ALTERAR):
    - 0 minutos = R$ 0
    - 1 a 30 minutos = cobra meia hora (valor_hora / 2)
    - 31+ minutos = meia hora + proporcional do excedente
    """
    if minutos <= 0 or valor_hora <= 0:
        return 0.0

    meia_hora = valor_hora / 2

    if minutos <= 30:
        return round(meia_hora, 2)
    else:
        excedente = minutos - 30
        proporcional = (excedente / 60) * valor_hora
        return round(meia_hora + proporcional, 2)


def recalcular_chamado(chamado: Chamado, db: Session):
    """
    Recalcula tempo e valor baseado no tipo de serviço.

    IMPORTANTE: para suporte_tecnico, NÃO calcula valor automaticamente mais.
    O valor só é definido quando admin finaliza o chamado via /finalizar-tecnico.
    """
    total_minutos = db.query(func.sum(HistoricoChamado.tempo_minutos))\
        .filter(HistoricoChamado.chamado_id == chamado.id).scalar() or 0
    chamado.tempo_gasto_minutos = total_minutos

    if chamado.tipo_servico == "suporte_tecnico":
        # Não mexe no valor_total aqui. Só é definido no /finalizar-tecnico.
        # Exceção: se o chamado ainda não foi finalizado, mantém zero.
        if chamado.status != "finalizado":
            chamado.valor_total = 0.0
        # Se está finalizado, preserva o valor que o admin definiu
    else:
        # Valor por tempo: usa valor_hora do cliente cadastrado
        if chamado.cliente and chamado.cliente.valor_hora:
            chamado.valor_total = calcular_valor_por_tempo(total_minutos, chamado.cliente.valor_hora)
        else:
            chamado.valor_total = 0.0


def _calcular_minutos_entre(hora_inicio: time, hora_termino: time) -> int:
    if not hora_inicio or not hora_termino:
        return 0
    base = date.today()
    dt_inicio = datetime.combine(base, hora_inicio)
    dt_termino = datetime.combine(base, hora_termino)
    if dt_termino < dt_inicio:
        dt_termino += timedelta(days=1)
    delta = dt_termino - dt_inicio
    return int(delta.total_seconds() // 60)


def _aplicar_data_hora_ao_historico(
    historico: HistoricoChamado,
    chamado: Chamado,
    data_atendimento,
    hora_inicio,
    hora_termino,
    tempo_minutos_direto,
):
    if data_atendimento is not None:
        if isinstance(data_atendimento, datetime):
            historico.data_atendimento = data_atendimento
        elif isinstance(data_atendimento, date):
            historico.data_atendimento = datetime.combine(data_atendimento, time(0, 0))

    if chamado.tipo_servico == "suporte_usuario":
        historico.hora_inicio = hora_inicio
        historico.hora_termino = hora_termino

        if hora_inicio and hora_termino:
            calc = _calcular_minutos_entre(hora_inicio, hora_termino)
            historico.tempo_minutos = calc
        elif tempo_minutos_direto is not None:
            historico.tempo_minutos = int(tempo_minutos_direto)
    else:
        historico.hora_inicio = None
        historico.hora_termino = None
        if tempo_minutos_direto is not None:
            historico.tempo_minutos = int(tempo_minutos_direto)


# =================== CHAMADOS CRUD ===================

@router.get("/")
async def listar_chamados(
    status: str = None,
    cliente_id: int = None,
    tipo_servico: str = None,
    meus: bool = False,
    fila_aberta: bool = False,
    fila: str = None,
    origem: str = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Lista chamados.

    Parâmetros:
    - fila=minha → só chamados atribuídos ao usuário logado (alias: meus=true)
    - fila=aberta → chamados com status='aberto' (sem técnico). Alias: fila_aberta=true.
      Só retorna conteúdo para técnicos ELEGÍVEIS (pode_ver_fila_aberta=true) ou admin.
    - Sem parâmetros: admin vê todos; técnico/cliente vê só os próprios.
    """
    # Normaliza aliases
    if fila == "minha":
        meus = True
    elif fila == "aberta":
        fila_aberta = True

    eh_admin = (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )
    eh_tecnico = getattr(usuario, "tipo_usuario", None) == "tecnico"

    query = db.query(Chamado)

    # Filtro por escopo
    if fila_aberta:
        # Só eleg. veem fila (briefing)
        if not eh_admin:
            if not eh_tecnico or not getattr(usuario, "pode_ver_fila_aberta", False):
                return []
        query = query.filter(Chamado.status == "aberto", Chamado.tecnico_id.is_(None))
    elif meus:
        query = query.filter(Chamado.tecnico_id == usuario.id)
    else:
        # Escopo default: admin vê tudo; técnico vê só os dele; cliente vê só os que ele abriu
        if eh_tecnico:
            query = query.filter(Chamado.tecnico_id == usuario.id)
        elif not eh_admin:
            # Cliente ou outro: só os que ele mesmo abriu
            query = query.filter(Chamado.solicitante_id == usuario.id)

    # Filtros adicionais
    if status:
        query = query.filter(Chamado.status == status)
    if cliente_id:
        query = query.filter(Chamado.cliente_id == cliente_id)
    if tipo_servico:
        query = query.filter(Chamado.tipo_servico == tipo_servico)
    if origem:
        # Origem = tipo do solicitante. Join com usuarios.
        if origem in ("admin", "tecnico", "cliente"):
            query = query.join(Usuario, Usuario.id == Chamado.solicitante_id).filter(
                Usuario.tipo_usuario == origem
            )

    chamados = query.order_by(Chamado.criado_em.desc()).all()
    return [serializar_chamado(c, usuario) for c in chamados]


@router.post("/")
async def criar_chamado(
    dados: ChamadoCriar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    numero = gerar_numero(db)

    # Novo fluxo técnico: valor começa em ZERO, será definido na finalização
    servico_id = None
    servico_tecnico_texto = None

    if dados.tipo_servico == "suporte_tecnico":
        if dados.servico_id:
            # Validar se o serviço existe e está ativo
            servico = db.query(ServicoTecnico).filter(
                ServicoTecnico.id == dados.servico_id,
                ServicoTecnico.ativo == True
            ).first()
            if not servico:
                raise HTTPException(status_code=400, detail="Serviço não encontrado ou inativo")
            servico_id = servico.id
            servico_tecnico_texto = servico.nome
        elif dados.servico_tecnico:
            # Compatibilidade: admin ainda pode criar com texto livre.
            # Técnico NÃO pode (serviço é obrigatório vir do catálogo).
            eh_admin_criador = (
                getattr(usuario, "tipo_usuario", None) == "admin"
                or getattr(usuario, "is_admin", False)
            )
            if not eh_admin_criador:
                raise HTTPException(
                    status_code=400,
                    detail="Técnico precisa selecionar um serviço do catálogo (serviços personalizados só podem ser criados pelo admin)",
                )
            servico_tecnico_texto = dados.servico_tecnico.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail="Selecione um serviço do catálogo"
            )

    # Auto-atribuição: se quem abre é técnico, já pega pra si
    eh_tecnico = getattr(usuario, "tipo_usuario", None) == "tecnico"
    tecnico_id = usuario.id if eh_tecnico else None
    status_inicial = "atribuido" if eh_tecnico else "aberto"

    novo = Chamado(
        numero=numero,
        titulo=dados.titulo,
        descricao=dados.descricao,
        categoria=dados.categoria,
        prioridade=dados.prioridade,
        cliente_id=dados.cliente_id,
        solicitante_id=usuario.id,
        tipo_servico=dados.tipo_servico,
        servico_id=servico_id,
        servico_tecnico=servico_tecnico_texto,
        valor_fixo=0.0,      # Sempre zero na abertura (novo fluxo)
        valor_total=0.0,     # Sempre zero na abertura (novo fluxo)
        status=status_inicial,
        tecnico_id=tecnico_id,
        data_inicio=datetime.now()
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return serializar_chamado(novo, usuario)


@router.get("/{chamado_id}")
async def obter_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")
    return serializar_chamado(chamado, usuario)


@router.put("/{chamado_id}")
async def atualizar_chamado(
    chamado_id: int,
    dados: ChamadoAtualizar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    dados_dict = dados.dict(exclude_unset=True) if hasattr(dados, 'dict') else dados.model_dump(exclude_unset=True)

    # Bloqueia finalizar direto por aqui se for técnico sem valor definido
    if dados_dict.get("status") == "finalizado" and chamado.tipo_servico == "suporte_tecnico":
        if (chamado.valor_total or 0) <= 0:
            raise HTTPException(
                status_code=400,
                detail="Para finalizar chamado técnico use o endpoint /finalizar-tecnico para definir o valor."
            )

    for campo, valor in dados_dict.items():
        if campo == "servico_id":
            if valor is not None:
                if not getattr(usuario, "is_admin", False):
                    raise HTTPException(status_code=403, detail="Apenas admins podem alterar o serviço")
                s = db.query(ServicoTecnico).filter(ServicoTecnico.id == valor).first()
                if not s:
                    raise HTTPException(status_code=400, detail="Serviço não encontrado")
                chamado.servico_id = s.id
                chamado.servico_tecnico = s.nome
            continue
        if campo in ('data_inicio', 'data_termino') and isinstance(valor, str):
            valor = datetime.fromisoformat(valor)
        setattr(chamado, campo, valor)

    if dados_dict.get('status') == 'finalizado' and not chamado.data_termino:
        chamado.data_termino = datetime.now()

    recalcular_chamado(chamado, db)

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


# =================== FINALIZAÇÃO ===================

class FinalizarTecnicoInput(BaseModel):
    # Usado pelo ADMIN — permite sobrescrever valor/quantidade
    valor_unitario: float
    quantidade: int


@router.post("/{chamado_id}/finalizar-tecnico")
async def finalizar_chamado_tecnico(
    chamado_id: int,
    dados: FinalizarTecnicoInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    [ADMIN] Finaliza chamado técnico definindo valor unitário × quantidade.
    Usado pela tela de admin, que mostra o modal com inputs.
    """
    eh_admin = (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )
    if not eh_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem usar este endpoint (técnico usa /finalizar)")

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.tipo_servico != "suporte_tecnico":
        raise HTTPException(status_code=400, detail="Este endpoint é só para chamados técnicos")

    valor_unit = float(dados.valor_unitario or 0)
    quantidade = int(dados.quantidade or 1)

    if valor_unit < 0:
        raise HTTPException(status_code=400, detail="Valor unitário não pode ser negativo")
    if quantidade < 1:
        raise HTTPException(status_code=400, detail="Quantidade precisa ser pelo menos 1")

    valor_total = round(valor_unit * quantidade, 2)

    chamado.valor_fixo = valor_unit
    chamado.valor_total = valor_total
    chamado.tempo_gasto_minutos = quantidade
    chamado.status = "finalizado"
    if not chamado.data_termino:
        chamado.data_termino = datetime.now()

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


@router.post("/{chamado_id}/finalizar")
async def finalizar_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Finalização simples (técnico ou admin). Calcula valor automaticamente:

    - Suporte ao Usuário: usa soma dos minutos × valor_hora do cliente
      (já calculado pela função recalcular_chamado).
    - Suporte Técnico: usa quantidade_registrada × valor_padrão_do_serviço.
      Se o chamado não tiver um serviço do catálogo vinculado (texto livre antigo),
      só admin pode finalizar pelo endpoint /finalizar-tecnico definindo o valor manual.
    """
    eh_admin = (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )
    eh_tecnico = getattr(usuario, "tipo_usuario", None) == "tecnico"

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.status == "finalizado":
        raise HTTPException(status_code=400, detail="Chamado já está finalizado")

    # Técnico só pode finalizar os próprios
    if eh_tecnico and chamado.tecnico_id != usuario.id:
        raise HTTPException(
            status_code=403,
            detail="Você só pode finalizar chamados atribuídos a você",
        )
    if not eh_admin and not eh_tecnico:
        raise HTTPException(status_code=403, detail="Sem permissão para finalizar")

    if (chamado.tempo_gasto_minutos or 0) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Antes de finalizar, adicione pelo menos um histórico com tempo/quantidade",
        )

    if chamado.tipo_servico == "suporte_tecnico":
        # Precisa de um serviço do catálogo com valor definido
        if not chamado.servico_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Este chamado não tem um serviço do catálogo vinculado. "
                    "Admin precisa finalizar definindo o valor manualmente."
                ),
            )
        servico = db.query(ServicoTecnico).filter(ServicoTecnico.id == chamado.servico_id).first()
        valor_unit = float(servico.valor_padrao or 0) if servico else 0.0
        if valor_unit <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"O serviço '{servico.nome if servico else ''}' não tem valor padrão cadastrado. "
                    "Admin precisa cadastrar o valor no catálogo ou finalizar definindo valor manualmente."
                ),
            )
        quantidade = int(chamado.tempo_gasto_minutos or 0)
        chamado.valor_fixo = valor_unit
        chamado.valor_total = round(valor_unit * quantidade, 2)
    else:
        # Suporte ao usuário: já foi calculado pela recalcular_chamado
        # mas garante que está atualizado
        recalcular_chamado(chamado, db)

    chamado.status = "finalizado"
    if not chamado.data_termino:
        chamado.data_termino = datetime.now()

    db.commit()
    db.refresh(chamado)

    # Retorno pro técnico: NUNCA com R$ (serializar_chamado já esconde)
    return serializar_chamado(chamado, usuario)


# =================== TROCAR SERVIÇO (técnico/admin) ===================

class TrocarServicoInput(BaseModel):
    servico_id: int


@router.put("/{chamado_id}/servico")
async def trocar_servico(
    chamado_id: int,
    dados: TrocarServicoInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Troca o serviço do catálogo vinculado ao chamado.
    - Técnico: só nos chamados dele, enquanto não finalizado.
    - Admin: em qualquer chamado não finalizado.
    """
    eh_admin = (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )
    eh_tecnico = getattr(usuario, "tipo_usuario", None) == "tecnico"

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.tipo_servico != "suporte_tecnico":
        raise HTTPException(status_code=400, detail="Só aplicável a chamados de suporte técnico")

    if chamado.status == "finalizado":
        raise HTTPException(status_code=400, detail="Chamado finalizado não pode ter o serviço trocado")

    if eh_tecnico and chamado.tecnico_id != usuario.id:
        raise HTTPException(status_code=403, detail="Sem permissão para este chamado")
    if not eh_admin and not eh_tecnico:
        raise HTTPException(status_code=403, detail="Sem permissão")

    servico = db.query(ServicoTecnico).filter(
        ServicoTecnico.id == dados.servico_id,
        ServicoTecnico.ativo == True,
    ).first()
    if not servico:
        raise HTTPException(status_code=400, detail="Serviço não encontrado ou inativo")

    chamado.servico_id = servico.id
    chamado.servico_tecnico = servico.nome

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


@router.delete("/{chamado_id}")
async def deletar_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Deleta um chamado e todos os registros relacionados.
    Só admin pode deletar.
    """
    # Só admin pode deletar
    eh_admin = (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )
    if not eh_admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem deletar chamados"
        )

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    # IMPORTANTE: deletar registros relacionados ANTES de deletar o chamado
    # Senão o SQLAlchemy tenta setar chamado_id=NULL nas FK e quebra (NOT NULL constraint)

    # 1. Deletar transferências do chamado (Fase 1)
    db.query(ChamadoTransferencia).filter(
        ChamadoTransferencia.chamado_id == chamado_id
    ).delete(synchronize_session=False)

    # 2. Deletar históricos do chamado
    db.query(HistoricoChamado).filter(
        HistoricoChamado.chamado_id == chamado_id
    ).delete(synchronize_session=False)

    # 3. Agora sim deleta o chamado
    db.delete(chamado)
    db.commit()

    return {"mensagem": "Chamado deletado com sucesso"}


# =================== HISTÓRICO ===================

@router.post("/{chamado_id}/historico")
async def adicionar_historico(
    chamado_id: int,
    dados: HistoricoCriar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    # Técnico só pode mexer em chamados atribuídos a ele
    eh_admin = (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )
    eh_tecnico = getattr(usuario, "tipo_usuario", None) == "tecnico"
    if eh_tecnico and chamado.tecnico_id != usuario.id:
        raise HTTPException(
            status_code=403,
            detail="Você só pode adicionar histórico em chamados atribuídos a você",
        )

    historico = HistoricoChamado(
        chamado_id=chamado_id,
        usuario_id=usuario.id,
        descricao=dados.descricao,
        tempo_minutos=0,
    )

    _aplicar_data_hora_ao_historico(
        historico=historico,
        chamado=chamado,
        data_atendimento=dados.data_atendimento,
        hora_inicio=dados.hora_inicio,
        hora_termino=dados.hora_termino,
        tempo_minutos_direto=dados.tempo_minutos,
    )

    db.add(historico)
    db.flush()  # Garante que o novo histórico entra na query de soma do recalcular

    # Transição de estado no primeiro histórico
    if chamado.status in ("aberto", "atribuido"):
        chamado.status = "em_atendimento"
    # Se motivo_devolucao estava setado (chamado foi devolvido anteriormente),
    # limpa porque o técnico atual está atendendo
    if chamado.motivo_devolucao:
        chamado.motivo_devolucao = None

    recalcular_chamado(chamado, db)
    db.commit()
    db.refresh(historico)

    return _serializar_historico(historico)


@router.put("/{chamado_id}/historico/{historico_id}")
async def editar_historico(
    chamado_id: int,
    historico_id: int,
    dados: HistoricoAtualizar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    historico = db.query(HistoricoChamado).filter(
        HistoricoChamado.id == historico_id,
        HistoricoChamado.chamado_id == chamado_id
    ).first()
    if not historico:
        raise HTTPException(status_code=404, detail="Histórico não encontrado")

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()

    dados_dict = dados.dict(exclude_unset=True) if hasattr(dados, 'dict') else dados.model_dump(exclude_unset=True)

    if "descricao" in dados_dict:
        historico.descricao = dados_dict["descricao"]

    tem_campo_tempo = any(
        k in dados_dict for k in ("tempo_minutos", "data_atendimento", "hora_inicio", "hora_termino")
    )

    if tem_campo_tempo:
        _aplicar_data_hora_ao_historico(
            historico=historico,
            chamado=chamado,
            data_atendimento=dados_dict.get("data_atendimento", historico.data_atendimento),
            hora_inicio=dados_dict.get("hora_inicio"),
            hora_termino=dados_dict.get("hora_termino"),
            tempo_minutos_direto=dados_dict.get("tempo_minutos"),
        )

    recalcular_chamado(chamado, db)
    db.commit()
    db.refresh(historico)

    return _serializar_historico(historico)


@router.delete("/{chamado_id}/historico/{historico_id}")
async def deletar_historico(
    chamado_id: int,
    historico_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    historico = db.query(HistoricoChamado).filter(
        HistoricoChamado.id == historico_id,
        HistoricoChamado.chamado_id == chamado_id
    ).first()
    if not historico:
        raise HTTPException(status_code=404, detail="Histórico não encontrado")

    db.delete(historico)
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    recalcular_chamado(chamado, db)
    db.commit()
    return {"mensagem": "Histórico deletado com sucesso"}


# ============================================================
# FASE 2 - CICLO ATRIBUIR / PUXAR / TRANSFERIR / DEVOLVER
# ============================================================

class AtribuirInput(BaseModel):
    tecnico_id: int


class TransferirInput(BaseModel):
    tecnico_id: int
    motivo: Optional[str] = None


class DevolverInput(BaseModel):
    motivo: str


def _eh_admin(usuario: Usuario) -> bool:
    return (
        getattr(usuario, "tipo_usuario", None) == "admin"
        or getattr(usuario, "is_admin", False)
    )


def _eh_tecnico(usuario: Usuario) -> bool:
    return getattr(usuario, "tipo_usuario", None) == "tecnico"


def _registrar_transferencia(db, chamado_id, de_id, para_id, motivo):
    """Grava auditoria."""
    reg = ChamadoTransferencia(
        chamado_id=chamado_id,
        de_usuario_id=de_id,
        para_usuario_id=para_id,
        motivo=motivo,
    )
    db.add(reg)


# ---------- ATRIBUIR (só admin) ----------

@router.post("/{chamado_id}/atribuir")
async def atribuir_chamado(
    chamado_id: int,
    dados: AtribuirInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Admin atribui chamado aberto a um técnico."""
    if not _eh_admin(usuario):
        raise HTTPException(status_code=403, detail="Apenas admins podem atribuir chamados")

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.status == "finalizado":
        raise HTTPException(status_code=400, detail="Chamado já finalizado não pode ser atribuído")

    tecnico = db.query(Usuario).filter(
        Usuario.id == dados.tecnico_id,
        Usuario.tipo_usuario == "tecnico",
        Usuario.ativo == True,
    ).first()
    if not tecnico:
        raise HTTPException(status_code=400, detail="Técnico não encontrado ou inativo")

    de_id = chamado.tecnico_id  # Pode ser None
    chamado.tecnico_id = tecnico.id
    # Se estava aberto, vira atribuido. Se já estava em_atendimento, mantém
    if chamado.status == "aberto":
        chamado.status = "atribuido"
    chamado.motivo_devolucao = None

    _registrar_transferencia(db, chamado.id, de_id, tecnico.id,
                             f"Atribuído pelo admin {usuario.nome}")

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


# ---------- PUXAR (técnico elegível ou admin) ----------

@router.post("/{chamado_id}/puxar")
async def puxar_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Técnico elegível puxa um chamado da fila aberta.
    Vira 'atribuido' direto pra ele (sem aprovação).
    """
    if not (_eh_admin(usuario) or _eh_tecnico(usuario)):
        raise HTTPException(status_code=403, detail="Só técnicos/admin podem puxar chamados")

    # Técnico precisa ser elegível
    if _eh_tecnico(usuario) and not getattr(usuario, "pode_ver_fila_aberta", False):
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para puxar chamados da fila aberta",
        )

    if _eh_tecnico(usuario) and not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.status != "aberto" or chamado.tecnico_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Este chamado não está disponível na fila aberta (pode já ter sido atribuído)",
        )

    chamado.tecnico_id = usuario.id
    chamado.status = "atribuido"
    chamado.motivo_devolucao = None

    _registrar_transferencia(db, chamado.id, None, usuario.id,
                             f"Puxado pelo técnico {usuario.nome}")

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


# ---------- TRANSFERIR (admin ou técnico responsável) ----------

@router.post("/{chamado_id}/transferir")
async def transferir_chamado(
    chamado_id: int,
    dados: TransferirInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Transfere chamado pra outro técnico (qualquer ativo, independente de flag).
    - Admin: pode transferir qualquer chamado
    - Técnico: só pode transferir os que são dele
    """
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.status == "finalizado":
        raise HTTPException(status_code=400, detail="Chamado finalizado não pode ser transferido")

    if not _eh_admin(usuario):
        if not _eh_tecnico(usuario):
            raise HTTPException(status_code=403, detail="Sem permissão para transferir")
        if chamado.tecnico_id != usuario.id:
            raise HTTPException(
                status_code=403,
                detail="Você só pode transferir chamados que estão atribuídos a você",
            )

    # Destino precisa ser técnico ativo
    destino = db.query(Usuario).filter(
        Usuario.id == dados.tecnico_id,
        Usuario.tipo_usuario == "tecnico",
        Usuario.ativo == True,
    ).first()
    if not destino:
        raise HTTPException(status_code=400, detail="Técnico destino não encontrado ou inativo")

    if destino.id == chamado.tecnico_id:
        raise HTTPException(status_code=400, detail="O chamado já está com esse técnico")

    de_id = chamado.tecnico_id
    chamado.tecnico_id = destino.id
    # Status: se estava em_atendimento, vira atribuido pro novo técnico
    if chamado.status in ("em_atendimento", "aberto"):
        chamado.status = "atribuido"
    chamado.motivo_devolucao = None

    motivo_txt = (dados.motivo or "").strip() or f"Transferido por {usuario.nome}"
    _registrar_transferencia(db, chamado.id, de_id, destino.id, motivo_txt)

    # Histórico automático pra auditoria (sem tempo)
    hist_txt = f"🔄 Chamado transferido para {destino.nome}. Motivo: {motivo_txt}"
    db.add(HistoricoChamado(
        chamado_id=chamado.id,
        usuario_id=usuario.id,
        descricao=hist_txt,
        tempo_minutos=0,
    ))

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


# ---------- DEVOLVER (admin ou técnico responsável) ----------

@router.post("/{chamado_id}/devolver")
async def devolver_chamado(
    chamado_id: int,
    dados: DevolverInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Devolve chamado pra fila aberta (status='aberto', tecnico_id=null).
    Motivo é obrigatório.
    - Admin: pode devolver qualquer chamado
    - Técnico: só pode devolver os que são dele
    """
    motivo = (dados.motivo or "").strip()
    if not motivo:
        raise HTTPException(status_code=400, detail="Motivo da devolução é obrigatório")

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.status == "finalizado":
        raise HTTPException(status_code=400, detail="Chamado finalizado não pode ser devolvido")

    if chamado.tecnico_id is None:
        raise HTTPException(status_code=400, detail="Chamado não tem técnico atribuído")

    if not _eh_admin(usuario):
        if not _eh_tecnico(usuario):
            raise HTTPException(status_code=403, detail="Sem permissão para devolver")
        if chamado.tecnico_id != usuario.id:
            raise HTTPException(
                status_code=403,
                detail="Você só pode devolver chamados atribuídos a você",
            )

    de_id = chamado.tecnico_id
    chamado.tecnico_id = None
    chamado.status = "aberto"
    chamado.motivo_devolucao = motivo

    _registrar_transferencia(db, chamado.id, de_id, None, motivo)

    # Histórico automático pra auditoria
    db.add(HistoricoChamado(
        chamado_id=chamado.id,
        usuario_id=usuario.id,
        descricao=f"🔙 Chamado devolvido à fila. Motivo: {motivo}",
        tempo_minutos=0,
    ))

    db.commit()
    db.refresh(chamado)
    return serializar_chamado(chamado, usuario)


# ---------- HISTÓRICO DE TRANSFERÊNCIAS ----------

@router.get("/{chamado_id}/transferencias")
async def listar_transferencias(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Lista histórico de transferências de um chamado (admin ou quem está atendendo)."""
    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if not _eh_admin(usuario):
        if chamado.tecnico_id != usuario.id and chamado.solicitante_id != usuario.id:
            raise HTTPException(status_code=403, detail="Sem permissão para ver histórico")

    transfs = db.query(ChamadoTransferencia)\
        .filter(ChamadoTransferencia.chamado_id == chamado_id)\
        .order_by(ChamadoTransferencia.criado_em.desc()).all()

    return [
        {
            "id": t.id,
            "de_usuario_id": t.de_usuario_id,
            "de_usuario_nome": t.de_usuario.nome if t.de_usuario else None,
            "para_usuario_id": t.para_usuario_id,
            "para_usuario_nome": t.para_usuario.nome if t.para_usuario else None,
            "motivo": t.motivo,
            "criado_em": t.criado_em.isoformat() if t.criado_em else None,
        }
        for t in transfs
    ]
