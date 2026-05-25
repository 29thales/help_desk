from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from collections import defaultdict

from database import get_db
from auth import obter_usuario_atual
from models.chamado import Chamado, HistoricoChamado
from models.cliente import Cliente
from models.user import Usuario

router = APIRouter()


# =================== HELPERS ===================

def _formatar_minutos(minutos):
    """Formata minutos para '5h 30min', '45min', etc."""
    minutos = int(minutos or 0)
    if minutos <= 0:
        return "0min"
    if minutos < 60:
        return f"{minutos}min"
    horas = minutos // 60
    mins = minutos % 60
    if mins == 0:
        return f"{horas}h"
    return f"{horas}h {mins}min"


def _primeiro_dia_mes(ano, mes):
    return datetime(ano, mes, 1)


def _primeiro_dia_proximo_mes(ano, mes):
    if mes == 12:
        return datetime(ano + 1, 1, 1)
    return datetime(ano, mes + 1, 1)


def _percentual_evolucao(atual, anterior):
    """Retorna percentual e direção comparando atual com anterior."""
    atual = float(atual or 0)
    anterior = float(anterior or 0)

    if anterior == 0 and atual == 0:
        return {"percentual": 0, "direcao": "neutro"}
    if anterior == 0:
        return {"percentual": 100, "direcao": "sobe"}

    diff = ((atual - anterior) / anterior) * 100

    if abs(diff) < 1:
        direcao = "neutro"
    elif diff > 0:
        direcao = "sobe"
    else:
        direcao = "desce"

    return {"percentual": round(abs(diff)), "direcao": direcao}


def _data_referencia(chamado):
    """Retorna a data do chamado para cálculos (termino ou criado_em)."""
    return chamado.data_termino or chamado.criado_em


def _chamados_do_mes(db, ano, mes):
    """Chamados finalizados dentro de um mês específico."""
    inicio = _primeiro_dia_mes(ano, mes)
    fim = _primeiro_dia_proximo_mes(ano, mes)

    return db.query(Chamado).filter(
        Chamado.status == "finalizado",
        func.coalesce(Chamado.data_termino, Chamado.criado_em) >= inicio,
        func.coalesce(Chamado.data_termino, Chamado.criado_em) < fim
    ).all()


# =================== ROTA PRINCIPAL ===================

