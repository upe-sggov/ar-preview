# AR Preview — a semana na Assembleia da República

Agenda parlamentar semanal para os dirigentes da área de Suporte à Decisão da Secretaria-Geral do Governo, triada por prioridade (Imediato, Vigilância, Registo), com cobertura mediática e fichas de varrimento. Desde 2 de novembro de 2026 as matérias não levam etiquetas de unidade orgânica (decisão da Direção).

**Página:** https://upe-sggov.github.io/ar-preview/ (repositório `upe-sggov/ar-preview`; até 30 de outubro de 2026 esteve em `celine-mestre/ar-ahead`)
**Responsável:** Unidade de Pesquisa e Estatísticas (UPE)

---

## O que acontece sozinho

| Quando (hora de Lisboa) | O quê |
|---|---|
| Todos os dias, 7h07 e 18h07 | Recolhe a agenda da AR, atualiza a edição da semana, marca o que é novo, alterado ou retirado, refaz a página e o PDF |
| Segunda-feira de manhã (9h07, com reserva às 9h37 e 11h07) | Envia aos dirigentes a lista de todas as reuniões da semana, com a prioridade, a ligação para a página e para o PDF (sem anexo) e, em cada matéria, a ligação para a AR, o varrimento e o calendário |
| Quando começa uma semana nova | Arquiva a edição anterior e avisa a pessoa da triagem com a lista de matérias a rever |

**Semana-alvo:** de segunda a quinta, a semana em curso; de sexta a domingo, a semana seguinte.

Os horários estão em UTC no workflow. No horário de verão (de março a outubro), subtrai-se 1 às horas dos três `cron`.

---

## Cadeia

```
1. scripts/recolher_agenda.py   dados abertos da AR          → dados/agenda_bruta.json
2. scripts/triar.py             regras (dados/regras_uo.json) → dados/triagem_proposta.json
3. scripts/montar_edicao.py     edição nova ou atualização    → dados/agenda.json
4. scripts/amalia_triagem.py    Amália: assunto e expressões de pesquisa das matérias Imediato e Vigilância
5. scripts/cobertura.py         notícias do Radar de Notícias (60 dias, OCS nacionais) para todas as matérias
6. scripts/amalia_varrimento.py Amália: fichas completas («Imediato») e curtas («Vigilância»)
7. scripts/gerar.py             modelo + dados + histórico   → saida/ar-preview.html
8. scripts/pdf.js               Chromium                      → saida/ar-preview.pdf
9. scripts/resolver_ligacoes.py ligações diretas às notícias (reencaminhamentos do Google Notícias → endereço do jornal; cache em dados/ligacoes.json)
10. scripts/indice_edicoes.py   lista de edições              → docs/edicoes/indice.json
   scripts/calendario.py        ficheiros de calendário (.ics) → docs/cal/<id>.ics e docs/cal/semana.ics
   scripts/email_resumo.py      corpo e assunto do email de segunda-feira
   scripts/sintese.py           membro do Governo, síntese curta e página na AR de cada matéria (usado pelo email e pelos calendários)
```

Tudo corre em `.github/workflows/ar-preview.yml`.

---

## Fonte dos dados

