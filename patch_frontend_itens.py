"""
Patch cirúrgico no chamados.html:
1. Substitui secaoServicos por versão com lista de itens
2. Atualiza submit do form para enviar itens[]
3. Atualiza modal finalizar-tecnico para listar itens por linha
"""
import re

ARQUIVO = '/app/templates/chamados.html'

with open(ARQUIVO, 'r', encoding='utf-8') as f:
    html = f.read()

# ============================================================
# PATCH 1 — secaoServicos: adiciona tabela de itens abaixo do combobox
# Localiza o fechamento da div.combobox-group e injeta a tabela de itens
# ============================================================

ANCORA_COMBOBOX = '''                    <div class="info-sem-valor">
                        <span>💡</span>
                        <span>O valor do chamado será definido pelo administrador ao finalizar o atendimento. Até lá, fica zerado.</span>
                    </div>
                </div>
            </div>'''

SUBSTITUTO_COMBOBOX = '''                    <div class="info-sem-valor">
                        <span>💡</span>
                        <span>O valor do chamado será definido pelo administrador ao finalizar o atendimento. Até lá, fica zerado.</span>
                    </div>
                </div>

                <!-- LISTA DE ITENS ADICIONADOS -->
                <div id="itensAdicionados" style="margin-top:12px; display:none;">
                    <label style="font-weight:600; color:#333; font-size:13px; margin-bottom:6px; display:block;">📦 Serviços adicionados ao chamado:</label>
                    <table style="width:100%; border-collapse:collapse; font-size:13px;">
                        <thead>
                            <tr style="background:#f0f4f8;">
                                <th style="padding:8px; text-align:left; border:1px solid #ddd;">Serviço</th>
                                <th style="padding:8px; text-align:center; border:1px solid #ddd; width:80px;">Qtd</th>
                                <th style="padding:8px; text-align:center; border:1px solid #ddd; width:60px;"></th>
                            </tr>
                        </thead>
                        <tbody id="itensAdicionadosBody"></tbody>
                    </table>
                </div>

                <!-- BOTÃO ADICIONAR ITEM -->
                <div id="btnAdicionarItemWrap" style="margin-top:10px; display:none;">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="adicionarItemAoForm()">➕ Adicionar outro serviço</button>
                </div>

            </div>'''

if ANCORA_COMBOBOX in html:
    html = html.replace(ANCORA_COMBOBOX, SUBSTITUTO_COMBOBOX, 1)
    print('✓ Patch 1: tabela de itens adicionada ao form')
else:
    print('✗ Patch 1: âncora não encontrada — verifique manualmente')

# ============================================================
# PATCH 2 — função selecionarServicoCombobox: ao selecionar serviço,
# em vez de apenas gravar no hidden, adiciona à lista de itens
# ============================================================

ANCORA_SELECIONAR = '''function selecionarServicoCombobox(id) {
    const s = servicosTecnicos.find(x => x.id === id);
    if (!s) return;

    document.getElementById('servico_id').value = s.id;
    document.getElementById('servico_tecnico').value = '';
    document.getElementById('servicoCustomNome').value = '';

    // Mostra card de selecionado
    document.getElementById('servicoSelNome').textContent = s.nome;
    document.getElementById('servicoSelCat').textContent = s.categoria;
    document.getElementById('servicoSelecionadoBox').style.display = 'flex';

    // Esconde combobox e personalizado
    document.getElementById('comboxServicoWrap').style.display = 'none';
    document.getElementById('servicoCustomBox').style.display = 'none';

    fecharDropdownServicos();
}'''

