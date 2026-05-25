# services/comissao_service.py
#
# Regras (Fase 4):
# - Competência = data_termino do chamado (mês de finalização)
# - Só entram chamados com status='finalizado' e valor_total > 0
# - Para cada chamado, peso de cada técnico = tempo_minutos_dele / total_tecnicos
#   (só conta histórico de usuários tipo_usuario='tecnico'; admin não entra)
# - Comissão do técnico num chamado = valor_total × peso × (percentual/100)
# - Percentual padrão vem do perfil (comissao_percentual), editável no fechamento
# - Arredondamento: trabalhar com precisão e arredondar só no final com round(x, 2)

from datetime import datetime
import calendar
import io

from sqlalchemy.orm import Session

from models.chamado import Chamado, HistoricoChamado
from models.user import Usuario
from models.fechamento_comissao import FechamentoComissao


# =========================================================
# CÁLCULO
# =========================================================

def _peso_tecnicos_chamado(db: Session, chamado: Chamado) -> dict:
    """
    Retorna {tecnico_id: peso_float} do chamado.
    Considera apenas históricos cujo usuario_id é de um TÉCNICO.
    """
    hists = db.query(HistoricoChamado, Usuario).join(
        Usuario, Usuario.id == HistoricoChamado.usuario_id
    ).filter(
        HistoricoChamado.chamado_id == chamado.id,
        Usuario.tipo_usuario == "tecnico",
        HistoricoChamado.tempo_minutos > 0,
    ).all()

    if not hists:
        return {}

    total = sum(h.tempo_minutos for h, _ in hists) or 0
    if total <= 0:
        return {}

    # Soma por técnico
    por_tecnico = {}
    for h, u in hists:
        por_tecnico[u.id] = por_tecnico.get(u.id, 0) + int(h.tempo_minutos or 0)

    return {tid: (minutos / total) for tid, minutos in por_tecnico.items()}


def _chamados_da_competencia(db: Session, ano: int, mes: int):
    """
    Chamados finalizados com valor > 0 cuja data_termino cai em ano/mes.
    """
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = datetime(ano, mes, 1, 0, 0, 0)
    fim = datetime(ano, mes, ultimo_dia, 23, 59, 59)

    return db.query(Chamado).filter(
        Chamado.status == "finalizado",
        Chamado.valor_total > 0,
        Chamado.data_termino >= inicio,
        Chamado.data_termino <= fim,
    ).order_by(Chamado.data_termino).all()


