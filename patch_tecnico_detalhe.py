ARQUIVO = '/app/templates/tecnico_painel.html'

with open(ARQUIVO, 'r', encoding='utf-8') as f:
    html = f.read()

# ============================================================
# PATCH 1 — detInfo: mostrar itens_servicos no detalhe
# ============================================================

ANCORA = '''        const ehTec = c.tipo_servico === 'suporte_tecnico';
        const totalLabel = ehTec
            ? `<strong>Total:</strong> 📦 ${c.tempo_gasto_minutos || 0} un`
            : `<strong>Tempo gasto:</strong> ${fmtMin(c.tempo_gasto_minutos)}`;
        document.getElementById('detInfo').innerHTML = `
            <strong>Cliente:</strong> ${escapeHTML(c.cliente_nome || '—')}<br>
            <strong>Descrição:</strong> ${escapeHTML(c.descricao)}<br>
            <strong>Status:</strong> ${statusBadge(c.status)} &nbsp;
            <strong>Prioridade:</strong> ${prioBadge(c.prioridade)}<br>
            <strong>Tipo:</strong> ${ehTec ? '🔧 Técnico' : '⏱️ Por tempo'}
            ${c.servico_tecnico_nome ? ' — ' + escapeHTML(c.servico_tecnico_nome) : ''}<br>
            ${totalLabel}
            ${c.motivo_devolucao ? `<br><strong style="color:#c0392b;">⚠ Motivo da última devolução:</strong> ${escapeHTML(c.motivo_devolucao)}` : ''}
        `;'''

SUBSTITUTO = '''        const ehTec = c.tipo_servico === 'suporte_tecnico';

        // Monta bloco de serviços técnicos
        let servicosHtml = '';
        if (ehTec) {
            const itens = c.itens_servicos || [];
            if (itens.length > 0) {
                const linhas = itens.map(i => `
                    <tr>
                        <td style="padding:5px 8px; border:1px solid #e0e6ed;">${escapeHTML(i.servico_nome || '-')}</td>
                        <td style="padding:5px 8px; border:1px solid #e0e6ed; text-align:center;">${i.quantidade} un</td>
                    </tr>
                `).join('');
                servicosHtml = `
                    <table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:6px;">
                        <thead>
                            <tr style="background:#f0f4f8;">
                                <th style="padding:5px 8px; text-align:left; border:1px solid #ddd;">Serviço</th>
                                <th style="padding:5px 8px; text-align:center; border:1px solid #ddd; width:70px;">Qtd</th>
                            </tr>
                        </thead>
                        <tbody>${linhas}</tbody>
                    </table>`;
            } else {
                servicosHtml = `<span style="color:#aaa;">— serviço a definir —</span>`;
            }
        }

        const totalLabel = ehTec
            ? `<strong>Serviços:</strong><br>${servicosHtml}`
            : `<strong>Tempo gasto:</strong> ${fmtMin(c.tempo_gasto_minutos)}`;

        document.getElementById('detInfo').innerHTML = `
            <strong>Cliente:</strong> ${escapeHTML(c.cliente_nome || '—')}<br>
            <strong>Descrição:</strong> ${escapeHTML(c.descricao)}<br>
            <strong>Status:</strong> ${statusBadge(c.status)} &nbsp;
            <strong>Prioridade:</strong> ${prioBadge(c.prioridade)}<br>
            <strong>Tipo:</strong> ${ehTec ? '🔧 Técnico' : '⏱️ Por tempo'}<br>
            ${totalLabel}
            ${c.motivo_devolucao ? `<br><strong style="color:#c0392b;">⚠ Motivo da última devolução:</strong> ${escapeHTML(c.motivo_devolucao)}` : ''}
        `;'''

if ANCORA in html:
    html = html.replace(ANCORA, SUBSTITUTO, 1)
    print('✓ Patch 1: detInfo lista itens_servicos')
else:
    print('✗ Patch 1: âncora não encontrada')

with open(ARQUIVO, 'w', encoding='utf-8') as f:
    f.write(html)

print('✅ Patch detalhe técnico concluído!')