SUBSTITUTO_SELECIONAR = '''// Lista de itens do form (novo fluxo multi-serviço)
let _itensForm = []; // [{servico_id, nome, quantidade}]

function selecionarServicoCombobox(id) {
    const s = servicosTecnicos.find(x => x.id === id);
    if (!s) return;

    // Adiciona à lista de itens
    const existente = _itensForm.find(i => i.servico_id === s.id);
    if (existente) {
        existente.quantidade += 1;
    } else {
        _itensForm.push({ servico_id: s.id, nome: s.nome, quantidade: 1 });
    }
    renderizarItensForm();

    // Atualiza hidden legado com o primeiro item
    document.getElementById('servico_id').value = _itensForm[0].servico_id;
    document.getElementById('servico_tecnico').value = '';
    document.getElementById('servicoCustomNome').value = '';

    // Mostra card de selecionado (primeiro item)
    document.getElementById('servicoSelNome').textContent = _itensForm.map(i => i.nome).join(', ');
    document.getElementById('servicoSelCat').textContent = _itensForm.length + ' serviço(s) selecionado(s)';
    document.getElementById('servicoSelecionadoBox').style.display = 'flex';

    // Esconde combobox e personalizado
    document.getElementById('comboxServicoWrap').style.display = 'none';
    document.getElementById('servicoCustomBox').style.display = 'none';

    fecharDropdownServicos();
}

function renderizarItensForm() {
    const tbody = document.getElementById('itensAdicionadosBody');
    const wrap = document.getElementById('itensAdicionados');
    const btnWrap = document.getElementById('btnAdicionarItemWrap');
    if (!tbody) return;

    if (_itensForm.length === 0) {
        wrap.style.display = 'none';
        btnWrap.style.display = 'none';
        return;
    }

    wrap.style.display = 'block';
    btnWrap.style.display = 'block';

    tbody.innerHTML = _itensForm.map((item, idx) => `
        <tr>
            <td style="padding:8px; border:1px solid #ddd;">${escapeHTMLstr(item.nome)}</td>
            <td style="padding:8px; border:1px solid #ddd; text-align:center;">
                <input type="number" min="1" value="${item.quantidade}"
                    style="width:60px; padding:4px; border:1px solid #ddd; border-radius:4px; text-align:center;"
                    onchange="_itensForm[${idx}].quantidade = parseInt(this.value) || 1">
            </td>
            <td style="padding:8px; border:1px solid #ddd; text-align:center;">
                <button type="button" style="background:none; border:none; cursor:pointer; color:#e74c3c; font-size:16px;"
                    onclick="removerItemForm(${idx})">🗑</button>
            </td>
        </tr>
    `).join('');
}

function removerItemForm(idx) {
    _itensForm.splice(idx, 1);
    renderizarItensForm();
    if (_itensForm.length === 0) {
        // Volta para o combobox
        document.getElementById('servico_id').value = '';
        document.getElementById('servicoSelecionadoBox').style.display = 'none';
        document.getElementById('comboxServicoWrap').style.display = '';
    } else {
        document.getElementById('servico_id').value = _itensForm[0].servico_id;
    }
}

function adicionarItemAoForm() {
    // Volta o combobox para selecionar mais um serviço
    document.getElementById('servicoSelecionadoBox').style.display = 'none';
    document.getElementById('comboxServicoWrap').style.display = '';
    document.getElementById('comboxServicoInput').value = '';
    renderizarDropdownServicos(servicosTecnicos);
    document.getElementById('comboxServicoInput').focus();
}'''

if ANCORA_SELECIONAR in html:
    html = html.replace(ANCORA_SELECIONAR, SUBSTITUTO_SELECIONAR, 1)
    print('✓ Patch 2: selecionarServicoCombobox atualizado para multi-item')
else:
    print('✗ Patch 2: âncora não encontrada')

# ============================================================
# PATCH 3 — limparServicoSelecionado: também limpa _itensForm
# ============================================================

ANCORA_LIMPAR = '''function limparServicoSelecionado() {
    document.getElementById('servico_id').value = '';
    document.getElementById('servico_tecnico').value = '';
    document.getElementById('servicoSelecionadoBox').style.display = 'none';
    document.getElementById('servicoCustomBox').style.display = 'none';
    document.getElementById('comboxServicoWrap').style.display = '';
    document.getElementById('comboxServicoInput').value = '';
    renderizarDropdownServicos(servicosTecnicos);
    document.getElementById('comboxServicoInput').focus();
}'''

SUBSTITUTO_LIMPAR = '''function limparServicoSelecionado() {
    _itensForm = [];
    document.getElementById('servico_id').value = '';
    document.getElementById('servico_tecnico').value = '';
    document.getElementById('servicoSelecionadoBox').style.display = 'none';
    document.getElementById('servicoCustomBox').style.display = 'none';
    document.getElementById('comboxServicoWrap').style.display = '';
    document.getElementById('comboxServicoInput').value = '';
    renderizarItensForm();
    renderizarDropdownServicos(servicosTecnicos);
    document.getElementById('comboxServicoInput').focus();
}'''