def calcular_previa(db: Session, ano: int, mes: int) -> dict:
    """
    Calcula preview da comissão do mês.

    Retorna:
        {
          "ano": 2026, "mes": 4, "fechado": False,
          "total_chamados": N,
          "total_valor_base": R$X,
          "total_comissao_preview": R$Y,
          "fechado_em": None,
          "tecnicos": [
            {tecnico_id, nome, email, percentual_padrao, percentual_aplicado,
             quantidade_chamados, valor_base_comissao, valor_comissao,
             chamados: [{numero, cliente, tipo_servico, valor_total, peso, parte, comissao}]
            }
          ]
        }
    """
    # Primeiro tenta recuperar fechamento, se já existir
    fechamento = db.query(FechamentoComissao).filter(
        FechamentoComissao.ano == ano,
        FechamentoComissao.mes == mes,
    ).all()

    ja_fechado = len(fechamento) > 0
    # Mapa de percentuais aplicados (se fechado)
    map_percentuais_fixos = {f.tecnico_id: f.percentual_aplicado for f in fechamento}

    chamados = _chamados_da_competencia(db, ano, mes)

    # Acumuladores por técnico
    tecnicos_map = {}  # tecnico_id -> dados

    for c in chamados:
        pesos = _peso_tecnicos_chamado(db, c)
        if not pesos:
            continue

        for tid, peso in pesos.items():
            parte = float(c.valor_total) * peso  # valor base dessa parte do chamado
            if tid not in tecnicos_map:
                tecnicos_map[tid] = {
                    "chamados": [],
                    "valor_base": 0.0,
                }
            tecnicos_map[tid]["chamados"].append({
                "chamado_id": c.id,
                "numero": c.numero,
                "cliente_nome": c.cliente.nome if c.cliente else "—",
                "tipo_servico": c.tipo_servico,
                "servico_nome": (
                    c.servico.nome if c.servico else (c.servico_tecnico or "")
                ),
                "data_termino": c.data_termino.isoformat() if c.data_termino else None,
                "valor_total": float(c.valor_total),
                "peso": peso,
                "parte": parte,
            })
            tecnicos_map[tid]["valor_base"] += parte

    # Carrega técnicos do banco (mesmo os desativados — dado histórico)
    ids = list(tecnicos_map.keys())
    if ids:
        tecnicos_db = db.query(Usuario).filter(Usuario.id.in_(ids)).all()
        tecnicos_db_map = {t.id: t for t in tecnicos_db}
    else:
        tecnicos_db_map = {}

    tecnicos_saida = []
    total_comissao = 0.0
    total_base = 0.0

    for tid, acc in tecnicos_map.items():
        u = tecnicos_db_map.get(tid)
        perc_padrao = float(u.comissao_percentual) if u else 0.0
        perc_aplicado = map_percentuais_fixos.get(tid, perc_padrao)

        # Comissão = soma(parte * perc/100) por chamado — mas como perc é fixo
        # por técnico no fechamento, dá no mesmo que valor_base * perc/100.
        # Calculamos per-chamado pra exibir na auditoria.
        comissao_total = 0.0
        for ch in acc["chamados"]:
            ch["percentual_aplicado"] = perc_aplicado
            ch["comissao"] = round(ch["parte"] * perc_aplicado / 100, 2)
            comissao_total += ch["parte"] * perc_aplicado / 100

        valor_base = acc["valor_base"]
        total_base += valor_base
        total_comissao += comissao_total

        tecnicos_saida.append({
            "tecnico_id": tid,
            "nome": u.nome if u else f"(técnico #{tid} removido)",
            "email": u.email if u else "",
            "ativo": bool(u.ativo) if u else False,
            "percentual_padrao": perc_padrao,
            "percentual_aplicado": perc_aplicado,
            "quantidade_chamados": len(acc["chamados"]),
            "valor_base_comissao": round(valor_base, 2),
            "valor_comissao": round(comissao_total, 2),
            "chamados": [
                {**ch, "parte": round(ch["parte"], 2), "peso": round(ch["peso"], 4)}
                for ch in acc["chamados"]
            ],
        })

    # Ordena por comissão desc
    tecnicos_saida.sort(key=lambda x: x["valor_comissao"], reverse=True)

    fechado_em = None
    if ja_fechado and fechamento:
        fechado_em = min(f.fechado_em for f in fechamento if f.fechado_em).isoformat()

    return {
        "ano": ano,
        "mes": mes,
        "fechado": ja_fechado,
        "fechado_em": fechado_em,
        "total_chamados": len(chamados),
        "total_valor_base": round(total_base, 2),
        "total_comissao": round(total_comissao, 2),
        "tecnicos": tecnicos_saida,
    }


# =========================================================
# FECHAMENTO
# =========================================================

def fechar_mes(
    db: Session,
    ano: int,
    mes: int,
    percentuais_customizados: dict,
    admin_id: int,
    observacoes_por_tecnico: dict = None,
) -> dict:
    """
    Fecha o mês, salvando uma linha por técnico em fechamento_comissao.

    percentuais_customizados: {tecnico_id: percentual_float}
      Se um técnico não aparecer no dict, usa percentual_padrão dele.
    """
    # Se já foi fechado, recusa
    existe = db.query(FechamentoComissao).filter(
        FechamentoComissao.ano == ano,
        FechamentoComissao.mes == mes,
    ).first()
    if existe:
        raise ValueError("Este mês já foi fechado. Reabra antes de refechar.")

    observacoes_por_tecnico = observacoes_por_tecnico or {}

    # Recalcula do zero (sem depender do preview do frontend)
    previa = calcular_previa(db, ano, mes)

    for tec in previa["tecnicos"]:
        tid = tec["tecnico_id"]
        perc = float(percentuais_customizados.get(str(tid), percentuais_customizados.get(tid, tec["percentual_padrao"])))
        if perc < 0 or perc > 100:
            raise ValueError(f"Percentual inválido para técnico {tid}: {perc}")

        # Recalcula comissão com perc customizado
        valor_comissao = round(tec["valor_base_comissao"] * perc / 100, 2)

        reg = FechamentoComissao(
            tecnico_id=tid,
            ano=ano,
            mes=mes,
            percentual_aplicado=perc,
            valor_base=tec["valor_base_comissao"],
            valor_comissao=valor_comissao,
            quantidade_chamados=tec["quantidade_chamados"],
            observacoes=observacoes_por_tecnico.get(str(tid)) or observacoes_por_tecnico.get(tid),
            fechado_por_id=admin_id,
            fechado_em=datetime.now(),
        )
        db.add(reg)

    db.commit()

    # Retorna a previa atualizada (agora com fechado=True)
    return calcular_previa(db, ano, mes)


