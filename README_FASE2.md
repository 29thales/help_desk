# FASE 2 — Área do Técnico + Ciclo atribuir/puxar/transferir/devolver

Implementação completa da Fase 2. Requer a **Fase 1 já aplicada** (colunas
`tecnico_id`, `motivo_devolucao`, tabela `chamado_transferencias`).

---

## Como aplicar

1. Faça backup manual do banco (`sistema_chamados.db`) antes.
2. Descompacte o ZIP na raiz do projeto, sobrescrevendo os arquivos.
3. Reinicie o servidor (`python main.py`).

**Não há migration nova** — a Fase 2 só usa campos que a Fase 1 já criou.

---

## Arquivos

```
sistema_chamados_22_04_2026/
├── main.py                    (ATUALIZADO - novas rotas HTML, /api/usuario-logado)
├── auth.py                    (ATUALIZADO - /me retorna tipo_usuario)
├── models/
│   ├── user.py                (sem mudança vs Fase 1 — incluído por segurança)
│   └── chamado.py             (sem mudança vs Fase 1 — incluído por segurança)
├── routes/
│   ├── chamados.py            (ATUALIZADO - filtros por perfil, novos endpoints)
│   ├── usuarios.py            (ATUALIZADO - /tecnicos público)
│   └── tecnico.py             (NOVO - /resumo)
└── templates/
    ├── tecnico_painel.html    (NOVO - área do técnico)
    ├── login.html             (ATUALIZADO - redireciona por tipo)
    ├── chamados.html          (ATUALIZADO - coluna Técnico, modais atribuir/transferir/devolver/histórico)
    ├── dashboard.html, clientes.html, faturamento.html, servicos.html, usuarios.html
                                (ATUALIZADOS - guarda redireciona não-admin)
```

---

## O que foi implementado

### Backend

**Novos endpoints em `/api/chamados/`:**
- `POST /{id}/puxar` — técnico elegível puxa da fila aberta (vira `atribuido`)
- `POST /{id}/atribuir` — admin atribui técnico a chamado (body: `tecnico_id`)
- `POST /{id}/transferir` — admin ou dono do chamado transfere (body: `tecnico_id`, `motivo`)
- `POST /{id}/devolver` — volta pra fila aberta (body: `motivo` obrigatório ≥10 chars)
- `GET /{id}/transferencias` — histórico de transferências do chamado

**Alterações em endpoints existentes:**
- `GET /api/chamados/`:
  - Aceita `?fila=minha` ou `?fila=aberta` (e aliases `?meus=true`, `?fila_aberta=true`)
  - Filtragem por perfil: admin vê tudo, técnico vê só os dele, cliente vê só os que abriu
  - Fila aberta só visível a técnicos elegíveis ou admin
- `POST /api/chamados/` — técnico que abre chamado já se auto-atribui (`status='atribuido'`)
- `POST /api/chamados/{id}/historico` — técnico só pode adicionar histórico em chamados atribuídos a ele (403 caso contrário); ao adicionar primeiro histórico o status vira `em_atendimento`
- **Transferir e devolver** geram entrada automática no histórico (🔄/🔙) para auditoria

**Novos endpoints auxiliares:**
- `GET /api/usuarios/tecnicos` — lista técnicos ativos (qualquer autenticado pode consultar, só devolve `id/nome/email/pode_ver_fila_aberta`)
- `GET /api/tecnico/resumo` — estatísticas do técnico logado
- `GET /tecnico/painel` — página HTML

### Frontend

**`tecnico_painel.html`** — área completa do técnico:
- Cards: chamados ativos, em atendimento, fila aberta (se elegível), tempo trabalhado
- Seção "Meus Chamados" com ações: Atender / Transferir / Devolver
- Seção "Fila Aberta" (só pra elegíveis) com botão "📌 Puxar"
- Modal de atender (adicionar histórico) — **sem box financeiro, sem botão finalizar**
- Modal de transferir (select de técnicos + motivo)
- Modal de devolver (motivo ≥10 chars)
- Modal de novo chamado (com aviso "será atribuído a você automaticamente")
- Rodapé: "Você não vê valores, faturamento, clientes ou serviços — só sua fila pessoal e a fila aberta."

**`login.html`** — após login, redireciona por tipo:
- `admin` → `/dashboard`
- `tecnico` → `/tecnico/painel`
- `cliente` → `/cliente/painel` (endpoint ainda não existe — Fase 3)

**Telas admin** (dashboard, clientes, chamados, faturamento, servicos, usuarios):
- Guarda JS que redireciona não-admins para `/tecnico/painel` (ou `/` se estado estranho)
- Link "👫 Usuários" no header só aparece pra admin

**`chamados.html` (admin)** — ganhou:
- Coluna "Técnico" na tabela
- Linha "Técnico responsável" no modal de detalhes
- Aviso "Motivo da última devolução" quando aplicável
- Botão "👤 Atribuir técnico" (quando sem técnico) / "🔄 Transferir" + "🔙 Devolver" (quando com técnico)
- Botão "📜 Histórico transferências" com modal listando todas as transferências

---

## Isolamento de valores

O serializador de chamado em `routes/chamados.py` já escondia `valor_total`,
`valor_fixo`, `cliente_valor_hora` e `servico_valor_padrao` para não-admins.
Verifiquei e **nenhum desses campos vaza para o técnico na API** (testado com `curl`).
Na UI do técnico, nenhum elemento menciona R$.

---

## Testes executados

Rodei backend completo + frontend (Playwright):

- ✅ Aliases `?fila=minha` e `?fila=aberta`
- ✅ Técnico elegível puxa chamado → vira `atribuido`
- ✅ Técnico não-elegível recebe 403 ao tentar puxar
- ✅ Não-elegível não vê fila aberta
- ✅ Adicionar histórico em chamado próprio → status vira `em_atendimento`
- ✅ Tentar adicionar histórico em chamado alheio → 403
- ✅ Transferir gera entrada automática 🔄 no histórico
- ✅ Devolver gera entrada automática 🔙 + `motivo_devolucao` salvo
- ✅ Técnico NÃO vê `valor_total`, `valor_fixo`, `cliente_valor_hora`, `servico_valor_padrao`
- ✅ Técnico abre chamado → auto-atribuído a ele com `status='atribuido'`
- ✅ Login admin → `/dashboard`; Login técnico → `/tecnico/painel`
- ✅ Tela admin mostra coluna "Técnico" e o modal tem botões atribuir/transferir/devolver + histórico

---

## O que NÃO foi feito

- Fase 3: Área do Cliente (portal)
- Fase 4: Relatório de comissão mensal

---

## Credenciais (usadas nos testes)

- Admin: `admin@helpdesk.com` / `admin123456` (padrão)
- Técnico elegível: `elegivel@teste.com` / `tec12345` (criado durante testes — pode deletar)
- Técnico não-elegível: `naoeleg@teste.com` / `tec12345` (idem)