if ANCORA_LIMPAR in html:
    html = html.replace(ANCORA_LIMPAR, SUBSTITUTO_LIMPAR, 1)
    print('✓ Patch 3: limparServicoSelecionado limpa _itensForm')
else:
    print('✗ Patch 3: âncora não encontrada')

# ============================================================
# PATCH 4 — cancelarEdicao: também limpa _itensForm
# ============================================================

ANCORA_CANCELAR = '''function cancelarEdicao() {
    editandoId = null;
    document.getElementById('formChamado').reset();
    document.getElementById('formTitle').textContent = '➕ Novo Chamado';
    document.getElementById('btnSalvar').textContent = '✓ Abrir Chamado';
    document.getElementById('btnCancelar').style.display = 'none';
    document.getElementById('cardForm').classList.remove('editing-mode');
    selecionarTipo('suporte_usuario');
}'''

SUBSTITUTO_CANCELAR = '''function cancelarEdicao() {
    editandoId = null;
    _itensForm = [];
    document.getElementById('formChamado').reset();
    document.getElementById('formTitle').textContent = '➕ Novo Chamado';
    document.getElementById('btnSalvar').textContent = '✓ Abrir Chamado';
    document.getElementById('btnCancelar').style.display = 'none';
    document.getElementById('cardForm').classList.remove('editing-mode');
    selecionarTipo('suporte_usuario');
}'''

if ANCORA_CANCELAR in html:
    html = html.replace(ANCORA_CANCELAR, SUBSTITUTO_CANCELAR, 1)
    print('✓ Patch 4: cancelarEdicao limpa _itensForm')
else:
    print('✗ Patch 4: âncora não encontrada')

# ============================================================
# PATCH 5 — submit do form: enviar itens[] em vez de servico_id único
# ============================================================

ANCORA_SUBMIT = '''    // Só envia os campos de serviço se for suporte técnico
    if (tipoServico === 'suporte_tecnico') {
        if (servicoIdStr) {
            dados.servico_id = parseInt(servicoIdStr);
        } else if (servicoTextoLivre) {
            dados.servico_tecnico = servicoTextoLivre;
        }
    }

    if (!dados.titulo || !dados.descricao) { mostrarErro('Preencha título e descrição!'); return; }
    if (!dados.cliente_id) { mostrarErro('Selecione uma empresa!'); return; }
    if (tipoServico === 'suporte_tecnico' && !dados.servico_id && !dados.servico_tecnico) {
        mostrarErro('Selecione um serviço técnico ou crie um personalizado!');
        return;
    }'''

SUBSTITUTO_SUBMIT = '''    // Só envia os campos de serviço se for suporte técnico
    if (tipoServico === 'suporte_tecnico') {
        if (_itensForm.length > 0) {
            // Novo fluxo: lista de itens
            dados.itens = _itensForm.map(i => ({ servico_id: i.servico_id, quantidade: i.quantidade }));
        } else if (servicoIdStr) {
            // Legado: serviço único
            dados.servico_id = parseInt(servicoIdStr);
        } else if (servicoTextoLivre) {
            dados.servico_tecnico = servicoTextoLivre;
        }
    }

    if (!dados.titulo || !dados.descricao) { mostrarErro('Preencha título e descrição!'); return; }
    if (!dados.cliente_id) { mostrarErro('Selecione uma empresa!'); return; }
    if (tipoServico === 'suporte_tecnico' && !dados.itens && !dados.servico_id && !dados.servico_tecnico) {
        mostrarErro('Selecione ao menos um serviço técnico!');
        return;
    }'''

if ANCORA_SUBMIT in html:
    html = html.replace(ANCORA_SUBMIT, SUBSTITUTO_SUBMIT, 1)
    print('✓ Patch 5: submit envia itens[]')
else:
    print('✗ Patch 5: âncora não encontrada')

# ============================================================
# PATCH 6 — modal de detalhe: mostrar tabela de itens_servicos
# Substitui a parte do tipoInfo que mostra 1 serviço por tabela
# ============================================================

ANCORA_TIPO_INFO = '''                ${tipoInfo}'''

