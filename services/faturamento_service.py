from datetime import datetime
import tempfile

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.cliente import Cliente
from models.chamado import Chamado


class FaturamentoService:
    EMPRESA_PADRAO = "RNS TECH"

    COR_PRIMARIA = "#1F3A5F"
    COR_SECUNDARIA = "#EAF1F8"
    COR_TEXTO = "#243447"
    COR_MUTED = "#5B7083"
    COR_BORDA = "#D7DEE7"
    COR_ZEBRA = "#F7F9FC"
    COR_VERDE = "#27ae60"
    COR_HIST_FUNDO = "#fafbfd"
    COR_SUBTOTAL_FUNDO = "#eef2f7"

    # ================= FORMATADORES =================

    @staticmethod
    def _formatar_minutos(minutos):
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

    @staticmethod
    def _formatar_moeda(valor):
        valor = float(valor or 0)
        texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {texto}"

    @staticmethod
    def _formatar_data(valor):
        return valor.strftime("%d/%m/%Y") if valor else ""

    @staticmethod
    def _formatar_hora(valor):
        return valor.strftime("%H:%M") if valor else ""

    @staticmethod
    def _formatar_data_hora_atual():
        return datetime.now().strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _formatar_quantidade(valor):
        return f"{int(valor or 0)} un"

    @staticmethod
    def _formatar_resumo(total_minutos, total_unidades):
        partes = []

        if (total_minutos or 0) > 0:
            partes.append(FaturamentoService._formatar_minutos(total_minutos))

        if (total_unidades or 0) > 0:
            partes.append(FaturamentoService._formatar_quantidade(total_unidades))

        return " + ".join(partes) if partes else "0min"

    @staticmethod
    def _humanizar_tipo_servico(tipo_servico):
        mapa = {
            "suporte_usuario": "Suporte por hora",
            "suporte_tecnico": "Serviço por unidade"
        }
        return mapa.get(tipo_servico, (tipo_servico or "").replace("_", " ").title())

    @staticmethod
    def _serializar_historicos(chamado):
        """
        Extrai os históricos de um chamado, ordenados do mais antigo ao mais recente,
        formatados para exibição (data/hora/descrição + tempo).
        """
        hists = list(chamado.historicos or [])

        def chave_ordenacao(h):
            from datetime import datetime as _dt
            if h.data_atendimento:
                return h.data_atendimento
            if h.criado_em:
                return h.criado_em
            return _dt.min

        hists.sort(key=chave_ordenacao)

        resultado = []
        for h in hists:
            data_fmt = "-"
            if h.data_atendimento:
                data_fmt = h.data_atendimento.strftime("%d/%m/%Y")
            elif h.criado_em:
                data_fmt = h.criado_em.strftime("%d/%m/%Y")

            hora_ini = ""
            hora_fim = ""
            if h.hora_inicio:
                hora_ini = h.hora_inicio.strftime('%H:%M')
            if h.hora_termino:
                hora_fim = h.hora_termino.strftime('%H:%M')

            tempo_fmt = ""
            if h.tempo_minutos and h.tempo_minutos > 0:
                if chamado.tipo_servico == "suporte_tecnico":
                    tempo_fmt = f"{h.tempo_minutos} un"
                else:
                    if h.tempo_minutos < 60:
                        tempo_fmt = f"{h.tempo_minutos}min"
                    elif h.tempo_minutos % 60 == 0:
                        tempo_fmt = f"{h.tempo_minutos // 60}h"
                    else:
                        tempo_fmt = f"{h.tempo_minutos // 60}h {h.tempo_minutos % 60}min"

            resultado.append({
                "data": data_fmt,
                "hora_inicio": hora_ini,
                "hora_termino": hora_fim,
                "descricao": (h.descricao or "").strip() or "-",
                "tempo": tempo_fmt
            })

        return resultado

    @staticmethod
    def _gerar_referencia(cliente_id, ano, mes):
        if cliente_id:
            return f"FAT-{ano}{mes:02d}-{int(cliente_id):04d}"
        return f"FAT-{ano}{mes:02d}-GERAL"

    # ================= REGRAS =================

    @staticmethod
    def _eh_servico_por_unidade(chamado):
        return chamado.tipo_servico == "suporte_tecnico"

    # ================= AUXILIARES PDF =================

    @staticmethod
    def _obter_estilos_pdf():
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        base = getSampleStyleSheet()

        return {
            "titulo": ParagraphStyle(
                name="Titulo",
                parent=base["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=colors.HexColor(FaturamentoService.COR_PRIMARIA),
                spaceAfter=0
            ),
            "subtitulo": ParagraphStyle(
                name="Subtitulo",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=colors.HexColor(FaturamentoService.COR_MUTED)
            ),
            "normal": ParagraphStyle(
                name="NormalCustom",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO)
            ),
            "normal_centro": ParagraphStyle(
                name="NormalCentro",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO)
            ),
            "normal_direita": ParagraphStyle(
                name="NormalDireita",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                alignment=TA_RIGHT,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO)
            ),
            "label": ParagraphStyle(
                name="Label",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor(FaturamentoService.COR_MUTED)
            ),
            "box_titulo": ParagraphStyle(
                name="BoxTitulo",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                textColor=colors.HexColor(FaturamentoService.COR_PRIMARIA),
                spaceAfter=4
            ),
            "box_texto": ParagraphStyle(
                name="BoxTexto",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO)
            ),
            "cabecalho_inverso_titulo": ParagraphStyle(
                name="CabecalhoInversoTitulo",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=16,
                leading=20,
                textColor=colors.white
            ),
            "cabecalho_inverso_texto": ParagraphStyle(
                name="CabecalhoInversoTexto",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=colors.white
            ),
            "tabela_head": ParagraphStyle(
                name="TabelaHead",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
                textColor=colors.white
            ),
            "tabela": ParagraphStyle(
                name="Tabela",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO),
                alignment=TA_LEFT
            ),
            "tabela_centro": ParagraphStyle(
                name="TabelaCentro",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO),
                alignment=TA_CENTER
            ),
            "tabela_direita": ParagraphStyle(
                name="TabelaDireita",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor(FaturamentoService.COR_TEXTO),
                alignment=TA_RIGHT
            ),
            # Estilo para descrição do histórico (centralizada)
            "historico_descricao": ParagraphStyle(
                name="HistoricoDescricao",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#3D4A5C"),
                alignment=TA_CENTER
            ),
            # Estilo para data/horário do histórico (muted, centralizado)
            "historico_centro_muted": ParagraphStyle(
                name="HistoricoCentroMuted",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10,
                textColor=colors.HexColor(FaturamentoService.COR_MUTED),
                alignment=TA_CENTER
            ),
            # Label "Subtotal CHM-XXXX:" (alinhado à direita)
            "subtotal_label": ParagraphStyle(
                name="SubtotalLabel",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor(FaturamentoService.COR_PRIMARIA),
                alignment=TA_RIGHT
            ),
            # Valor do subtotal em verde
            "subtotal_valor": ParagraphStyle(
                name="SubtotalValor",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=11,
                textColor=colors.HexColor(FaturamentoService.COR_VERDE),
                alignment=TA_RIGHT
            ),
            "total": ParagraphStyle(
                name="Total",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=15,
                leading=18,
                alignment=TA_RIGHT,
                textColor=colors.HexColor(FaturamentoService.COR_PRIMARIA)
            )
        }

    @staticmethod
    def _p(texto, estilo):
        from reportlab.platypus import Paragraph
        return Paragraph(texto or "", estilo)

    @staticmethod
    def _rodape(canvas, doc, texto_esquerda=""):
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(FaturamentoService.COR_BORDA))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 12 * mm, doc.pagesize[0] - doc.rightMargin, 12 * mm)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor(FaturamentoService.COR_MUTED))
        canvas.drawString(doc.leftMargin, 7 * mm, texto_esquerda or "")
        canvas.drawRightString(
            doc.pagesize[0] - doc.rightMargin,
            7 * mm,
            f"Página {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    # ================= RESUMO =================

    @staticmethod
    def obter_resumo_mensal(db: Session, ano: int, mes: int, cliente_id: int = None):
        competencia = f"{ano}-{mes:02d}"

        chamados = db.query(Chamado).filter(
            Chamado.status == "finalizado",
            Chamado.cliente_id.isnot(None),
            func.strftime("%Y-%m", func.coalesce(Chamado.data_termino, Chamado.criado_em)) == competencia
        ).all()

        if cliente_id:
            chamados = [c for c in chamados if c.cliente_id == cliente_id]

        agrupado = {}

        for c in chamados:
            if c.cliente_id not in agrupado:
                agrupado[c.cliente_id] = []

            agrupado[c.cliente_id].append(c)

        clientes_ids = list(agrupado.keys())
        clientes_map = {}

        if clientes_ids:
            clientes = db.query(Cliente).filter(Cliente.id.in_(clientes_ids)).all()
            clientes_map = {c.id: c for c in clientes}

        resumo = []

        for cid in sorted(
            agrupado.keys(),
            key=lambda x: (
                (clientes_map.get(x).empresa or "").lower() if clientes_map.get(x) else "",
                (clientes_map.get(x).nome or "").lower() if clientes_map.get(x) else ""
            )
        ):
            cliente = clientes_map.get(cid)
            if not cliente:
                continue

            lista = agrupado[cid]

            total_minutos = sum(
                c.tempo_gasto_minutos or 0
                for c in lista
                if c.tipo_servico == "suporte_usuario"
            )

            total_unidades = sum(
                c.tempo_gasto_minutos or 0
                for c in lista
                if c.tipo_servico == "suporte_tecnico"
            )

            total_faturado = sum(float(c.valor_total or 0) for c in lista)

            resumo.append({
                "cliente_id": cid,
                "nome": cliente.nome,
                "empresa": cliente.empresa,
                "quantidade_chamados": len(lista),
                "total_minutos": total_minutos,
                "total_unidades": total_unidades,
                "total_horas": round(total_minutos / 60, 2),
                "total_horas_formatado": FaturamentoService._formatar_resumo(total_minutos, total_unidades),
                "total_faturado": total_faturado
            })

        return resumo

    # ================= DETALHE =================

    @staticmethod
    def obter_detalhe_cliente(db: Session, cliente_id: int, ano: int, mes: int):
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

        competencia = f"{ano}-{mes:02d}"

        chamados = db.query(Chamado).filter(
            Chamado.cliente_id == cliente_id,
            Chamado.status == "finalizado",
            func.strftime("%Y-%m", func.coalesce(Chamado.data_termino, Chamado.criado_em)) == competencia
        ).all()

        chamados = sorted(
            chamados,
            key=lambda c: (
                c.data_termino or c.criado_em or datetime.min,
                c.numero or ""
            )
        )

        total_minutos = sum(
            c.tempo_gasto_minutos or 0
            for c in chamados
            if c.tipo_servico == "suporte_usuario"
        )

        total_unidades = sum(
            c.tempo_gasto_minutos or 0
            for c in chamados
            if c.tipo_servico == "suporte_tecnico"
        )

        total_faturado = sum(float(c.valor_total or 0) for c in chamados)

        chamados_formatados = []

        for c in chamados:
            inicio = c.data_inicio or c.criado_em
            termino = c.data_termino or c.criado_em

            if c.tipo_servico == "suporte_tecnico":
                horas = ""
                unidades = FaturamentoService._formatar_quantidade(c.tempo_gasto_minutos or 0)
            else:
                horas = FaturamentoService._formatar_minutos(c.tempo_gasto_minutos or 0)
                unidades = ""

            chamados_formatados.append({
                "numero": c.numero or "-",
                "titulo": c.titulo or "",
                "tipo_servico": c.tipo_servico,
                "tipo_servico_descricao": FaturamentoService._humanizar_tipo_servico(c.tipo_servico),
                "status": c.status,
                "data_faturamento": FaturamentoService._formatar_data(c.data_termino or c.criado_em),
                "tempo_gasto_minutos": c.tempo_gasto_minutos or 0,
                "data_atendimento": FaturamentoService._formatar_data(inicio),
                "hora_inicio": FaturamentoService._formatar_hora(inicio),
                "hora_termino": FaturamentoService._formatar_hora(termino),
                "descricao_atendimento": c.descricao or c.titulo or "-",
                "horas_atendimento": horas,
                "unidades_atendimento": unidades,
                "valor_total": float(c.valor_total or 0),
                "historicos": FaturamentoService._serializar_historicos(c)
            })

        return {
            "cliente_id": cliente_id,
            "nome": cliente.nome,
            "empresa": cliente.empresa,
            "ano": ano,
            "mes": mes,
            "quantidade_chamados": len(chamados),
            "total_minutos": total_minutos,
            "total_unidades": total_unidades,
            "total_horas": round(total_minutos / 60, 2),
            "total_horas_formatado": FaturamentoService._formatar_resumo(total_minutos, total_unidades),
            "total_faturado": total_faturado,
            "chamados": chamados_formatados
        }

    # ================= PDF GERAL =================

    @staticmethod
    def gerar_pdf_geral(db: Session, ano: int, mes: int, cliente_id: int = None):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer

        styles = FaturamentoService._obter_estilos_pdf()
        resumo = FaturamentoService.obter_resumo_mensal(db, ano, mes, cliente_id)

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

        doc = SimpleDocTemplate(
            temp.name,
            pagesize=landscape(A4),
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=18 * mm
        )

        referencia = FaturamentoService._gerar_referencia(cliente_id, ano, mes)
        emitido_em = FaturamentoService._formatar_data_hora_atual()

        elementos = []

        cabecalho = Table(
            [[
                FaturamentoService._p(
                    f"<b>{FaturamentoService.EMPRESA_PADRAO}</b><br/>"
                    f"<font size='9'>Relatório geral de faturamento mensal</font>",
                    styles["cabecalho_inverso_titulo"]
                ),
                FaturamentoService._p(
                    f"<b>Referência:</b> {referencia}<br/>"
                    f"<b>Competência:</b> {mes:02d}/{ano}<br/>"
                    f"<b>Emitido em:</b> {emitido_em}",
                    styles["normal"]
                )
            ]],
            colWidths=[doc.width * 0.50, doc.width * 0.50]
        )

        cabecalho.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(FaturamentoService.COR_PRIMARIA)),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(FaturamentoService.COR_SECUNDARIA)),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        elementos.append(cabecalho)
        elementos.append(Spacer(1, 8 * mm))

        titulo_secao = "Consolidado por cliente"
        if cliente_id:
            titulo_secao += " (filtro aplicado)"

        elementos.append(FaturamentoService._p(f"<b>{titulo_secao}</b>", styles["box_titulo"]))
        elementos.append(Spacer(1, 2 * mm))

        if not resumo:
            aviso = Table(
                [[FaturamentoService._p(
                    "Nenhum chamado finalizado foi encontrado para a competência informada.",
                    styles["box_texto"]
                )]],
                colWidths=[doc.width]
            )

            aviso.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]))

            elementos.append(aviso)
        else:
            tabela_dados = [[
                FaturamentoService._p("Cliente", styles["tabela_head"]),
                FaturamentoService._p("Empresa", styles["tabela_head"]),
                FaturamentoService._p("Chamados", styles["tabela_head"]),
                FaturamentoService._p("Horas / Unidades", styles["tabela_head"]),
                FaturamentoService._p("Valor", styles["tabela_head"]),
            ]]

            total_faturado = 0
            total_minutos = 0
            total_unidades = 0
            total_chamados = 0

            for r in resumo:
                tabela_dados.append([
                    FaturamentoService._p(r["nome"] or "-", styles["tabela"]),
                    FaturamentoService._p(r["empresa"] or "-", styles["tabela"]),
                    FaturamentoService._p(str(r["quantidade_chamados"]), styles["tabela_centro"]),
                    FaturamentoService._p(r["total_horas_formatado"], styles["tabela_centro"]),
                    FaturamentoService._p(
                        FaturamentoService._formatar_moeda(r["total_faturado"]),
                        styles["tabela_direita"]
                    ),
                ])

                total_faturado += float(r["total_faturado"] or 0)
                total_minutos += int(r["total_minutos"] or 0)
                total_unidades += int(r.get("total_unidades") or 0)
                total_chamados += int(r["quantidade_chamados"] or 0)

            tabela = Table(
                tabela_dados,
                repeatRows=1,
                colWidths=[
                    doc.width * 0.22,
                    doc.width * 0.28,
                    doc.width * 0.12,
                    doc.width * 0.18,
                    doc.width * 0.20,
                ]
            )

            tabela.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FaturamentoService.COR_PRIMARIA)),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(FaturamentoService.COR_ZEBRA)]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))

            elementos.append(tabela)
            elementos.append(Spacer(1, 8 * mm))

            resumo_boxes = Table(
                [[
                    FaturamentoService._p(
                        f"<b>Resumo operacional</b><br/>"
                        f"Clientes faturados: {len(resumo)}<br/>"
                        f"Chamados finalizados: {total_chamados}<br/>"
                        f"Tempo / unidades: {FaturamentoService._formatar_resumo(total_minutos, total_unidades)}",
                        styles["box_texto"]
                    ),
                    FaturamentoService._p(
                        f"<b>Resumo financeiro</b><br/>"
                        f"Total consolidado: {FaturamentoService._formatar_moeda(total_faturado)}<br/>"
                        f"Referência: {referencia}<br/>"
                        f"Critério: conforme cadastro do cliente e tipo de serviço",
                        styles["box_texto"]
                    )
                ]],
                colWidths=[doc.width * 0.50, doc.width * 0.50]
            )

            resumo_boxes.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))

            elementos.append(resumo_boxes)

        doc.build(
            elementos,
            onFirstPage=lambda canvas, doc_obj: FaturamentoService._rodape(
                canvas,
                doc_obj,
                f"Relatório geral de faturamento • Competência {mes:02d}/{ano}"
            ),
            onLaterPages=lambda canvas, doc_obj: FaturamentoService._rodape(
                canvas,
                doc_obj,
                f"Relatório geral de faturamento • Competência {mes:02d}/{ano}"
            )
        )

        return FileResponse(
            temp.name,
            media_type="application/pdf",
            filename=f"relatorio_geral_{ano}_{mes:02d}.pdf"
        )

    # ================= PDF CLIENTE (PROFISSIONAL) =================

    @staticmethod
    def gerar_pdf_cliente(db: Session, cliente_id: int, ano: int, mes: int):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer

        detalhe = FaturamentoService.obter_detalhe_cliente(db, cliente_id, ano, mes)
        styles = FaturamentoService._obter_estilos_pdf()

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

        doc = SimpleDocTemplate(
            temp.name,
            pagesize=landscape(A4),
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=18 * mm
        )

        referencia = FaturamentoService._gerar_referencia(cliente_id, ano, mes)
        emitido_em = FaturamentoService._formatar_data_hora_atual()

        elementos = []

        cabecalho = Table(
            [[
                FaturamentoService._p(
                    f"<b>{FaturamentoService.EMPRESA_PADRAO}</b><br/>"
                    f"<font size='9'>Relatório mensal de faturamento para autorização</font>",
                    styles["cabecalho_inverso_titulo"]
                ),
                FaturamentoService._p(
                    f"<b>Referência:</b> {referencia}<br/>"
                    f"<b>Competência:</b> {mes:02d}/{ano}<br/>"
                    f"<b>Emitido em:</b> {emitido_em}",
                    styles["normal"]
                )
            ]],
            colWidths=[doc.width * 0.50, doc.width * 0.50]
        )

        cabecalho.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(FaturamentoService.COR_PRIMARIA)),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(FaturamentoService.COR_SECUNDARIA)),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        elementos.append(cabecalho)
        elementos.append(Spacer(1, 6 * mm))

        bloco_cliente = Table(
            [
                [
                    FaturamentoService._p("Cliente", styles["label"]),
                    FaturamentoService._p(detalhe["nome"] or "-", styles["normal"]),
                    FaturamentoService._p("Empresa", styles["label"]),
                    FaturamentoService._p(detalhe["empresa"] or "-", styles["normal"])
                ],
                [
                    FaturamentoService._p("Competência", styles["label"]),
                    FaturamentoService._p(f"{mes:02d}/{ano}", styles["normal"]),
                    FaturamentoService._p("Chamados finalizados", styles["label"]),
                    FaturamentoService._p(str(detalhe["quantidade_chamados"]), styles["normal"])
                ],
                [
                    FaturamentoService._p("Tempo / unidades", styles["label"]),
                    FaturamentoService._p(detalhe["total_horas_formatado"], styles["normal"]),
                    FaturamentoService._p("Status do relatório", styles["label"]),
                    FaturamentoService._p("Aguardando autorização", styles["normal"])
                ]
            ],
            colWidths=[
                doc.width * 0.14,
                doc.width * 0.36,
                doc.width * 0.16,
                doc.width * 0.34
            ]
        )

        bloco_cliente.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(FaturamentoService.COR_SECUNDARIA)),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor(FaturamentoService.COR_SECUNDARIA)),
        ]))

        elementos.append(bloco_cliente)
        elementos.append(Spacer(1, 6 * mm))

        elementos.append(FaturamentoService._p("<b>Detalhamento dos chamados faturados</b>", styles["box_titulo"]))
        elementos.append(Spacer(1, 2 * mm))

        if detalhe["chamados"]:
            tabela_dados = [[
                FaturamentoService._p("Chamado", styles["tabela_head"]),
                FaturamentoService._p("Data", styles["tabela_head"]),
                FaturamentoService._p("Início", styles["tabela_head"]),
                FaturamentoService._p("Fim", styles["tabela_head"]),
                FaturamentoService._p("Descrição", styles["tabela_head"]),
                FaturamentoService._p("Tipo", styles["tabela_head"]),
                FaturamentoService._p("Horas", styles["tabela_head"]),
                FaturamentoService._p("Unid.", styles["tabela_head"]),
                FaturamentoService._p("Valor", styles["tabela_head"]),
            ]]

            # Rastreamento de linhas
            linhas_historico = []   # linhas que são históricos
            linhas_subtotal = []    # linhas de subtotal
            linha_atual = 1         # 0 é o cabeçalho

            for c in detalhe["chamados"]:
                # Linha principal do chamado
                tabela_dados.append([
                    FaturamentoService._p(str(c["numero"]), styles["tabela_centro"]),
                    FaturamentoService._p(c["data_atendimento"], styles["tabela_centro"]),
                    FaturamentoService._p(c["hora_inicio"], styles["tabela_centro"]),
                    FaturamentoService._p(c["hora_termino"], styles["tabela_centro"]),
                    FaturamentoService._p(c["descricao_atendimento"], styles["tabela"]),
                    FaturamentoService._p(c["tipo_servico_descricao"], styles["tabela"]),
                    FaturamentoService._p(c["horas_atendimento"] or "-", styles["tabela_centro"]),
                    FaturamentoService._p(c["unidades_atendimento"] or "-", styles["tabela_centro"]),
                    FaturamentoService._p(
                        FaturamentoService._formatar_moeda(c["valor_total"]),
                        styles["tabela_direita"]
                    ),
                ])
                linha_atual += 1

                # Linhas de histórico (descrição CENTRALIZADA)
                historicos = c.get("historicos") or []
                for h in historicos:
                    # Monta descrição centralizada + tempo em verde com bullet
                    descricao = h["descricao"]
                    if h.get("tempo"):
                        descricao += f' <font size="7" color="{FaturamentoService.COR_VERDE}"><b>• {h["tempo"]}</b></font>'

                    tabela_dados.append([
                        FaturamentoService._p("", styles["tabela_centro"]),  # Chamado vazio
                        FaturamentoService._p(h["data"], styles["historico_centro_muted"]),
                        FaturamentoService._p(h.get("hora_inicio") or "—", styles["historico_centro_muted"]),
                        FaturamentoService._p(h.get("hora_termino") or "—", styles["historico_centro_muted"]),
                        FaturamentoService._p(descricao, styles["historico_descricao"]),  # CENTRALIZADA
                        FaturamentoService._p("", styles["tabela"]),
                        FaturamentoService._p("", styles["tabela_centro"]),
                        FaturamentoService._p("", styles["tabela_centro"]),
                        FaturamentoService._p("", styles["tabela_direita"]),
                    ])
                    linhas_historico.append(linha_atual)
                    linha_atual += 1

                # Linha de SUBTOTAL do chamado (fecha o bloco com valor consolidado)
                tabela_dados.append([
                    "", "", "", "", "", "", "",
                    FaturamentoService._p(f"Subtotal {c['numero']}:", styles["subtotal_label"]),
                    FaturamentoService._p(
                        FaturamentoService._formatar_moeda(c["valor_total"]),
                        styles["subtotal_valor"]
                    ),
                ])
                linhas_subtotal.append(linha_atual)
                linha_atual += 1

            tabela = Table(
                tabela_dados,
                repeatRows=1,
                colWidths=[
                    doc.width * 0.08,
                    doc.width * 0.08,
                    doc.width * 0.06,
                    doc.width * 0.06,
                    doc.width * 0.32,
                    doc.width * 0.14,
                    doc.width * 0.08,
                    doc.width * 0.07,
                    doc.width * 0.11
                ]
            )

            estilo_tabela = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FaturamentoService.COR_PRIMARIA)),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]

            # Histórico: fundo sutilmente diferenciado, padding reduzido
            for linha in linhas_historico:
                estilo_tabela.append(("BACKGROUND", (0, linha), (-1, linha), colors.HexColor(FaturamentoService.COR_HIST_FUNDO)))
                estilo_tabela.append(("TOPPADDING", (0, linha), (-1, linha), 4))
                estilo_tabela.append(("BOTTOMPADDING", (0, linha), (-1, linha), 4))

            # Subtotal: fundo azul-claro + SPAN pra esticar colunas 0-6 + borda grossa embaixo
            for linha in linhas_subtotal:
                estilo_tabela.append(("BACKGROUND", (0, linha), (-1, linha), colors.HexColor(FaturamentoService.COR_SUBTOTAL_FUNDO)))
                estilo_tabela.append(("SPAN", (0, linha), (6, linha)))  # Colunas 0-6 viram uma só (vazia)
                estilo_tabela.append(("LINEABOVE", (0, linha), (-1, linha), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)))
                estilo_tabela.append(("LINEBELOW", (0, linha), (-1, linha), 1.2, colors.HexColor(FaturamentoService.COR_PRIMARIA)))
                estilo_tabela.append(("TOPPADDING", (0, linha), (-1, linha), 6))
                estilo_tabela.append(("BOTTOMPADDING", (0, linha), (-1, linha), 6))

            tabela.setStyle(TableStyle(estilo_tabela))

            elementos.append(tabela)
        else:
            sem_dados = Table(
                [[FaturamentoService._p(
                    "Não há chamados finalizados para este cliente na competência informada.",
                    styles["box_texto"]
                )]],
                colWidths=[doc.width]
            )

            sem_dados.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]))

            elementos.append(sem_dados)

        elementos.append(Spacer(1, 6 * mm))

        qtd_servicos_hora = sum(
            1 for c in detalhe["chamados"]
            if c["tipo_servico"] == "suporte_usuario"
        )
        qtd_servicos_unidade = sum(
            1 for c in detalhe["chamados"]
            if c["tipo_servico"] == "suporte_tecnico"
        )

        resumo = Table(
            [[
                FaturamentoService._p(
                    f"<b>Resumo operacional</b><br/>"
                    f"Chamados finalizados: {detalhe['quantidade_chamados']}<br/>"
                    f"Serviços por hora: {qtd_servicos_hora}<br/>"
                    f"Serviços por unidade: {qtd_servicos_unidade}<br/>"
                    f"Tempo / unidades faturáveis: {detalhe['total_horas_formatado']}",
                    styles["box_texto"]
                ),
                FaturamentoService._p(
                    f"<b>Resumo financeiro</b><br/>"
                    f"Total apurado: {FaturamentoService._formatar_moeda(detalhe['total_faturado'])}<br/>"
                    f"Referência: {referencia}<br/>"
                    f"Critério: conforme tipo de serviço e regra de cobrança cadastrada",
                    styles["box_texto"]
                )
            ]],
            colWidths=[doc.width * 0.50, doc.width * 0.50]
        )

        resumo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        elementos.append(resumo)
        elementos.append(Spacer(1, 5 * mm))

        total_box = Table(
            [[FaturamentoService._p(
                f"TOTAL DO PERÍODO: {FaturamentoService._formatar_moeda(detalhe['total_faturado'])}",
                styles["total"]
            )]],
            colWidths=[doc.width]
        )

        total_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(FaturamentoService.COR_SECUNDARIA)),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))

        elementos.append(total_box)
        elementos.append(Spacer(1, 5 * mm))

        observacoes = Table(
            [[FaturamentoService._p(
                "<b>Observações</b><br/>"
                "Este relatório consolida os chamados finalizados na competência informada "
                "e deve ser utilizado para conferência e autorização prévia do faturamento, "
                "antes da emissão do documento fiscal correspondente.",
                styles["box_texto"]
            )]],
            colWidths=[doc.width]
        )

        observacoes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        elementos.append(observacoes)
        elementos.append(Spacer(1, 7 * mm))

        aprovacao = Table(
            [
                [
                    FaturamentoService._p("Responsável pela conferência", styles["label"]),
                    FaturamentoService._p("Data", styles["label"]),
                    FaturamentoService._p("Assinatura / Carimbo", styles["label"]),
                ],
                ["", "", ""]
            ],
            colWidths=[doc.width * 0.42, doc.width * 0.18, doc.width * 0.40],
            rowHeights=[None, 18 * mm]
        )

        aprovacao.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FaturamentoService.COR_SECUNDARIA)),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("LINEABOVE", (0, 1), (-1, 1), 0.6, colors.HexColor(FaturamentoService.COR_BORDA)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        elementos.append(aprovacao)

        doc.build(
            elementos,
            onFirstPage=lambda canvas, doc_obj: FaturamentoService._rodape(
                canvas,
                doc_obj,
                f"{detalhe['empresa']} • Relatório de faturamento • Competência {mes:02d}/{ano}"
            ),
            onLaterPages=lambda canvas, doc_obj: FaturamentoService._rodape(
                canvas,
                doc_obj,
                f"{detalhe['empresa']} • Relatório de faturamento • Competência {mes:02d}/{ano}"
            )
        )

        return FileResponse(
            temp.name,
            media_type="application/pdf",
            filename=f"relatorio_cliente_{cliente_id}_{ano}_{mes:02d}.pdf"
        )