@router.get("/admin")
def obter_dashboard_admin(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Retorna todos os dados consolidados para o dashboard do administrador.
    """
    agora = datetime.now()
    ano_atual = agora.year
    mes_atual = agora.month

    # ============ SEÇÃO 1: PRECISA DE ATENÇÃO ============

    todos_chamados = db.query(Chamado).all()

    limite_atrasado = agora - timedelta(days=3)

    chamados_atrasados = sum(
        1 for c in todos_chamados
        if c.status == "aberto" and c.criado_em and c.criado_em < limite_atrasado
    )
    chamados_abertos = sum(1 for c in todos_chamados if c.status == "aberto")
    chamados_em_atendimento = sum(1 for c in todos_chamados if c.status == "em_atendimento")
    chamados_prio_alta = sum(
        1 for c in todos_chamados
        if c.status in ("aberto", "em_atendimento") and c.prioridade == "alta"
    )

    # ============ SEÇÃO 2: ESTE MÊS ============

    chamados_mes = _chamados_do_mes(db, ano_atual, mes_atual)

    # Mês anterior para comparação
    if mes_atual == 1:
        ano_ant, mes_ant = ano_atual - 1, 12
    else:
        ano_ant, mes_ant = ano_atual, mes_atual - 1

    chamados_mes_ant = _chamados_do_mes(db, ano_ant, mes_ant)

    # Totais do mês atual
    qtd_finalizados = len(chamados_mes)

    total_minutos_mes = sum(
        c.tempo_gasto_minutos or 0 for c in chamados_mes
        if c.tipo_servico == "suporte_usuario"
    )
    total_unidades_mes = sum(
        c.tempo_gasto_minutos or 0 for c in chamados_mes
        if c.tipo_servico == "suporte_tecnico"
    )
    total_faturado_mes = sum(float(c.valor_total or 0) for c in chamados_mes)

    # Totais do mês anterior (para evolução)
    qtd_finalizados_ant = len(chamados_mes_ant)
    total_minutos_ant = sum(
        c.tempo_gasto_minutos or 0 for c in chamados_mes_ant
        if c.tipo_servico == "suporte_usuario"
    )
    total_unidades_ant = sum(
        c.tempo_gasto_minutos or 0 for c in chamados_mes_ant
        if c.tipo_servico == "suporte_tecnico"
    )
    total_faturado_ant = sum(float(c.valor_total or 0) for c in chamados_mes_ant)

    # ============ SEÇÃO 3: GRÁFICOS ============

    # Faturamento últimos 6 meses
    faturamento_6m = []
    nomes_meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                   "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    for i in range(5, -1, -1):
        # Calcula o mês subtraindo i meses do atual
        total_meses = (ano_atual * 12 + mes_atual - 1) - i
        ano_ref = total_meses // 12
        mes_ref = (total_meses % 12) + 1

        chamados_ref = _chamados_do_mes(db, ano_ref, mes_ref)
        valor = sum(float(c.valor_total or 0) for c in chamados_ref)

        faturamento_6m.append({
            "label": f"{nomes_meses[mes_ref - 1]}/{str(ano_ref)[-2:]}",
            "valor": round(valor, 2)
        })

    # Distribuição de status (todos os chamados)
    status_count = defaultdict(int)
    for c in todos_chamados:
        status_count[c.status] += 1

    distribuicao_status = [
        {"label": "Finalizados", "valor": status_count.get("finalizado", 0)},
        {"label": "Em Atendimento", "valor": status_count.get("em_atendimento", 0)},
        {"label": "Abertos", "valor": status_count.get("aberto", 0)},
        {"label": "Cancelados", "valor": status_count.get("cancelado", 0)},
    ]

    # ============ SEÇÃO 4: RANKINGS ============

    # Top clientes do mês (por faturamento)
    por_cliente = defaultdict(lambda: {"chamados": 0, "valor": 0.0, "nome": None, "empresa": None})

    for c in chamados_mes:
        if c.cliente_id is None:
            continue
        por_cliente[c.cliente_id]["chamados"] += 1
        por_cliente[c.cliente_id]["valor"] += float(c.valor_total or 0)

    # Buscar dados dos clientes
    ids_clientes = list(por_cliente.keys())
    if ids_clientes:
        clientes_info = db.query(Cliente).filter(Cliente.id.in_(ids_clientes)).all()
        for cli in clientes_info:
            por_cliente[cli.id]["nome"] = cli.nome
            por_cliente[cli.id]["empresa"] = cli.empresa

    top_clientes = sorted(
        [
            {
                "cliente_id": cid,
                "nome": dados["nome"] or "Sem nome",
                "empresa": dados["empresa"] or "",
                "chamados": dados["chamados"],
                "valor": round(dados["valor"], 2)
            }
            for cid, dados in por_cliente.items()
        ],
        key=lambda x: x["valor"],
        reverse=True
    )[:5]

    # Valor máximo para calcular barras de progresso
    valor_max_cliente = max((t["valor"] for t in top_clientes), default=0)
    for t in top_clientes:
        t["percentual_barra"] = round((t["valor"] / valor_max_cliente) * 100) if valor_max_cliente > 0 else 0

    # Top tipos de serviço do mês
    SERVICOS_TECNICOS_NOMES = {
        "formatacao_notebook": "Formatação de Notebook",
        "formatacao_desktop": "Formatação de Desktop",
        "troca_hd_ssd": "Troca de HD/SSD",
        "limpeza_interna": "Limpeza Interna",
        "instalacao_so": "Instalação de Sistema Operacional",
        "backup_dados": "Backup de Dados",
        "outro": "Outro Serviço Técnico",
    }

    por_servico = defaultdict(lambda: {"chamados": 0, "minutos": 0, "unidades": 0})

    for c in chamados_mes:
        if c.tipo_servico == "suporte_usuario":
            chave = "suporte_usuario"
            nome = "Suporte por Hora"
            por_servico[chave]["minutos"] += c.tempo_gasto_minutos or 0
        else:
            chave = c.servico_tecnico or "outro"
            nome = SERVICOS_TECNICOS_NOMES.get(chave, "Outro Serviço Técnico")
            por_servico[chave]["unidades"] += c.tempo_gasto_minutos or 0

        por_servico[chave]["chamados"] += 1
        por_servico[chave]["nome"] = nome

    total_chamados_mes_servicos = sum(d["chamados"] for d in por_servico.values())

    top_servicos = sorted(
        [
            {
                "nome": dados["nome"],
                "chamados": dados["chamados"],
                "minutos": dados["minutos"],
                "minutos_formatado": _formatar_minutos(dados["minutos"]),
                "unidades": dados["unidades"],
                "percentual": round((dados["chamados"] / total_chamados_mes_servicos) * 100)
                if total_chamados_mes_servicos > 0 else 0
            }
            for dados in por_servico.values()
        ],
        key=lambda x: x["chamados"],
        reverse=True
    )[:5]

    # Valor máximo para barras
    max_pct_servico = max((s["percentual"] for s in top_servicos), default=0)
    for s in top_servicos:
        s["percentual_barra"] = round((s["percentual"] / max_pct_servico) * 100) if max_pct_servico > 0 else 0

    # ============ SEÇÃO 5: LISTAS RECENTES ============

    # Últimos 5 chamados
    ultimos_chamados_query = db.query(Chamado).order_by(Chamado.criado_em.desc()).limit(5).all()
    clientes_dict = {cli.id: cli for cli in db.query(Cliente).all()}

    ultimos_chamados = []
    for c in ultimos_chamados_query:
        cli = clientes_dict.get(c.cliente_id) if c.cliente_id else None
        ultimos_chamados.append({
            "numero": c.numero,
            "cliente_nome": cli.nome if cli else "-",
            "empresa": cli.empresa if cli and cli.empresa else "-",
            "prioridade": c.prioridade,
            "status": c.status,
        })

    # Últimos 5 clientes
    ultimos_clientes_query = db.query(Cliente).order_by(Cliente.criado_em.desc()).limit(5).all()

    ultimos_clientes = [
        {
            "nome": cli.nome,
            "empresa": cli.empresa or "-",
            "criado_em": cli.criado_em.strftime("%d/%m/%Y") if cli.criado_em else "-"
        }
        for cli in ultimos_clientes_query
    ]

    # ============ MONTA RESPOSTA ============

    return {
        "usuario_nome": usuario.nome,
        "atencao": {
            "atrasados": chamados_atrasados,
            "abertos": chamados_abertos,
            "em_atendimento": chamados_em_atendimento,
            "prioridade_alta": chamados_prio_alta,
        },
        "mes_atual": {
            "ano": ano_atual,
            "mes": mes_atual,
            "nome_mes": nomes_meses[mes_atual - 1],
            "chamados_finalizados": qtd_finalizados,
            "total_minutos": total_minutos_mes,
            "total_minutos_formatado": _formatar_minutos(total_minutos_mes),
            "total_unidades": total_unidades_mes,
            "total_faturado": round(total_faturado_mes, 2),
            "evolucao_chamados": _percentual_evolucao(qtd_finalizados, qtd_finalizados_ant),
            "evolucao_minutos": _percentual_evolucao(total_minutos_mes, total_minutos_ant),
            "evolucao_unidades": _percentual_evolucao(total_unidades_mes, total_unidades_ant),
            "evolucao_faturado": _percentual_evolucao(total_faturado_mes, total_faturado_ant),
        },
        "graficos": {
            "faturamento_6m": faturamento_6m,
            "distribuicao_status": distribuicao_status,
        },
        "rankings": {
            "top_clientes": top_clientes,
            "top_servicos": top_servicos,
        },
        "ultimos_chamados": ultimos_chamados,
        "ultimos_clientes": ultimos_clientes,
    }
