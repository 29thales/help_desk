"""
Patch: multi-serviço no painel do técnico (tecnico_painel.html)
- Substitui select único por lista de itens com botão adicionar
- Atualiza criarChamado() para enviar itens[]
"""

ARQUIVO = '/app/templates/tecnico_painel.html'

with open(ARQUIVO, 'r', encoding='utf-8') as f:
    html = f.read()

# ============================================================
# PATCH 1 — substitui o grpServico (select único) por lista de itens
# ============================================================

ANCORA_SERVICO = '''            <!-- Bloco que aparece SÓ se suporte técnico -->
            <div class="form-group" id="grpServico" style="display:none;">
                <label>Serviço técnico *</label>
                <select id="novoServico">
                    <option value="">— Selecione um serviço —</option>
                </select>
                <div class="help-text">Se o serviço que você precisa não está na lista, peça ao admin para cadastrar.</div>
            </div>'''

SUBSTITUTO_SERVICO = '''            <!-- Bloco que aparece SÓ se suporte técnico -->
            <div class="form-group" id="grpServico" style="display:none;">
                <label>Serviço técnico *</label>
                <div style="display:flex; gap:8px; align-items:center;">
                    <select id="novoServico" style="flex:1;">
                        <option value="">— Selecione um serviço —</option>
                    </select>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="adicionarServicoTecnico()" style="white-space:nowrap;">➕ Adicionar</button>
                </div>
                <div class="help-text">Selecione e clique em ➕ para adicionar. Pode adicionar vários serviços.</div>

                <!-- Lista de itens adicionados -->
                <div id="tecItensWrap" style="display:none; margin-top:10px;">
                    <table style="width:100%; border-collapse:collapse; font-size:13px;">
                        <thead>
                            <tr style="background:#f0f4f8;">
                                <th style="padding:7px 8px; text-align:left; border:1px solid #ddd;">Serviço</th>
                                <th style="padding:7px 8px; text-align:center; border:1px solid #ddd; width:80px;">Qtd</th>
                                <th style="padding:7px 8px; text-align:center; border:1px solid #ddd; width:50px;"></th>
                            </tr>
                        </thead>
                        <tbody id="tecItensBody"></tbody>
                    </table>
                </div>
            </div>'''

if ANCORA_SERVICO in html:
    html = html.replace(ANCORA_SERVICO, SUBSTITUTO_SERVICO, 1)
    print('✓ Patch 1: grpServico virou lista de itens')
else:
    print('✗ Patch 1: âncora não encontrada')

# ============================================================
# PATCH 2 — adiciona variável _tecItensForm e funções de controle
# Injeta antes de function criarChamado()
# ============================================================

ANCORA_CRIAR = '''async function criarChamado() {'''

SUBSTITUTO_CRIAR = '''let _tecItensForm = []; // [{servico_id, nome, quantidade}]

function adicionarServicoTecnico() {
    const sel = document.getElementById('novoServico');
    const sid = parseInt(sel.value);
    if (!sid) { mostrarErro('Selecione um serviço antes de adicionar'); return; }
    const nome = sel.options[sel.selectedIndex].text;
    const existente = _tecItensForm.find(i => i.servico_id === sid);
    if (existente) {
        existente.quantidade += 1;
    } else {
        _tecItensForm.push({ servico_id: sid, nome, quantidade: 1 });
    }
    sel.value = '';
    renderizarTecItens();
}

function renderizarTecItens() {
    const tbody = document.getElementById('tecItensBody');
    const wrap = document.getElementById('tecItensWrap');
    if (!tbody) return;
    if (_tecItensForm.length === 0) {
        wrap.style.display = 'none';
        return;
    }
    wrap.style.display = 'block';
    tbody.innerHTML = _tecItensForm.map((item, idx) => `
        <tr>
            <td style="padding:7px 8px; border:1px solid #ddd;">${escapeHTML(item.nome)}</td>
            <td style="padding:7px 8px; border:1px solid #ddd; text-align:center;">
                <input type="number" min="1" value="${item.quantidade}"
                    style="width:55px; padding:3px; border:1px solid #ddd; border-radius:4px; text-align:center;"
                    onchange="_tecItensForm[${idx}].quantidade = parseInt(this.value) || 1">
            </td>
            <td style="padding:7px 8px; border:1px solid #ddd; text-align:center;">
                <button type="button" style="background:none; border:none; cursor:pointer; color:#e74c3c; font-size:15px;"
                    onclick="_tecItensForm.splice(${idx},1); renderizarTecItens()">🗑</button>
            </td>
        </tr>
    `).join('');
}

async function criarChamado() {'''

if ANCORA_CRIAR in html:
    html = html.replace(ANCORA_CRIAR, SUBSTITUTO_CRIAR, 1)
    print('✓ Patch 2: funções adicionarServicoTecnico e renderizarTecItens adicionadas')
else:
    print('✗ Patch 2: âncora não encontrada')

# ============================================================
# PATCH 3 — atualiza criarChamado() para enviar itens[]
# ============================================================

ANCORA_PAYLOAD_SERVICO = '''    // Se for suporte técnico: precisa de um serviço do catálogo
    if (tipoChamadoAtual === 'suporte_tecnico') {
        const sid = document.getElementById('novoServico').value;
        if (!sid) {
            mostrarErro('Selecione um serviço técnico do catálogo');
            return;
        }
        payload.servico_id = parseInt(sid, 10);
    }'''

SUBSTITUTO_PAYLOAD_SERVICO = '''    // Se for suporte técnico: envia lista de itens
    if (tipoChamadoAtual === 'suporte_tecnico') {
        if (_tecItensForm.length === 0) {
            // Tenta usar o select se não tiver itens adicionados
            const sid = document.getElementById('novoServico').value;
            if (!sid) {
                mostrarErro('Adicione ao menos um serviço técnico');
                return;
            }
            payload.servico_id = parseInt(sid, 10);
        } else {
            payload.itens = _tecItensForm.map(i => ({
                servico_id: i.servico_id,
                quantidade: i.quantidade
            }));
        }
    }'''

if ANCORA_PAYLOAD_SERVICO in html:
    html = html.replace(ANCORA_PAYLOAD_SERVICO, SUBSTITUTO_PAYLOAD_SERVICO, 1)
    print('✓ Patch 3: criarChamado envia itens[]')
else:
    print('✗ Patch 3: âncora não encontrada')

# ============================================================
# PATCH 4 — limpar _tecItensForm ao fechar modal de novo chamado
# ============================================================

ANCORA_ABRIR_MODAL = '''    document.getElementById('novoPrio').value = 'media';
    document.getElementById('novoCat').value = 'geral';
    document.getElementById('novoServico').value = '';
    document.getElementById('modalNovo').classList.add('active');
}'''

SUBSTITUTO_ABRIR_MODAL = '''    document.getElementById('novoPrio').value = 'media';
    document.getElementById('novoCat').value = 'geral';
    document.getElementById('novoServico').value = '';
    _tecItensForm = [];
    renderizarTecItens();
    document.getElementById('modalNovo').classList.add('active');
}'''

if ANCORA_ABRIR_MODAL in html:
    html = html.replace(ANCORA_ABRIR_MODAL, SUBSTITUTO_ABRIR_MODAL, 1)
    print('✓ Patch 4: _tecItensForm limpa ao abrir modal')
else:
    print('✗ Patch 4: âncora não encontrada')

with open(ARQUIVO, 'w', encoding='utf-8') as f:
    f.write(html)

print('\n✅ Patch tecnico_painel concluído!')
