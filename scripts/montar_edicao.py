"""Passo 2 — monta ou ATUALIZA dados/agenda.json a partir da recolha do dia (dados/triagem_proposta.json).

* Semana nova  → nova edição (número + 1).
* Mesma semana → atualização: mantém as classificações e fichas já feitas; marca as matérias
  novas («novo»), as que mudaram de ordem de trabalhos («alterado») e as que deixaram de constar («retirado»).
* dados/correcoes.csv (chave;uo;pertinencia;assunto;expressoes) — correções da revisão humana (UPE), aplicadas sempre por cima;
  expressoes = expressões de pesquisa separadas por | (ex.: Lusa|Luísa Meireles).
* Escreve dados/triagem_semana.csv para a revisão e, no GitHub Actions, a saída nova_semana=sim|nao.
"""
import json, pathlib, datetime, sys, os, csv, re
from zoneinfo import ZoneInfo

tri_p, ag_p = pathlib.Path('dados/triagem_proposta.json'), pathlib.Path('dados/agenda.json')
cor_p, csv_p = pathlib.Path('dados/correcoes.csv'), pathlib.Path('dados/triagem_semana.csv')
def saida(k, v):
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write(f'{k}={v}\n')

if not tri_p.exists():
    print('Sem recolha nova — mantém-se a edição em vigor.'); saida('nova_semana', 'nao'); sys.exit(0)
tri = json.loads(tri_p.read_text(encoding='utf-8'))
ant = json.loads(ag_p.read_text(encoding='utf-8')) if ag_p.exists() else {}
if ant and tri['inicio'] < ant['edicao']['inicio']:
    print('A recolha é de uma semana anterior à edição em vigor — ignorada.'); saida('nova_semana', 'nao'); sys.exit(0)

DIAS = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
d = datetime.date.fromisoformat
def rotulo(s): x = d(s); return f"{DIAS[x.weekday()]}, {x.day} {MESES[x.month-1][:3]}"
def extenso(x, ano=True): return f"{x.day} de {MESES[x.month-1]}" + (f" de {x.year}" if ano else '')
def chave(i):
    if i.get('id_ar'): return f"ar-{i['id_ar']}"          # identificador da própria AR: estável mesmo que mude a hora
    return re.sub(r'\s+', ' ', f"{i['data']}|{i.get('hora','')}|{(i.get('orgao') or i.get('tema',''))[:80]}").strip().lower()

agora = datetime.datetime.now(ZoneInfo('Europe/Lisbon'))
hoje = agora.date().isoformat()
ini, fim = d(tri['inicio']), d(tri['fim'])
semana = f"{extenso(ini, False)} a {extenso(fim)}" if ini.month != fim.month else f"{ini.day} a {extenso(fim)}"
nova_semana = not ant or tri['inicio'] > ant['edicao']['inicio']
preliminar = bool(ant) and not nova_semana and ant['edicao'].get('estado') == 'preliminar'   # 1.ª recolha real de uma edição feita à mão

def base(i):
    x = {k: i.get(k, '') for k in ('tema', 'data', 'hora', 'interveniente', 'tipoLabel', 'resumo', 'ordemTrabalhos', 'orgao', 'id_ar')}
    x.update(chave=chave(i), dataLabel=rotulo(i['data']), tipo=i.get('tipo', []), uo=i.get('uo', []), pertinencia=i.get('pertinencia', 'Registo'), criterio=i.get('criterio', []),
             periodo='Manhã' if (i.get('hora') or '99')[:2] < '13' else 'Tarde',
             ligacoes=[{'titulo': 'Agenda parlamentar', 'url': i['ligacao']}] if i.get('ligacao') else [])
    # o nome da comissão passa para a linha do tipo («Comissão de Orçamento, Finanças e Administração Pública · Reunião n.º 31 · Sala 1»),
    # para não se perder quando o título passa a dizer quem é ouvido
    if x['orgao'] and (x['tipoLabel'] or '').startswith('Comissões Parlamentares'):
        x['tipoLabel'] = x['orgao'] + x['tipoLabel'][len('Comissões Parlamentares'):]
    return x