- **Principal: https://agenda.parlamento.pt** — a exportação JSON do próprio site da Agenda Parlamentar (a mesma do botão «Exportar › Para JSON»). É a versão mais atual: a 26/10/2026, o ficheiro dos dados abertos ainda não tinha três reuniões que o site já mostrava (COFAP de 27/10 às 11h00, Grupo de Trabalho para os Assuntos Culturais de 28/10 e o Parlamento dos Jovens remarcado para 29/10 às 9h30).
- **Recurso: dados abertos** (https://www.parlamento.pt/Cidadania/Paginas/DABoletimInformativo.aspx › Agenda Parlamentar › XVII Legislatura › `AgendaParlamentar_json.txt`), usados se o site da agenda não responder. A «Resumo da Calendarização» dos meses seguintes vem sempre daqui.
- O registo de cada recolha (`dados/agenda_bruta.json`, campo `fonte`) diz qual das duas foi usada.

Secções lidas: Plenário, Comissões Parlamentares, Grupo de Trabalho, Grupo de Trabalho AR, Conferência de Líderes e Comissão Permanente. Ficam de fora as audiências dos grupos parlamentares, as visitas, as assistências e o Conselho de Administração.

---

## A página

- **Edição em curso:** calendário mensal, agenda hora a hora e hemiciclo; ao clicar numa matéria abre-se o cartão na gaveta lateral, com a classificação, a cobertura e a lista de notícias (exportável para Excel e imprimível). Os cartões completos ficam ocultos por defeito e mostram-se com um botão; o PDF inclui-os sempre.
- **Seletor «Semanas»**, por cima do calendário:
  - edições anteriores, a cinzento, com ligação para a edição completa;
  - a semana em curso;
  - as semanas seguintes já publicadas pela AR, a verde, ainda sem triagem completa nem varrimento.
- **«Mais à frente»:** reuniões futuras e calendarização da AR.
- **Histórico:** cada edição fica em `docs/edicoes/nNN.html` e `.json`. A n.º 1 é a edição piloto (19 a 25 de outubro de 2026), a n.º 2 a primeira automática. O seletor de semanas lê esse arquivo.
- **Modelo e dados separados:** `modelo/template_cartoes.html` não tem conteúdo, só desenha o `dados/agenda.json`. Para mudar o aspeto, muda-se o modelo; para mudar o conteúdo, muda-se o JSON.

---

## Quem decide «Imediato», «Vigilância» e «Registo»

Critérios da UPE (novembro de 2026), aplicados automaticamente em cada atualização a todas as matérias que não foram revistas por pessoas:

- **Imediato**
  - presença de um **cliente habitual**: Primeiro-Ministro, Ministro de Estado e das Finanças, Ministro da Presidência, Ministro da Economia e da Coesão Territorial, Ministro Adjunto e da Reforma do Estado, e os respetivos secretários de Estado (lista de cargos e nomes em `dados/regras_uo.json` › `pertinencia.clientes`; atualizar em remodelações);
  - matéria que **já teve varrimento próprio entregue** (`dados/varrimentos_entregues.csv`: data;assunto;expressoes;cliente;unidade (a coluna unidade já não é usada) — basta que uma das expressões, separadas por `|`, apareça no tema ou na ordem de trabalhos);
  - **debates do Governo no Plenário** (Orçamento do Estado, interpelações, debates com o Primeiro-Ministro, estado da Nação, moções…; lista em `pertinencia.plenario_imediato`).
- **Vigilância**
  - presença de **outros membros do Governo** (ou tempo atribuído ao Governo no Plenário), comissões de inquérito;
  - **dossiers acompanhados** pela área de Suporte à Decisão (`dados/dossiers.csv`: unidade;dossier;expressoes — a coluna unidade já não é usada).
- **Registo** — o resto, só para conhecimento.

As matérias **não levam etiquetas de unidade** (decisão de 2/11/2026): o campo `uo` continua a ser calculado internamente pelas regras, mas não aparece na página, no PDF, no email nem no calendário. A **revisão humana** (`dados/correcoes.csv`) prevalece sempre e marca a matéria como validada.

**Audições conjuntas** — quando a AR publica a mesma audição em duas ou três comissões à mesma hora (por exemplo a comissão setorial e a de Orçamento), fica uma só linha, a da comissão setorial, com a indicação «conjunta com …».

Cada cartão mostra a linha «Classificação: …» com o termo ou a justificação que decidiu, para a revisão perceber o porquê e corrigir a regra, não só o caso.

---

## Revisão humana

Para corrigir a classificação de uma matéria, acrescenta-se uma linha a `dados/correcoes.csv`:

```
chave;uo;pertinencia;assunto;expressoes
ar-123456;;Vigilância;Conselho das Comunidades Portuguesas;Conselho das Comunidades|CCP
```

- A `chave` aparece em `dados/triagem_semana.csv`.
- A coluna `uo` fica vazia (já não se usam unidades); as expressões de pesquisa separam-se com `|`.
- A correção prevalece em todas as atualizações seguintes e a matéria fica marcada como validada; o Amália nunca a altera.
- Também se aplica às matérias das semanas seguintes (por exemplo, para marcar já como «Imediato» uma grande matéria de novembro).
- As expressões de pesquisa tornam a contagem de notícias precisa.

A agenda vem exclusivamente da Assembleia da República: não se acrescentam matérias à mão (prazos ou lembretes que não constem da agenda da AR ficam de fora).

---

## Varrimento mediático (automático) e Amália

**As notícias vêm sempre e só do Radar de Notícias por área governativa** (`upe-sggov/radar-noticias`): nunca de pesquisa manual nem da memória do modelo. Fichas feitas à mão são retiradas e substituídas pela versão automática. As únicas ligações mantidas nos cartões são as da Assembleia da República.

- **Contagem e lista completa (sem IA):** `cobertura.py` procura, para cada matéria, as notícias dos últimos 60 dias pelas expressões de pesquisa (definidas na revisão, pelo Amália, ou reconhecidas automaticamente para matérias recorrentes como o Orçamento do Estado e a Conta Geral do Estado) e guarda a contagem, a tendência de 7 dias e a lista (até 400, as mais recentes).
- **Fichas (`amalia_varrimento.py`):**
  - «Imediato»: ficha completa com até 20 notícias. «Vigilância»: ficha curta com até 8, que passa a completa quando a cobertura está a subir. As matérias «Imediato» das semanas seguintes também têm ficha com antecedência.
  - A seleção é feita ao longo dos 60 dias: cerca de 40 % da última semana e o resto repartido pelas semanas anteriores na proporção da cobertura, com preferência pelo assunto no título e pela variedade de órgãos e de dias.
  - **O Amália** corre como no Radar de Notícias: pesos abertos (layerx-labs/AMALIA-9B-0626-DPO-GGUF, Apache 2.0) descarregados do Hugging Face e guardados em cache, no próprio servidor do GitHub, sem segredo nem serviço externo. Sem placa gráfica é lento: no máximo 120 minutos de fichas por atualização (`AMALIA_MINUTOS`); o que faltar fica para a seguinte, e entretanto a ficha mostra a seleção de notícias do Radar, sem análise. Se o modelo falhar, as fichas ficam só com as notícias.
  - **Triagem pelo Amália**: escreve o assunto e as expressões de pesquisa das matérias Imediato e Vigilância. A prioridade não é dele: segue sempre os critérios da UPE.
  - **Com o Amália:** a mesma seleção (amostra de até 20/8 notícias: dias de pico, jornais diferentes, as mais recentes), lida pelo Amália: resumo da cobertura, síntese e natureza de cada notícia (Crítica, Relevante, Positiva, Contextual). As restantes ficam na lista completa da página, só com título e jornal e sem etiqueta. Nada vem dos varrimentos feitos pela equipa da UPE.
  - As fichas são refeitas até à segunda-feira da semana da matéria quando há notícias novas, quando passam de curta a completa e quando uma ficha sem notícias passa a ter notícias. A mesma matéria em vários dias (por exemplo, duas sessões do mesmo debate) partilha a ficha.
  - `python scripts/amalia_varrimento.py --verificar` diz o que há para fazer, sem carregar o modelo.
- **Triagem:** `amalia_triagem.py` propõe o assunto e as expressões de pesquisa das matérias Imediato e Vigilância que ainda não os têm.
- **Revisão:** as fichas do Amália não incluem a verificação de números, que fica para revisão humana. Para marcar uma ficha como revista (e impedir que seja reescrita), acrescenta-se `"revista_por": "nome"` à ficha em `dados/agenda.json`; a página passa a mostrar as notícias novas desde a revisão.

---

## Segredos do repositório

Criam-se em Settings › Secrets and variables › Actions › New repository secret.

| Nome | Valor |
|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | endereço remetente |
| `SMTP_PASS` | palavra-passe de aplicação do Google (16 letras, sem espaços) |
| `SMTP_FROM` | já não é usado: o remetente aparece como «AR Preview», com o endereço de `SMTP_USER` |
| `DIRIGENTES_DSSD` | destinatários do email de segunda-feira (chefias da área de Suporte à Decisão), separados por vírgulas |
| `EMAIL_TRIAGEM` | destinatário do aviso de semana nova |

Sem os segredos SMTP, os emails não são enviados e o registo do workflow mostra o texto que seria enviado.

---

## Correr à mão

Actions › AR Preview › Run workflow, com o passo `atualizar` (recolha e publicação) ou `enviar` (email aos dirigentes).

---

## Notas

- O repositório é **público**. A página tem `noindex`, para não aparecer nos motores de pesquisa, mas abre para qualquer pessoa com o endereço, e todo o conteúdo do repositório (dados, regras, histórico) é legível.
- A prioridade e o varrimento são indicativos e estão sujeitos a validação. O varrimento é amostral e não exaustivo.
- **Email de segunda-feira.** Remetente «AR Preview»; assunto «AR Preview n.º N · semana — agenda da Assembleia da República». Mesmo desenho do email do Radar de Notícias (cartão branco, cabeçalho azul, contagem em destaque, rodapé escuro); matérias agrupadas por dia e ordenadas por hora ; cada matéria leva:
  - o membro do Governo presente e uma síntese muito curta, tirados da ordem de trabalhos publicada pela AR (nada é inferido; no Plenário, quando a AR atribui tempo ao Governo, aparece «Governo (intervenção prevista)»);
  - a página da comissão ou da matéria na AR, só quando existe — a agenda geral não, porque o conteúdo dela já vai no email;
  - «adicionar ao calendário», um ficheiro .ics que o Outlook abre como evento (hora de fim indicativa: 2 horas); o botão «Todas no calendário» junta as matérias da semana.
  As emissões não têm ligação própria antecipada: o email indica o Canal Parlamento (canal.parlamento.pt).
- O email usa o logótipo publicado em `docs/logo-sggov-email.png` (o mesmo do Radar de Notícias, com anel branco fino desenhado na imagem, para ficar redondo também no Outlook): os programas de email não mostram imagens embebidas no próprio HTML.
- `scripts/importar_html_antigo.py` converteu a edição piloto (HTML original) para JSON.