def reabrir_mes(db: Session, ano: int, mes: int) -> int:
    """Remove fechamentos do mês. Retorna quantos registros foram removidos."""
    rows = db.query(FechamentoComissao).filter(
        FechamentoComissao.ano == ano,
        FechamentoComissao.mes == mes,
    ).all()
    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return n


# =========================================================
# PDF
# =========================================================

def gerar_pdf_individual(db: Session, tecnico_id: int, ano: int, mes: int) -> bytes:
    """Gera PDF individual do técnico. Retorna bytes do PDF."""
    previa = calcular_previa(db, ano, mes)

    tec = next((t for t in previa["tecnicos"] if t["tecnico_id"] == tecnico_id), None)
    if not tec:
        raise ValueError(f"Técnico {tecnico_id} não tem comissão em {mes:02d}/{ano}")

    return _gerar_pdf_bytes(previa, [tec], titulo_extra=f"Técnico: {tec['nome']}")


def gerar_pdf_consolidado(db: Session, ano: int, mes: int) -> bytes:
    """Gera PDF consolidado (todos os técnicos). Retorna bytes do PDF."""
    previa = calcular_previa(db, ano, mes)
    if not previa["tecnicos"]:
        raise ValueError(f"Não há técnicos com comissão em {mes:02d}/{ano}")
    return _gerar_pdf_bytes(previa, previa["tecnicos"], titulo_extra="Consolidado")


# ---------- Helpers de formatação compartilhados ----------

def _fmt_moeda(v):
    v = float(v or 0)
    texto = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"

def _fmt_pct(v):
    return f"{float(v or 0):.1f}%".replace(".", ",")

def _nome_mes(mes):
    meses = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    return meses[mes] if 1 <= mes <= 12 else str(mes)


