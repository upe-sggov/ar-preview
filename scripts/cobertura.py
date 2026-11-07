"""Cobertura mediática de TODAS as matérias, sem IA: procura no arquivo do Radar de Notícias (OCS nacionais acompanhados
pelo Radar, últimos 60 dias, incluindo notícias não marcadas) as notícias sobre o assunto de cada matéria e grava em cada uma
x['cobertura'] = {n7, n7ant, n, dias, ref, metodo, ultimas:[{data, fonte, titulo, url}]}:
  n7 = notícias nos últimos 7 dias; n7ant = nos 7 dias anteriores (tendência); n = total em 60 dias.
É também o «cesto» de notícias que o Amália usa nas fichas.
Uso: python scripts/cobertura.py [--local pasta_com_ficheiros_do_radar]"""
import json, gzip, re, sys, io, os, pathlib, datetime, unicodedata, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sintese import sintese, membro_governo, membros_governo

RADAR = 'https://raw.githubusercontent.com/upe-sggov/radar-noticias/main/'
ESTRANGEIROS = ('.br', '.cv', '.ao', '.mz', '.gw', '.st', '.tl', '.mo', '.es', '.fr', '.it', '.de', '.uk', '.com.br')
DIAS = 60
VAZIAS = set('''comissao comissoes parlamentar parlamentares audicao audicoes reuniao apreciacao votacao votacoes requerimento
requerimentos projeto projetos proposta propostas resolucao discussao relatorio relatorios parecer pareceres plenario
grupo trabalho trabalhos governo ministro ministra secretario secretaria estado assuntos sobre outros informacoes deputado
deputada relator relatora prazo prazos envio sessao legislativa iniciativa iniciativas apresentacao nomeacao distribuicao
direitos liberdades garantias atividades plano orcamento ordem sinalizada sinalizado
para pela pelo pelas pelos como mais entre desde este esta estes estas esse essa isso isto seus suas nossa nosso
quando onde qual quais cada todo toda todos todas outra outro outras tambem ainda apos ante contra durante segundo
janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro
segunda terca quarta quinta sexta sabado domingo hoje ontem amanha semana data datas numero alteracao alteracoes
continuacao debate generalidade especialidade encerramento'''.split())

def norm(s): return ''.join(c for c in unicodedata.normalize('NFD', (s or '').lower()) if unicodedata.category(c) != 'Mn')

def ler(nome, local):
    if local: return (pathlib.Path(local) / nome).read_bytes()
    return urllib.request.urlopen(RADAR + nome, timeout=120).read()

def corpus(local=None):
    arts = []
    for nome in ('corpus.json', 'arquivo.json'):
        try: arts += json.loads(ler(nome, local))['noticias']
        except Exception as e: print('aviso:', nome, e)
    hoje = datetime.date.today()
    meses = sorted({(hoje - datetime.timedelta(days=i)).strftime('%Y-%m') for i in range(0, DIAS + 1, 10)})
    for m in meses:
        try:
            with gzip.open(io.BytesIO(ler(f'meses/{m}.jsonl.gz', local)), 'rt', encoding='utf-8') as f:
                arts += [json.loads(l) for l in f if l.strip()]
        except Exception as e: print('aviso:', m, e)
    limite = (hoje - datetime.timedelta(days=DIAS)).isoformat()
    vistos, out = set(), []
    for a in arts:
        k = (a.get('ligacao') or '', norm(a.get('titulo'))[:90] + '|' + (a.get('fonte') or ''))
        if (a.get('data') or '')[:10] < limite or k[0] in vistos or k[1] in vistos: continue
        dom, fonte = (a.get('dominio') or ''), (a.get('fonte') or '')
        if '(' in fonte or dom.endswith(ESTRANGEIROS) or any(s in (dom + ' ' + norm(fonte)) for s in ('brasil', 'mocambique', 'cartamz', 'angola', 'macau')): continue   # só OCS nacionais
        vistos.update(k); t = norm((a.get('titulo') or '') + ' ' + (a.get('resumo') or ''))
        a['_t'] = t; a['_w'] = set(re.findall(r'[a-z0-9]+', t)); out.append(a)
    return out