# Não vamos mudar tipoInfo direto pois ele é gerado dinamicamente.
# Em vez disso, vamos injetar a tabela de itens APÓS o resumoFinanceiroHtml
# para chamados técnicos. Isso é feito no patch do resumoFinanceiroHtml.

# ============================================================
# PATCH 7 — modal finalizar técnico: lista itens por linha
# Substitui confirmarFinalizarTecnico para enviar lista de itens
# ============================================================

ANCORA_CONFIRMAR_TECNICO = '''async function confirmarFinalizarTecnico(chamadoId) {
    const valor = parseFloat(document.getElementById('finValorUnitario').value) || 0;
    const qtd = parseInt(document.getElementById('finQuantidade').value) || 0;
    const dataInput = document.getElementById('finDataTermino');
    const dataValor = dataInput ? dataInput.value : '';

    if (valor < 0) { mostrarErro('Valor unitário não pode ser negativo'); return; }
    if (qtd < 1) { mostrarErro('Quantidade precisa ser pelo menos 1'); return; }
    if (!dataValor) { mostrarErro('Informe a data de finalização'); return; }

    if (valor === 0) {
        if (!confirm('Valor unitário está zerado. Confirma finalizar com R$ 0,00?')) return;
    }

    const body = {
        valor_unitario: valor,
        quantidade: qtd,
        data_termino: dataValor + 'T23:59:00'
    };

    try {
        const res = await fetch(`/api/chamados/${chamadoId}/finalizar-tecnico`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify(body)
        });
        if (res.ok) {
            mostrarSucesso('Chamado finalizado com sucesso!');
            fecharModalFinalizarTecnico();
            carregarChamados();
            abrirDetalhe(chamadoId);
        } else {
            const e = await res.json();
            mostrarErro(e.detail || 'Erro ao finalizar');
        }
    } catch (err) {
        mostrarErro('Erro: ' + err.message);
    }
}'''

SUBSTITUTO_CONFIRMAR_TECNICO = '''async function confirmarFinalizarTecnico(chamadoId) {
    const dataInput = document.getElementById('finDataTermino');
    const dataValor = dataInput ? dataInput.value : '';
    if (!dataValor) { mostrarErro('Informe a data de finalização'); return; }

    const c = window._chamadoAtual;
    const itens = (c && c.itens_servicos && c.itens_servicos.length > 0) ? c.itens_servicos : null;

    let body = { data_termino: dataValor + 'T23:59:00' };

    if (itens && itens.length > 0) {
        // Novo fluxo: lê cada linha da tabela de itens
        const linhas = document.querySelectorAll('#tabelaItensFinalizacao tbody tr');
        const itensPayload = [];
        let totalGeral = 0;

        for (const linha of linhas) {
            const itemId = parseInt(linha.dataset.itemId);
            const valor = parseFloat(linha.querySelector('.fin-valor').value) || 0;
            const qtd = parseInt(linha.querySelector('.fin-qtd').value) || 1;

            if (valor < 0) { mostrarErro('Valor unitário não pode ser negativo'); return; }
            if (qtd < 1) { mostrarErro('Quantidade precisa ser pelo menos 1'); return; }

            totalGeral += valor * qtd;
            itensPayload.push({ item_id: itemId, valor_unitario: valor, quantidade: qtd });
        }

        if (totalGeral === 0) {
            if (!confirm('Valor total está zerado. Confirma finalizar com R$ 0,00?')) return;
        }

        body.itens = itensPayload;
    } else {
        // Fluxo legado
        const valor = parseFloat(document.getElementById('finValorUnitario').value) || 0;
        const qtd = parseInt(document.getElementById('finQuantidade').value) || 0;
        if (valor < 0) { mostrarErro('Valor unitário não pode ser negativo'); return; }
        if (qtd < 1) { mostrarErro('Quantidade precisa ser pelo menos 1'); return; }
        if (valor === 0) {
            if (!confirm('Valor unitário está zerado. Confirma finalizar com R$ 0,00?')) return;
        }
        body.valor_unitario = valor;
        body.quantidade = qtd;
    }

    try {
        const res = await fetch(`/api/chamados/${chamadoId}/finalizar-tecnico`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify(body)
        });
        if (res.ok) {
            mostrarSucesso('Chamado finalizado com sucesso!');
            fecharModalFinalizarTecnico();
            carregarChamados();
            abrirDetalhe(chamadoId);
        } else {
            const e = await res.json();
            mostrarErro(e.detail || 'Erro ao finalizar');
        }
    } catch (err) {
        mostrarErro('Erro: ' + err.message);
    }
}'''