_AUD = re.compile(r'(?:Parte I\s+)?(Audi(?:ção|ência)(?: conjunta)? (?:d[aeo]s?|com (?:[ao]s? )?).+?)(?=,?\s+(?:no âmbito|sobre|relativ|acerca|a propósito|responsável)\b|[;\[]|\.\s|\.$|$)')
def titulo_regras(x):
    """Título das reuniões de comissão cujo tema é só o nome da comissão: quem é ouvido, tal como a AR o escreve
    («Audiência da Associação Nacional das Farmácias (ANF) — Orçamento do Estado 2027»). Só texto publicado pela AR."""
    t, org = (x.get('tema') or '').strip(), (x.get('orgao') or '').strip()
    if (t != org and not x.get('tituloRegras')) or not re.match(r'(Comissão|Subcomissão)\b', org): return None
    ot = (x.get('ordemTrabalhos') or '').strip()
    m = _AUD.match(re.sub(r'\s*\n\s*', ' ', ot[:500]))   # a AR parte as linhas a meio da frase
    if not m: return None
    q = re.sub(r'\s+', ' ', m.group(1)).strip(' ,.-–')
    if len(q) > 110: q = q[:110].rsplit(' ', 1)[0] + '…'
    if re.search(r'Orçamento do Estado para (20\d\d)', ot[:400]):
        q += ' — Orçamento do Estado ' + re.search(r'Orçamento do Estado para (20\d\d)', ot[:400]).group(1)
    return q

novos_itens = [base(i) for i in tri['itens']]

# audições conjuntas: a AR publica a mesma audição em cada comissão envolvida (ex.: Comissão de Infraestruturas e Comissão de
# Orçamento, à mesma hora). Fica uma só linha — a da comissão setorial — com a indicação «conjunta com …».
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sintese import membros_governo
PRI = {'Imediato': 0, 'Vigilância': 1, 'Registo': 2}
def quem(x):
    ot = (x.get('ordemTrabalhos') or '').strip()
    if not re.match(r'Audi(ção|ência)', ot): return None
    m = membros_governo(x)
    if m: return m[0][0].lower()
    e = re.match(r'Audi(?:ção|ência)(?: conjunta)? d[aeo]s? (.+?)(?:,|\s+no âmbito|\s*[–-]|$)', ot)
    return re.sub(r'\W+', ' ', e.group(1).lower()).strip()[:60] if e else None
def juntar(lista):
    grupos, fora = {}, []
    for x in lista:
        q = quem(x)
        ot = (x.get('ordemTrabalhos') or '')
        # audição conjunta sem membro do Governo (ex.: uma comissária europeia ouvida por três comissões): junta-se pelo início do texto
        t0 = re.sub(r'^parte i\b\s*', '', re.sub(r'\W+', ' ', ot.lower()).strip())
        if not q and re.match(r'audi[cç][aã]o|audi[eê]ncia', t0):
            q = 'ot:' + t0[:70]
        if q: grupos.setdefault((x['data'], x.get('hora'), q), []).append(x)
        else: fora.append(x)
    out, absorvidas = list(fora), set()
    for g in grupos.values():
        if len(g) == 1: out.append(g[0]); continue
        g.sort(key=lambda x: 'Orçamento, Finanças' in (x.get('tema') or ''))   # a comissão setorial primeiro
        p, outros = dict(g[0]), g[1:]
        p['conjunta'] = [o['tema'] for o in outros]
        p['tipoLabel'] = (p.get('tipoLabel') or '') + ' · conjunta com ' + ' e '.join(p['conjunta'])
        linhas = (p.get('ordemTrabalhos') or '').split('\n')
        for o in outros:
            linhas += [l for l in (o.get('ordemTrabalhos') or '').split('\n')[1:] if l.strip() and l not in linhas]   # nomes dos membros do Governo, etc.
            p['uo'] = sorted(set(p.get('uo', [])) | set(o.get('uo', [])))
            if PRI.get(o.get('pertinencia'), 2) < PRI.get(p.get('pertinencia'), 2): p['pertinencia'] = o['pertinencia']
            p['criterio'] = list(dict.fromkeys(p.get('criterio', []) + o.get('criterio', [])))
            p.setdefault('ids_ar', [p.get('id_ar')]).append(o.get('id_ar'))
            absorvidas.add(o['chave'])
        p['ordemTrabalhos'] = '\n'.join(linhas)
        out.append(p)
    out.sort(key=lambda x: (x['data'], x.get('hora') or '99'))
    return out, absorvidas
novos_itens, ABSORVIDAS = juntar(novos_itens)

# o que já se sabia das semanas seguintes (classificação do Amália ou da revisão humana, expressões, cobertura, ficha) não se perde:
# passa para a nova edição quando a semana chega, e mantém-se de uma recolha para a outra
fut_ant = {x.get('chave') or chave(x): x for x in ant.get('futuro', [])}
HERDA = ('varrimento', 'expressoes', 'amalia', 'validado', 'cobertura')
def herdar(x, v):
    if not v: return
    for k in HERDA:
        if v.get(k) and not x.get(k): x[k] = v[k]
    if v.get('validado') and v.get('uo'): x['uo'], x['pertinencia'] = v['uo'], v['pertinencia']
    elif v.get('amalia') and v.get('uo') and not x.get('uo'): x['uo'] = v['uo']      # Amália: só a unidade; a prioridade é das regras
    if v.get('amalia') and not v.get('validado'): x['tema'] = v.get('tema', x['tema'])