def so_orgao(x):
    """O tema é só o nome do órgão («Comissão de Infraestruturas, Mobilidade e Habitação»): o assunto está na ordem de trabalhos."""
    t = (x.get('orgao') or x.get('tema') or '').strip()   # o Amália reescreve o tema; o nome do órgão fica em «orgao»
    # comissões permanentes; as de inquérito e os grupos de trabalho já trazem o assunto no próprio nome
    return bool(re.match(r'(Comissão|Subcomissão)\b', t)) and 'Inquérito' not in t and not re.search(r'[:—]', t) and len(t) <= 80

NOMES_SEMANA = {}   # cargo -> nome, de todas as reuniões da edição (a AR nem sempre repete o nome em cada comissão)

def registar_nomes(itens):
    for x in itens:
        for cargo, nome in membros_governo(x):
            if nome: NOMES_SEMANA.setdefault(norm(cargo), nome)

_GERAIS_CARGO = {'ministro', 'ministra', 'estado', 'nacional', 'secretario', 'secretaria', 'adjunto', 'adjunta', 'primeiro', 'primeira'}
def pastas_governo(x):
    """Palavras da pasta dos ministros ouvidos («Defesa», «Educação», «Habitação»), para ligar o nome ao setor."""
    out = set()
    for cargo, _ in membros_governo(x):
        if re.match(r'(Primeir|Ministr)', cargo):
            out |= {w for w in re.findall(r'[a-z]+', norm(cargo)) if len(w) >= 5 and w not in _GERAIS_CARGO}
    return out

def nomes_governo(x):
    """Apelidos dos membros do Governo ouvidos («Pinto Luz»): o nome escrito nesta reunião ou, na falta dele, o que a AR
    publica para o mesmo cargo noutra reunião da semana (audições conjuntas com a Comissão de Orçamento, por exemplo)."""
    out = []
    membros = membros_governo(x)
    principais = [m for m in membros if re.match(r'(Primeir|Ministr)', m[0])] or membros   # o ministro ouvido; os secretários de Estado só se não houver ministro
    for cargo, nome in principais:
        nome = nome or NOMES_SEMANA.get(norm(cargo), '')
        pal = [w for w in nome.split() if w[:1].isupper()]
        if len(pal) >= 2: out.append(norm(' '.join(pal[-2:])))
    return list(dict.fromkeys(out))

_ENT = re.compile(r'Audi(?:ência|ção)(?: conjunta)? d[aeo]s? (.+?)(?=,?\s+(?:no âmbito|sobre|relativ|acerca|a propósito|para)\b|[;\n]|$)')
def entidades(x):
    """Entidades ouvidas («Associação Nacional das Farmácias (ANF)», «ANMP – Associação Nacional Municípios Portugueses»):
    nome por extenso e sigla, para procurar no título e resumo das notícias. Membros do Governo ficam de fora (têm regra própria)."""
    out = []
    for m in _ENT.finditer(x.get('ordemTrabalhos') or ''):
        t = m.group(1).strip()
        if re.match(r'(Primeir[oa]-Ministr|Ministr|Secretári)', t): continue
        siglas = re.findall(r'\b([A-Z][A-Z0-9]{2,})\b', t)
        nome = re.sub(r'\([^)]*\)|\b[A-Z][A-Z0-9]{2,}\b\s*[-–]?', ' ', t)
        nome = re.sub(r'\s+', ' ', nome).strip(' -–,')
        if len(nome.split()) >= 2: out.append(norm(nome))
        out += [s_ for s_ in siglas if s_ not in ('GOV', 'XVII', 'XVI', 'COM', 'OE')]
    return list(dict.fromkeys(out))