if ANCORA_CONFIRMAR_TECNICO in html:
    html = html.replace(ANCORA_CONFIRMAR_TECNICO, SUBSTITUTO_CONFIRMAR_TECNICO, 1)
    print('✓ Patch 7: confirmarFinalizarTecnico envia lista de itens')
else:
    print('✗ Patch 7: âncora não encontrada')

# ============================================================
# PATCH 8 — abrirModalFinalizarTecnico: mostrar tabela de itens
# Substitui o calc-valor-box por tabela quando há itens_servicos
# ============================================================

ANCORA_MODAL_TECNICO_CALC = '''                    <div class="calc-valor-box">
                        <div class="calc-grid">
                            <div>
                                <label>Valor unitário (R$)</label>
                                <input type="number" id="finValorUnitario" value="${valorSugerido.toFixed(2)}" step="0.01" min="0" oninput="atualizarCalcFinalizar()">
                            </div>
                            <div class="operador">×</div>
                            <div>
                                <label>Quantidade</label>
                                <input type="number" id="finQuantidade" value="${qtdSugerida}" min="1" oninput="atualizarCalcFinalizar()">
                            </div>
                        </div>

                        <div class="resultado">
                            <div class="resultado-label">Valor total a faturar</div>
                            <div class="resultado-valor" id="finResultado">${formatarValor(valorSugerido * qtdSugerida)}</div>
                        </div>
                    </div>'''

SUBSTITUTO_MODAL_TECNICO_CALC = '''                    ${_buildTabelaItensFinalizacao(c)}'''

if ANCORA_MODAL_TECNICO_CALC in html:
    html = html.replace(ANCORA_MODAL_TECNICO_CALC, SUBSTITUTO_MODAL_TECNICO_CALC, 1)
    print('✓ Patch 8: modal finalização usa tabela de itens')
else:
    print('✗ Patch 8: âncora não encontrada')

# ============================================================
# PATCH 9 — adicionar função _buildTabelaItensFinalizacao
# Injeta antes de fecharModalFinalizarTecnico
# ============================================================

ANCORA_FECHAR_MODAL = '''function fecharModalFinalizarTecnico() {
    const m = document.getElementById('modalFinalizarTecnico');
    if (m) m.remove();
}'''