def _gerar_pdf_bytes(previa: dict, tecnicos: list, titulo_extra: str = "") -> bytes:
    """Gera PDF no padrão visual do faturamento (cores e estrutura)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

    # Cores do padrão do sistema
    COR_PRIMARIA = colors.HexColor("#1F3A5F")
    COR_SECUNDARIA = colors.HexColor("#EAF1F8")
    COR_TEXTO = colors.HexColor("#243447")
    COR_MUTED = colors.HexColor("#5B7083")
    COR_BORDA = colors.HexColor("#D7DEE7")
    COR_ZEBRA = colors.HexColor("#F7F9FC")
    COR_VERDE = colors.HexColor("#27ae60")
    COR_SUBTOTAL_FUNDO = colors.HexColor("#eef2f7")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=18*mm,
    )

    styles = getSampleStyleSheet()
    st_titulo = ParagraphStyle(
        "titulo", parent=styles["Heading1"], fontSize=16, textColor=COR_PRIMARIA,
        alignment=TA_LEFT, spaceAfter=2
    )
    st_sub = ParagraphStyle(
        "sub", parent=styles["Normal"], fontSize=10, textColor=COR_MUTED,
        alignment=TA_LEFT, spaceAfter=10
    )
    st_h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=12, textColor=COR_PRIMARIA,
        spaceBefore=14, spaceAfter=6
    )
    st_p = ParagraphStyle(
        "p", parent=styles["Normal"], fontSize=9, textColor=COR_TEXTO
    )
    st_p_right = ParagraphStyle(
        "pr", parent=styles["Normal"], fontSize=10, textColor=COR_TEXTO, alignment=TA_RIGHT
    )
    st_center = ParagraphStyle(
        "c", parent=styles["Normal"], fontSize=9, textColor=COR_MUTED, alignment=TA_CENTER
    )

    story = []

    competencia_txt = f"{_nome_mes(previa['mes']).capitalize()} de {previa['ano']}"

    # ======== HEADER ========
    story.append(Paragraph("RNS TECH — Relatório de Comissão", st_titulo))
    sub = f"Competência: <b>{competencia_txt}</b>"
    if titulo_extra:
        sub += f"  •  {titulo_extra}"
    if previa.get("fechado"):
        sub += "  •  <b>Fechado</b>"
    else:
        sub += "  •  <i>Prévia (não fechado)</i>"
    story.append(Paragraph(sub, st_sub))

    # ======== RESUMO GERAL ========
    story.append(Paragraph("Resumo", st_h2))
    total_comissao = sum(t["valor_comissao"] for t in tecnicos)
    total_base = sum(t["valor_base_comissao"] for t in tecnicos)
    total_chamados = sum(t["quantidade_chamados"] for t in tecnicos)

    resumo_data = [
        ["Técnicos no relatório", "Chamados", "Base (R$)", "Comissão total (R$)"],
        [str(len(tecnicos)), str(total_chamados), _fmt_moeda(total_base), _fmt_moeda(total_comissao)],
    ]
    t_resumo = Table(resumo_data, colWidths=[45*mm, 30*mm, 45*mm, 45*mm])
    t_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, COR_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TEXTCOLOR", (3, 1), (3, 1), COR_VERDE),
        ("FONTNAME", (3, 1), (3, 1), "Helvetica-Bold"),
    ]))
    story.append(t_resumo)

    # Se mais de 1 técnico, adiciona tabela consolidada antes do detalhamento
    if len(tecnicos) > 1:
        story.append(Paragraph("Por técnico", st_h2))
        cons_data = [["Técnico", "Chamados", "Base", "%", "Comissão"]]
        for t in tecnicos:
            cons_data.append([
                t["nome"],
                str(t["quantidade_chamados"]),
                _fmt_moeda(t["valor_base_comissao"]),
                _fmt_pct(t["percentual_aplicado"]),
                _fmt_moeda(t["valor_comissao"]),
            ])
        cons_data.append([
            "TOTAL", str(total_chamados), _fmt_moeda(total_base), "", _fmt_moeda(total_comissao)
        ])

        t_cons = Table(cons_data, colWidths=[60*mm, 22*mm, 30*mm, 18*mm, 35*mm])
        t_cons.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, COR_BORDA),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, COR_ZEBRA]),
            ("BACKGROUND", (0, -1), (-1, -1), COR_SUBTOTAL_FUNDO),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (-1, 1), (-1, -1), COR_VERDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_cons)

    # ======== DETALHAMENTO POR TÉCNICO ========
    for idx, tec in enumerate(tecnicos):
        story.append(PageBreak() if idx > 0 or len(tecnicos) > 1 else Spacer(1, 10))
        story.append(Paragraph(f"Detalhamento — {tec['nome']}", st_h2))

        # Dados do técnico
        story.append(Paragraph(
            f"<b>Email:</b> {tec['email'] or '—'}<br/>"
            f"<b>Percentual aplicado:</b> {_fmt_pct(tec['percentual_aplicado'])}"
            f" (padrão: {_fmt_pct(tec['percentual_padrao'])})<br/>"
            f"<b>Chamados:</b> {tec['quantidade_chamados']}  &nbsp;&nbsp;"
            f"<b>Base:</b> {_fmt_moeda(tec['valor_base_comissao'])}  &nbsp;&nbsp;"
            f"<b>Comissão:</b> <font color='{COR_VERDE.hexval()}'><b>{_fmt_moeda(tec['valor_comissao'])}</b></font>",
            st_p
        ))
        story.append(Spacer(1, 8))

        # Tabela de chamados
        cham_data = [["Nº", "Cliente", "Serviço", "Valor Total", "Sua parte", "%", "Comissão"]]
        for ch in tec["chamados"]:
            cham_data.append([
                ch["numero"],
                (ch["cliente_nome"] or "—")[:25],
                (ch["servico_nome"] or ("Tempo" if ch["tipo_servico"] == "suporte_usuario" else "Técnico"))[:25],
                _fmt_moeda(ch["valor_total"]),
                _fmt_moeda(ch["parte"]),
                _fmt_pct(ch["percentual_aplicado"]),
                _fmt_moeda(ch["comissao"]),
            ])
        cham_data.append([
            "", "", "TOTAL",
            "", _fmt_moeda(tec["valor_base_comissao"]),
            "", _fmt_moeda(tec["valor_comissao"]),
        ])

        t_cham = Table(cham_data, colWidths=[20*mm, 38*mm, 38*mm, 22*mm, 22*mm, 14*mm, 24*mm])
        t_cham.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (5, 0), (5, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.4, COR_BORDA),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, COR_ZEBRA]),
            ("BACKGROUND", (0, -1), (-1, -1), COR_SUBTOTAL_FUNDO),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (-1, 1), (-1, -1), COR_VERDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_cham)

        # Assinatura
        story.append(Spacer(1, 20))
        assin = [
            ["", ""],
            ["_" * 40, "_" * 40],
            [f"{tec['nome']}", "RNS TECH"],
            ["Técnico", "Responsável financeiro"],
        ]
        t_assin = Table(assin, colWidths=[80*mm, 80*mm])
        t_assin.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TEXTCOLOR", (0, 0), (-1, -1), COR_MUTED),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t_assin)

    # ======== FOOTER (em cada página) ========
    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(COR_MUTED)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas.drawString(15*mm, 10*mm, f"RNS TECH — Relatório gerado em {agora}")
        canvas.drawRightString(195*mm, 10*mm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()