def assunto(x):
    """Texto do assunto: o do Amália, se houver; senão o tema; nas reuniões de comissão cujo tema é só o nome do órgão,
    a síntese da ordem de trabalhos (sem o nome do membro do Governo, que entra à parte)."""
    if (x.get('amalia') or {}).get('assunto'): return x['amalia']['assunto']
    return sintese(x, limite=200) if so_orgao(x) else (x.get('tema') or '')

def termos(texto):
    """Termos de pesquisa a partir do ASSUNTO: palavras significativas e pares de palavras seguidas
    (no texto das notícias podem ter até duas palavras curtas no meio: «conflito de interesses»)."""
    if isinstance(texto, dict): texto = assunto(texto)
    ws = [w for w in re.findall(r'[a-z0-9]+', norm(texto)) if len(w) >= 4 and w not in VAZIAS and not w.isdigit()]
    sig = list(dict.fromkeys(ws))[:12]
    pares = list(dict.fromkeys(f'{a} {b}' for a, b in zip(ws, ws[1:])))[:10]
    return sig, pares

def _par_rx(par, folga=True):
    a, b = par.split(' ', 1)
    if not folga: return re.compile(rf'\b{re.escape(a)} {re.escape(b)}\b')     # como antes: palavras seguidas
    return re.compile(rf'\b{re.escape(a)}\W+(?:[a-z]{{1,3}}\W+){{0,2}}{re.escape(b)}\b')

# matérias recorrentes reconhecidas no texto da AR: expressões de pesquisa automáticas, quando ninguém as definiu
PADROES = [
    (r'or[cç]amento do estado para (20\d\d)', lambda m: [f'Orçamento do Estado para {m.group(1)}', f'OE{m.group(1)}', f'OE {m.group(1)}']),
    (r'\bOE ?(20\d\d)\b', lambda m: [f'Orçamento do Estado para {m.group(1)}', f'OE{m.group(1)}', f'OE {m.group(1)}']),
    (r'conta geral do estado(?: \(cge\))? (?:de |para )?(20\d\d)', lambda m: [f'Conta Geral do Estado de {m.group(1)}', f'CGE {m.group(1)}', f'CGE de {m.group(1)}', 'Conta Geral do Estado']),
    (r'\bPRR\b|plano de recupera[cç][aã]o e resili[eê]ncia', lambda m: ['PRR', 'Plano de Recuperação e Resiliência']),
    (r'grandes op[cç][oõ]es do plano', lambda m: ['Grandes Opções do Plano', 'Grandes Opções']),
    (r'programa de estabilidade', lambda m: ['Programa de Estabilidade']),
    (r'estado da na[cç][aã]o', lambda m: ['estado da nação']),
]
def expressoes_auto(x):
    # no Plenário a ordem do dia é a matéria; nas comissões o Orçamento aparece como um ponto entre muitos (pareceres setoriais),
    # por isso aí só conta o próprio tema
    plenario = (x.get('orgao') or '').startswith('Plenário') or (x.get('tema') or '').startswith('Plenário')
    txt = ' '.join(filter(None, [x.get('tema'), (x.get('ordemTrabalhos') or x.get('resumo')) if plenario else None]))
    out = []
    for p, f in PADROES:
        m = re.search(p, txt, re.I)
        if m: out += [e for e in f(m) if e not in out]
    return out

def procurar(x, arts):
    # reunião de comissão: o assunto está na ordem de trabalhos (o nome da comissão sozinho só trazia ruído:
    # «Orçamento, Finanças e Administração Pública» apanhava as mesmas notícias genéricas em todas as reuniões)
    return _procurar(x, arts, assunto(x), nomes=so_orgao(x))

GERAL = 150   # notícias em 60 dias a partir das quais uma expressão de pesquisa é demasiado geral