if nova_semana or preliminar:
    itens = novos_itens
    ed = {'numero': ant.get('edicao', {}).get('numero', 0) + (0 if preliminar else 1), 'ano': ini.year, 'semana': semana, 'inicio': tri['inicio'], 'fim': tri['fim'],
          'fecho': hoje, 'fechoLabel': extenso(agora.date()), 'alteracoes': []}
    fichas = ant.get('fichas', {}) if preliminar else {}
    n_novo = n_alt = n_ret = 0
    for x in itens:
        herdar(x, fut_ant.get(x['chave']))
        if x.get('varrimento') and x['varrimento'] in ant.get('fichas', {}): fichas[x['varrimento']] = ant['fichas'][x['varrimento']]
    if preliminar:   # herda fichas, unidades e ligações da edição preliminar (mesmo dia e hora, ou mesmo dia e assunto)
        velhos = ant['destaques'] + ant['agenda']
        def pal(t): return {w for w in re.findall(r'[a-zà-ú0-9]{5,}', (t or '').lower())}
        for x in itens:
            v = next((o for o in velhos if not o.get('manual') and o['data'] == x['data'] and o.get('hora') == x.get('hora')), None) \
                or next((o for o in velhos if not o.get('manual') and o['data'] == x['data'] and len(pal(o['tema']) & pal(x['tema'] + ' ' + x.get('ordemTrabalhos', ''))) >= 3), None)
            if v:
                if v.get('varrimento'): x['varrimento'] = v['varrimento']
                if v.get('ligacoes') and not x['ligacoes']: x['ligacoes'] = v['ligacoes']
                if v.get('uo'): x['uo'], x['pertinencia'] = v['uo'], v['pertinencia']   # a classificação feita à mão prevalece sobre as regras
        itens += [o for o in velhos if o.get('manual')]   # prazos e notas acrescentados à mão mantêm-se
else:
    ed = dict(ant['edicao']); fichas = ant.get('fichas', {})
    antigos = {x.get('chave') or chave(x): x for x in ant['destaques'] + ant['agenda']}
    vistos, itens, n_novo, n_alt = set(), [], 0, 0
    for x in novos_itens:
        a = antigos.get(x['chave'])
        if a:
            vistos.add(x['chave'])
            y = dict(a); y.pop('retirado', None)
            if not a.get('validado') and not a.get('amalia'):   # sem revisão humana nem Amália: as regras (atualizadas) voltam a classificar
                y['uo'], y['pertinencia'], y['criterio'] = x['uo'], x['pertinencia'], x.get('criterio', [])
            elif not a.get('validado'):   # vista pelo Amália: prioridade sempre pelas regras; unidade das regras, ou a do Amália se as regras não derem nenhuma
                y['pertinencia'] = x['pertinencia']
                y['uo'] = x['uo'] or a.get('uo', [])
                y['criterio'] = x.get('criterio', []) + [c for c in a.get('criterio', []) if c.startswith('unidade pelo Amália')]
            for k in ('hora', 'interveniente', 'tipoLabel', 'ligacoes'):
                y[k] = x[k] or a.get(k, '')
            if x.get('conjunta'): y['conjunta'], y['ids_ar'] = x['conjunta'], x.get('ids_ar', [])
            if x.get('conjunta') and not a.get('conjunta'):
                y['ordemTrabalhos'] = x['ordemTrabalhos']        # junção de audição conjunta: não é alteração da AR
            elif x['ordemTrabalhos'] and x['ordemTrabalhos'] != a.get('ordemTrabalhos'):
                y['ordemTrabalhos'] = x['ordemTrabalhos']
                if not a.get('amalia'): y['resumo'] = x['resumo']
                y['alterado'] = hoje; n_alt += 1
            itens.append(y)
        else:
            herdar(x, fut_ant.get(x['chave']))
            x['novo'] = hoje; itens.append(x); n_novo += 1
    n_ret = 0
    for k, a in antigos.items():
        if k in ABSORVIDAS: continue                       # passou a fazer parte de uma audição conjunta: não é retirada
        if k not in vistos and a.get('manual'):
            itens.append(a)                                  # acrescentados à mão: a AR não os publica, não se retiram
        elif k not in vistos and (a.get('data') or '9999') < hoje:
            # já aconteceu: o sítio da AR só publica de hoje em diante, por isso desaparecer da fonte não é ser retirado
            y = dict(a)
            if y.get('retirado') and y['retirado'] > y.get('data', ''): y.pop('retirado')   # desfaz retiradas por este motivo
            itens.append(y)
        elif k not in vistos:
            y = dict(a)
            if not y.get('retirado'): y['retirado'] = hoje; n_ret += 1
            itens.append(y)
    if n_novo or n_alt or n_ret:
        ed.setdefault('alteracoes', []).append({'data': hoje, 'novos': n_novo, 'alterados': n_alt, 'retirados': n_ret})