SUBSTITUTO_FECHAR_MODAL = '''function _buildTabelaItensFinalizacao(c) {
    const itens = c.itens_servicos || [];
    if (itens.length === 0) {
        // Fluxo legado: sem itens, mostra campo único
        const valorSugerido = c.servico_valor_padrao || 0;
        const qtdSugerida = (c.tempo_gasto_minutos && c.tempo_gasto_minutos > 0) ? c.tempo_gasto_minutos : 1;
        return `
            <div class="calc-valor-box">
                <div class="calc-grid">
                    <div>
                        <label>Valor unitário (R$)</label>
                        <input type="number" id="finValorUnitario" value="${valorSugerido.toFixed(2)}" step="0.01" min="0" oninput="atualizarCalcFinalizar()">
                    </div>
                    <div class="operador">×</div>
                    <div>
                        <label>Quantidade</label>
                        <input type="number" id="finQuantidade" value="${qtdSugerida}" min="1" oninput="atualizarCalcFinalizar()">
                    </div>
                </div>
                <div class="resultado">
                    <div class="resultado-label">Valor total a faturar</div>
                    <div class="resultado-valor" id="finResultado">${formatarValor(valorSugerido * qtdSugerida)}</div>
                </div>
            </div>`;
    }

    // Novo fluxo: tabela com 1 linha por item
    const linhas = itens.map(item => `
        <tr data-item-id="${item.id}">
            <td style="padding:8px; border:1px solid #ddd;">${escapeHTMLstr(item.servico_nome || '-')}</td>
            <td style="padding:8px; border:1px solid #ddd; text-align:center;">
                <input class="fin-qtd" type="number" min="1" value="${item.quantidade}"
                    style="width:60px; padding:4px; border:1px solid #ddd; border-radius:4px; text-align:center;"
                    oninput="atualizarTotalFinalizacao()">
            </td>
            <td style="padding:8px; border:1px solid #ddd; text-align:center;">
                <input class="fin-valor" type="number" min="0" step="0.01" value="${(item.valor_unitario || 0).toFixed(2)}"
                    style="width:90px; padding:4px; border:1px solid #ddd; border-radius:4px; text-align:right;"
                    oninput="atualizarTotalFinalizacao()">
            </td>
            <td style="padding:8px; border:1px solid #ddd; text-align:right; font-weight:600; color:#27ae60;" id="subtotal_item_${item.id}">
                ${formatarValor((item.valor_unitario || 0) * item.quantidade)}
            </td>
        </tr>
    `).join('');

    const totalAtual = itens.reduce((s, i) => s + (i.valor_unitario || 0) * i.quantidade, 0);

    return `
        <div style="margin-top:12px;">
            <label style="font-weight:600; color:#333; font-size:13px; margin-bottom:6px; display:block;">💰 Ajuste os valores por serviço:</label>
            <table id="tabelaItensFinalizacao" style="width:100%; border-collapse:collapse; font-size:13px;">
                <thead>
                    <tr style="background:#f0f4f8;">
                        <th style="padding:8px; text-align:left; border:1px solid #ddd;">Serviço</th>
                        <th style="padding:8px; text-align:center; border:1px solid #ddd; width:80px;">Qtd</th>
                        <th style="padding:8px; text-align:center; border:1px solid #ddd; width:100px;">Valor Unit.</th>
                        <th style="padding:8px; text-align:right; border:1px solid #ddd; width:110px;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>${linhas}</tbody>
            </table>
            <div style="text-align:right; margin-top:8px; font-size:15px; font-weight:700; color:#1F3A5F;">
                Total: <span id="finTotalGeral" style="color:#27ae60;">${formatarValor(totalAtual)}</span>
            </div>
        </div>`;
}

function atualizarTotalFinalizacao() {
    let total = 0;
    const linhas = document.querySelectorAll('#tabelaItensFinalizacao tbody tr');
    for (const linha of linhas) {
        const itemId = linha.dataset.itemId;
        const valor = parseFloat(linha.querySelector('.fin-valor').value) || 0;
        const qtd = parseInt(linha.querySelector('.fin-qtd').value) || 1;
        const sub = valor * qtd;
        total += sub;
        const subEl = document.getElementById('subtotal_item_' + itemId);
        if (subEl) subEl.textContent = formatarValor(sub);
    }
    const totalEl = document.getElementById('finTotalGeral');
    if (totalEl) totalEl.textContent = formatarValor(total);
}

function fecharModalFinalizarTecnico() {
    const m = document.getElementById('modalFinalizarTecnico');
    if (m) m.remove();
}'''

if ANCORA_FECHAR_MODAL in html:
    html = html.replace(ANCORA_FECHAR_MODAL, SUBSTITUTO_FECHAR_MODAL, 1)
    print('✓ Patch 9: _buildTabelaItensFinalizacao adicionada')
else:
    print('✗ Patch 9: âncora não encontrada')

# ============================================================
# PATCH 10 — modal detalhe: mostrar itens_servicos na seção técnico
# Substitui o bloco de "Serviço prestado" no resumoFinanceiroHtml
# para chamados técnicos finalizados
# ============================================================

ANCORA_RESUMO_TECNICO_FINALIZADO = '''                    <div class="resumo-item">
                            <div class="rf-label">Quantidade</div>
                            <div class="rf-valor">${qtd} un</div>
                            <div class="rf-sub">${c.historicos.length} registro${c.historicos.length !== 1 ? 's' : ''}</div>
                        </div>
                        <div class="resumo-item">
                            <div class="rf-label">Valor Unitário</div>
                            <div class="rf-valor laranja">${formatarValor(c.valor_fixo)}</div>
                            <div class="rf-sub">definido pelo admin</div>
                        </div>
                        <div class="resumo-item">
                            <div class="rf-label">Cálculo</div>
                            <div class="rf-valor pequeno">Qtd × Valor<br>Unitário</div>
                            <div class="rf-sub">serviço técnico</div>
                        </div>
                        <div class="resumo-item">
                            <div class="rf-label">Valor Faturado</div>
                            <div class="rf-valor verde">${formatarValor(c.valor_total)}</div>
                            <div class="rf-sub">finalizado</div>
                        </div>'''