def _procurar(x, arts, texto, nomes=True, folga=True):
    if not x.get('expressoes'):
        auto = expressoes_auto(x)
        if auto: x['expressoes_auto'] = auto
    exps = [norm(e).strip() for e in (x.get('expressoes') or x.get('expressoes_auto') or []) if e and e.strip()]
    # expressões propostas pelo Amália não mandam nas audições: aí a pesquisa é por quem é ouvido (mais precisa);
    # as da revisão humana (correcoes.csv) mandam sempre
    if exps and x.get('amalia') and not x.get('validado') and so_orgao(x) and (membros_governo(x) or entidades(x)):
        exps = []
    if exps and not x.get('validado') and len(exps) > 1:
        # expressões demasiado gerais («Comissão de Inquérito», «Polícia Judiciária», o nome de um ministro) apanham centenas de
        # notícias que não são sobre a matéria: uma expressão que sozinha aparece em mais de GERAL notícias só conta junto com outra
        # expressão da matéria (ex.: «Luís Neves» + «Polícia Judiciária»); as precisas contam sozinhas
        rxs = {e: re.compile(r'\b' + re.escape(e) + r'\b') for e in exps}
        conta = {e: sum(1 for a in arts if rxs[e].search(a['_t'])) for e in exps}
        gerais = {e for e in exps if conta[e] > GERAL}
        if gerais:
            res = []
            for a in arts:
                hit = [e for e in exps if rxs[e].search(a['_t'])]
                if any(e not in gerais for e in hit) or len(hit) >= 2: res.append(a)
            res.sort(key=lambda a: a.get('data', ''), reverse=True)
            return res
    if exps:   # expressões de pesquisa definidas (pelo Amália ou pela revisão humana): muito mais precisas
        rx = re.compile(r'\b(' + '|'.join(re.escape(e) for e in exps) + r')\b')
        res = [a for a in arts if rx.search(a['_t'])]
        res.sort(key=lambda a: a.get('data', ''), reverse=True)
        return res
    sig, pares = termos(texto)
    ents = entidades(x) if nomes else []
    pastas = pastas_governo(x) if nomes else set()
    nomes = nomes_governo(x) if nomes else []
    extra = {norm(e) for p_, f in PADROES for m in [re.search(p_, texto, re.I)] if m for e in f(m)}   # «Orçamento do Estado para 2027», «OE2027»…
    if any('orcamento do estado' in e for e in extra): extra.add('orcamento')
    # siglas procuram-se no texto original, em maiúsculas (ANF, ANMP); nomes por extenso no texto normalizado
    rx_ent = [(e.isupper(), re.compile(r'\b' + re.escape(e) + r'\b')) for e in ents]
    if (len(sig) < 2 or not pares) and not nomes and not rx_ent: return []
    res, sigs, prx = [], set(sig), [_par_rx(e, folga) for e in pares]
    for a in arts:
        s = len(sigs & a['_w'])
        if nomes and any(n in a['_t'] for n in nomes):   # ministro ouvido + o assunto (Orçamento…) ou + a sua pasta
            if s >= 2 or any(e in a['_t'] for e in extra): res.append((20 + s, a)); continue
            if pastas & a['_w']: res.append((10 + s, a)); continue
        if rx_ent:   # entidade ouvida (nome ou sigla, a sigla no texto original) + o assunto
            orig = (a.get('titulo') or '') + ' ' + (a.get('resumo') or '')
            if any(r.search(orig if sigla else a['_t']) for sigla, r in rx_ent) and (not extra or any(e in a['_t'] for e in extra)):
                res.append((8 + s, a)); continue
        if nomes or rx_ent: continue   # audição de alguém: conta só quem é ouvido (com o assunto), não as palavras gerais da ordem de trabalhos
        if s < 2 or not prx: continue
        p = sum(1 for r in prx if r.search(a['_t']))
        if p >= 1 and s >= min(3, len(sigs)):   # exige uma expressão do assunto e quase todas as palavras
            res.append((p * 3 + s, a))
    res.sort(key=lambda r: (r[0], r[1].get('data', '')), reverse=True)
    return [a for _, a in res]

LISTA_MAX = 400   # notícias guardadas por matéria para a lista completa da página (as mais recentes)