for x in itens: x.setdefault('chave', chave(x))

fut = []
for i in tri.get('futuro', []):
    y = base(i); herdar(y, fut_ant.get(y['chave'])); fut.append(y)
fut, _ = juntar(fut)
for y in fut:   # fichas das semanas seguintes acompanham a matéria
    if y.get('varrimento') and y['varrimento'] in ant.get('fichas', {}): fichas.setdefault(y['varrimento'], ant['fichas'][y['varrimento']])

# título pelas regras quando o tema é só o nome da comissão (o Amália e a revisão humana prevalecem)
for x in itens + fut:
    if x.get('amalia') or x.get('validado'): continue
    t = titulo_regras(x)
    if t: x['tema'], x['tituloRegras'] = t, True

# correções manuais da revisão humana (prevalecem sempre)
if cor_p.exists():
    for r in csv.DictReader(cor_p.open(encoding='utf-8-sig'), delimiter=';'):
        k = (r.get('chave') or '').strip().lower()
        for x in itens + fut:      # também as semanas seguintes
            if x.get('chave') == k:
                if r.get('uo') is not None and r.get('uo').strip() != '':
                    x['uo'] = [u.strip() for u in re.split(r'[,|]', r['uo']) if u.strip() and u.strip() != '-']   # aceita vírgula ou |
                if (r.get('pertinencia') or '').strip(): x['pertinencia'] = r['pertinencia'].strip()
                if (r.get('assunto') or '').strip(): x['tema'] = r['assunto'].strip()
                if (r.get('expressoes') or '').strip(): x['expressoes'] = [e.strip() for e in r['expressoes'].split('|') if e.strip()]
                x['validado'] = True
                x['criterio'] = ['revisão humana (correcoes.csv)']

ed.update(atualizado=agora.isoformat(timespec='minutes'), atualizadoLabel=f"{extenso(agora.date(), False)}, {agora:%Hh%M}")
primeira = (ed.get('alteracoes') or [{}])[0].get('data') if ed.get('alteracoes') else None
if not nova_semana: ed['desdeLabel'] = extenso(d(ed['fecho']), False)
ativos = [x for x in itens if not x.get('retirado')]
por_rever = sum(1 for x in ativos if not x.get('validado') and x['pertinencia'] != 'Registo')
if por_rever:
    ed.update(estado='Classificação automática', aviso='A prioridade de cada matéria segue os critérios descritos no botão «i». As fichas de fundo mediático reúnem notícias do Radar de Notícias, com síntese e natureza atribuídas automaticamente pelo Amália, sem verificação de números.')
else:
    ed.pop('estado', None); ed.pop('aviso', None)

ordem = lambda x: (x['data'], x.get('hora') or '99')
nova = {k: ant[k] for k in ('produto', 'tagline', 'unidades', 'disclaimer', 'metodologia', 'pedidos') if k in ant}
nova['futuro'] = sorted(fut, key=lambda x: (x['data'], x.get('hora') or '99'))
nova['calendarizacao'] = tri.get('calendarizacao', [])
nova['produto'] = 'AR Preview'
nova.update(edicao=ed, fichas=fichas,
            destaques=sorted([x for x in itens if x['pertinencia'] == 'Imediato'], key=ordem),
            agenda=sorted([x for x in itens if x['pertinencia'] != 'Imediato'], key=ordem))
ag_p.write_text(json.dumps(nova, ensure_ascii=False, indent=1), encoding='utf-8')

with csv_p.open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['chave', 'data', 'hora', 'tema', 'uo', 'pertinencia', 'expressoes', 'noticias_60d', 'estado', 'revisto'])
    for x in sorted(itens, key=ordem):
        w.writerow([x['chave'], x['data'], x.get('hora', ''), x['tema'], ','.join(x['uo']), x['pertinencia'], '|'.join(x.get('expressoes') or []), (x.get('cobertura') or {}).get('n', ''),
                    'retirado' if x.get('retirado') else 'novo' if x.get('novo') else 'alterado' if x.get('alterado') else '', 'sim' if x.get('validado') else ''])

saida('nova_semana', 'sim' if nova_semana else 'nao')
print(f"{'Nova edição' if nova_semana else 'Atualização da edição'} n.º {ed['numero']} ({semana}): "
      f"{len(nova['destaques'])} destaques, {len(nova['agenda'])} na agenda; hoje: +{n_novo} novas, {n_alt} alteradas, {n_ret} retiradas; {por_rever} por rever")