SUBSTITUTO_RESUMO_TECNICO_FINALIZADO = '''                    ${_buildResumoItensTecnico(c)}'''

if ANCORA_RESUMO_TECNICO_FINALIZADO in html:
    html = html.replace(ANCORA_RESUMO_TECNICO_FINALIZADO, SUBSTITUTO_RESUMO_TECNICO_FINALIZADO, 1)
    print('✓ Patch 10: resumo técnico usa _buildResumoItensTecnico')
else:
    print('✗ Patch 10: âncora não encontrada')

# Adiciona _buildResumoItensTecnico junto com _buildTabelaItensFinalizacao
ANCORA_INJECT_RESUMO = '''function _buildTabelaItensFinalizacao(c) {'''

SUBSTITUTO_INJECT_RESUMO = '''function _buildResumoItensTecnico(c) {
    const itens = c.itens_servicos || [];
    if (itens.length === 0) {
        // Legado: sem itens
        const qtd = c.tempo_gasto_minutos || 0;
        return `
            <div class="resumo-item">
                <div class="rf-label">Quantidade</div>
                <div class="rf-valor">${qtd} un</div>
                <div class="rf-sub">${c.historicos.length} registro${c.historicos.length !== 1 ? 's' : ''}</div>
            </div>
            <div class="resumo-item">
                <div class="rf-label">Valor Unitário</div>
                <div class="rf-valor laranja">${formatarValor(c.valor_fixo)}</div>
                <div class="rf-sub">definido pelo admin</div>
            </div>
            <div class="resumo-item">
                <div class="rf-label">Cálculo</div>
                <div class="rf-valor pequeno">Qtd × Valor<br>Unitário</div>
                <div class="rf-sub">serviço técnico</div>
            </div>
            <div class="resumo-item">
                <div class="rf-label">Valor Faturado</div>
                <div class="rf-valor verde">${formatarValor(c.valor_total)}</div>
                <div class="rf-sub">finalizado</div>
            </div>`;
    }

    // Novo fluxo: lista de itens
    const linhasHtml = itens.map(item => `
        <tr>
            <td style="padding:6px 8px; border:1px solid #e0e6ed;">${escapeHTMLstr(item.servico_nome || '-')}</td>
            <td style="padding:6px 8px; border:1px solid #e0e6ed; text-align:center;">${item.quantidade} un</td>
            <td style="padding:6px 8px; border:1px solid #e0e6ed; text-align:right;">${formatarValor(item.valor_unitario)}</td>
            <td style="padding:6px 8px; border:1px solid #e0e6ed; text-align:right; font-weight:600; color:#27ae60;">${formatarValor(item.valor_total)}</td>
        </tr>
    `).join('');

    return `
        <div style="grid-column: span 4; width:100%;">
            <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:8px;">
                <thead>
                    <tr style="background:#f0f4f8;">
                        <th style="padding:7px 8px; text-align:left; border:1px solid #ddd;">Serviço</th>
                        <th style="padding:7px 8px; text-align:center; border:1px solid #ddd; width:70px;">Qtd</th>
                        <th style="padding:7px 8px; text-align:right; border:1px solid #ddd; width:110px;">Valor Unit.</th>
                        <th style="padding:7px 8px; text-align:right; border:1px solid #ddd; width:110px;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>${linhasHtml}</tbody>
                <tfoot>
                    <tr style="background:#eef2f7;">
                        <td colspan="3" style="padding:7px 8px; border:1px solid #ddd; font-weight:700; text-align:right;">Total faturado:</td>
                        <td style="padding:7px 8px; border:1px solid #ddd; font-weight:700; color:#27ae60; text-align:right;">${formatarValor(c.total_calculado || c.valor_total)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>`;
}

function _buildTabelaItensFinalizacao(c) {'''

if ANCORA_INJECT_RESUMO in html:
    html = html.replace(ANCORA_INJECT_RESUMO, SUBSTITUTO_INJECT_RESUMO, 1)
    print('✓ Patch 11: _buildResumoItensTecnico adicionada')
else:
    print('✗ Patch 11: âncora não encontrada')

# Salva
with open(ARQUIVO, 'w', encoding='utf-8') as f:
    f.write(html)

print('\n✅ Todos os patches aplicados!')