def cobertura(x, r, hoje):
    c7, c14 = (hoje - datetime.timedelta(days=7)).isoformat(), (hoje - datetime.timedelta(days=14)).isoformat()
    rs = sorted(r, key=lambda a: a.get('data', ''), reverse=True)
    return {'n': len(r), 'n7': sum(1 for a in r if (a.get('data') or '')[:10] > c7),
            'n7ant': sum(1 for a in r if c14 < (a.get('data') or '')[:10] <= c7),
            'dias': DIAS, 'ref': hoje.isoformat(), 'metodo': 'expressoes' if (x.get('expressoes') or x.get('expressoes_auto')) else 'palavras',
            'ultima': rs[0].get('data', '')[:16] if rs else '',
            'ultimas': [{'data': a.get('data', '')[:10], 'fonte': a.get('fonte'), 'titulo': a.get('titulo'), 'url': a.get('ligacao')} for a in rs[:3]],
            # lista completa (sem IA): [data, fonte, título, ligação]
            'todas': [[a.get('data', '')[:16], a.get('fonte') or '', a.get('titulo') or '', a.get('ligacao') or ''] for a in rs[:LISTA_MAX]]}

if __name__ == '__main__':
    local = sys.argv[sys.argv.index('--local') + 1] if '--local' in sys.argv else None
    p = pathlib.Path('dados/agenda.json'); d = json.loads(p.read_text(encoding='utf-8'))
    arts = corpus(local)
    registar_nomes(d['destaques'] + d['agenda'] + d.get('futuro', []))
    print(len(arts), 'notícias no cesto (últimos', DIAS, 'dias)')
    hoje = datetime.date.today()
    resultados = {}
    for x in d['destaques'] + d['agenda'] + d.get('futuro', []):     # também as semanas seguintes já publicadas
        if x.get('retirado'): continue
        r = procurar(x, arts)
        x['cobertura'] = cobertura(x, r, hoje); x.pop('_ligacoes', None)
        if x.get('varrimento'): resultados.setdefault(x['varrimento'], []).extend(r)
    # fichas: notícias novas desde que a ficha foi feita ou revista (sem IA; a ficha não é reescrita aqui)
    for k, r in resultados.items():
        f = d.get('fichas', {}).get(k)
        if not f: continue
        datas = sorted({a.get('data', '')[:16] for a in r})
        base = f.setdefault('base', {'ultima': datas[-1] if datas else '', 'em': hoje.isoformat()})   # fichas antigas: começa a contar a partir de agora
        f['novas'] = sum(1 for dt in datas if dt > (base.get('ultima') or ''))
    # nota de metodologia (substitui a versão anterior, se existir)
    NOTA = ('Cobertura mediática: contagem das notícias dos órgãos de comunicação social nacionais acompanhados pelo Radar de Notícias '
            'da UPE cujo título ou resumo refere o assunto (pelas expressões de pesquisa da matéria ou, na sua falta, pelas palavras do assunto, '
            'contagem indicativa; nas reuniões de comissão, cujo tema é só o nome da comissão, o assunto é o da ordem de trabalhos e contam '
            'também o nome do membro do Governo ouvido — o escrito nessa reunião ou o que a AR publica para o mesmo cargo noutra reunião '
            'da semana — e o nome ou a sigla da entidade ouvida, sempre junto com o assunto; o nome do ministro conta também junto com palavras da sua pasta). Mostra-se o número dos últimos 7 dias, a comparação com os 7 dias anteriores e o total em 60 dias; '
            'a lista completa das notícias encontradas está disponível em cada matéria. As fichas de fundo mediático analisam uma amostra '
            'escolhida ao longo dos 60 dias (dias de maior cobertura, diversidade de órgãos e notícias mais recentes).')
    d['metodologia'] = [m for m in d.get('metodologia', []) if not m.startswith('Cobertura mediática:')] + [NOTA]
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    for x in d['destaques'] + d['agenda'] + d.get('futuro', []):
        if 'cobertura' in x: print(f"{x['cobertura'].get('n7', 0):>4} /{x['cobertura']['n']:>5}  {x['pertinencia'][:3]}  {x['data']}  {x['tema'][:60]}")
