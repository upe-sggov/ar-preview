"""Varrimento mediático AUTOMÁTICO: as notícias das fichas vêm SEMPRE e SÓ do Radar de Notícias por área governativa
(nunca de pesquisa manual nem da memória do modelo). Fichas feitas à mão (sem origem automática) são substituídas.
  * Sem o Amália (--sem-ia): ficha só com a seleção de notícias do Radar (data, órgão, título, ligação), sem análise.
  * Com o Amália: a mesma seleção, lida pelo Amália: resumo factual da cobertura, síntese factual e natureza de cada notícia
    (Crítica, Relevante, Positiva, Contextual — critério em CRITERIO, abaixo); substitui as fichas sem análise.
  Só a amostra é lida e classificada; as restantes notícias da matéria ficam na lista completa da página, só com título e jornal.
  Tudo vem do Radar: nada destas fichas vem dos varrimentos feitos pela equipa, nem lá entra.
Níveis:
  Imediato                              → ficha completa: até 20 notícias (dias de pico, jornais diferentes, as mais recentes);
  Vigilância                            → ficha curta: até 8 notícias;
  Vigilância com cobertura «a subir»    → passa a ficha completa (3 ou mais notícias na última semana e mais do que na anterior);
                                          uma ficha completa não volta a curta (não se perde o que já foi reunido);
  Registo                               → sem ficha (fica a contagem e a lista completa, calculadas por cobertura.py).

Amostra escolhida ao longo dos 60 dias, e não só as mais recentes: cerca de 40 % da última semana e o resto repartido
pelas semanas anteriores na proporção da cobertura (os dias de pico pesam mais), com preferência pelas notícias que têm
o assunto no título e pela variedade de órgãos de comunicação social.

Quando se (re)faz uma ficha:
  * matéria sem ficha;
  * ficha sem notícias, quando entretanto há notícias;
  * ficha com muito menos notícias do que cabem (menos de 3/4 do máximo do nível ou do total encontrado) — ex.: feita antes de a pesquisa encontrar as notícias;
  * ficha curta de uma matéria que passou a pedir ficha completa;
  * até à segunda-feira da semana da matéria (inclusive), quando saíram notícias novas desde a ficha
    (3 ou mais; ou 1 ou mais se a ficha ainda tem menos notícias do que o máximo).
Fichas revistas por pessoas (sem «Amália» em gerado_por) NUNCA são reescritas: cobertura.py conta as notícias novas
desde a revisão e a página mostra-o.
Semanas seguintes: também as matérias «Imediato» já publicadas pela AR (grandes matérias com antecedência).
Uma chamada ao modelo por ficha; grava a cada ficha, para que nada se perca se o tempo acabar.
Os «Pontos de atenção» (verificação de números na fonte primária) NÃO são gerados: são trabalho humano.
Uso: python scripts/amalia_varrimento.py [--verificar] [--local pasta_do_radar]
  --verificar: só diz se há trabalho (código 0) ou não (código 1), sem carregar o modelo."""
import json, pathlib, re, sys, datetime, math, collections, os, time
from cobertura import corpus, procurar, norm, registar_nomes

MAXN = {'completa': 20, 'curta': 8}
SEM_IA = '--sem-ia' in sys.argv
GERADO_RADAR = 'Radar de Notícias — seleção automática'
GERADO_AMALIA = 'Radar de Notícias — amostra lida e classificada pelo Amália'
ROT = {'critica': 'Crítica', 'relevante': 'Relevante', 'positivo': 'Positiva', 'contexto': 'Contextual'}
CRITERIO = """Natureza de cada notícia em relação a ESTA matéria:
- "critica": crítica, acusação, polémica, falha ou problema que pode ser levantado contra o Governo ou a medida nesta reunião;
- "relevante": diretamente sobre a matéria (medidas, números, posições dos intervenientes), sem polémica;
- "positivo": diretamente sobre a matéria, em tom favorável (anúncio, resultado, apoio, elogio);
- "contexto": enquadramento geral ou menção lateral."""
SIS = "Assistente de apoio à decisão (Secretaria-Geral do Governo). Português europeu. Responde só com JSON. Usa só o que está nas notícias dadas, sem acrescentar factos."
HOJE = datetime.date.today()

def nivel_desejado(x):
    if x['pertinencia'] == 'Imediato': return 'completa'
    c = x.get('cobertura') or {}
    if c.get('n7', 0) >= 3 and c.get('n7', 0) > c.get('n7ant', 0): return 'completa'   # tema a aquecer
    return 'curta'

def segunda(iso):
    d = datetime.date.fromisoformat(iso[:10]); return d - datetime.timedelta(days=d.weekday())

def motivo(x, f):
    """Porque é que esta matéria precisa de ficha nova (ou None)."""
    c = x.get('cobertura') or {}
    if not f: return 'sem ficha'
    if f.get('revista_por'): return None                                                # revista por pessoas: não se toca
    if f.get('origem') not in ('radar', 'amalia'): return 'ficha manual substituída pela automática (Radar)'
    if SEM_IA and f.get('origem') == 'amalia': return None                             # sem modelo, não se estraga a análise feita
    if not SEM_IA and f.get('origem') == 'radar': return 'acrescentar a análise do Amália'
    if not f.get('fundo') and c.get('n', 0) > 0: return 'havia zero notícias, agora há'
    if f.get('origem') == 'amalia' and any(n.get('natureza') not in ROT for n in f.get('fundo') or []): return 'falta a natureza das notícias'
    # a ficha tem de ser uma escolha da lista completa da matéria: se a pesquisa mudou e as notícias da ficha já lá não estão, refaz-se
    todas = c.get('todas') or []
    if f.get('fundo') and todas and len(todas) < 400:
        urls, pares = {t[3] for t in todas}, {(t[1], t[0][:10]) for t in todas}
        fora = sum(1 for n in f['fundo'] if n.get('url') not in urls and (n.get('fonte'), (n.get('data') or '')[:10]) not in pares)
        if fora * 3 > len(f['fundo']): return f'{fora} notícias da ficha já não estão na lista da matéria (pesquisa mudou)'
    cabe = min(MAXN.get(f.get('nivel'), 8), c.get('n', 0))
    if len(f.get('fundo', [])) < cabe and len(f.get('fundo', [])) < cabe * 0.75:      # ficha muito abaixo do que o Radar já tem
        return f"ficha com {len(f.get('fundo', []))} notícias, o Radar tem {c.get('n', 0)}"
    if f.get('nivel') == 'curta' and nivel_desejado(x) == 'completa': return 'passa a ficha completa'
    if HOJE <= segunda(x['data']):
        novas = f.get('novas', 0); cheia = len(f.get('fundo', [])) >= MAXN.get(f.get('nivel'), 8)
        if novas >= 3 or (novas >= 1 and not cheia): return f'{novas} notícias novas'
    return None

def texto_radar(n_sel, c, n_total=None):
    """Frase de abertura das fichas sem Amália (aparece no PDF, por cima das notícias escolhidas)."""
    n = c.get('n', n_total or 0); n7 = c.get('n7', 0)
    return (f"Das {n} notícias que o Radar de Notícias encontrou sobre esta matéria nos últimos 60 dias ({n7} na última semana), "
            f"estas são {n_sel}, escolhidas automaticamente: os dias com mais notícias, jornais diferentes e as mais recentes. "
            f"A lista completa está no AR Preview. Sem análise: a síntese e a natureza de cada notícia chegam quando o Amália correr.")

def alvos(d):
    """Matérias da semana (Imediato e Vigilância) e matérias Imediato das semanas seguintes, por esta ordem."""
    semana = [x for x in d['destaques'] + d['agenda'] if x['pertinencia'] in ('Imediato', 'Vigilância') and not x.get('retirado')]
    semana.sort(key=lambda x: (x['pertinencia'] != 'Imediato', x['data']))
    futuras = [x for x in d.get('futuro', []) if x['pertinencia'] == 'Imediato']
    out = []
    for x in semana + futuras:
        m = motivo(x, d['fichas'].get(x.get('varrimento') or ''))
        if m: out.append((x, m))
    return out

def escolher(x, r, maxn):
    """Amostra ao longo dos 60 dias: última semana + semanas anteriores na proporção da cobertura; variedade de órgãos."""
    if len(r) <= maxn: return sorted(r, key=lambda a: a.get('data', ''))
    exps = [norm(e) for e in (x.get('expressoes') or x.get('expressoes_auto') or []) if e.strip()]
    no_titulo = (lambda a: any(e in norm(a.get('titulo')) for e in exps)) if exps else (lambda a: False)
    c7 = (HOJE - datetime.timedelta(days=7)).isoformat()
    grupos = collections.defaultdict(list)
    for a in r: grupos['recente' if a.get('data', '')[:10] > c7 else segunda(a['data']).isoformat()].append(a)
    quotas = {}
    if grupos.get('recente'): quotas['recente'] = min(len(grupos['recente']), math.ceil(maxn * 0.4))
    resto = maxn - sum(quotas.values()); antigos = {k: v for k, v in grupos.items() if k != 'recente'}
    tot = sum(len(v) for v in antigos.values())
    if tot and resto > 0:
        bruto = {k: resto * len(v) / tot for k, v in antigos.items()}
        for k in bruto: quotas[k] = min(len(antigos[k]), int(bruto[k]))
        for k in sorted(bruto, key=lambda k: bruto[k] - int(bruto[k]), reverse=True):   # maior resto
            if sum(quotas.values()) >= maxn: break
            if quotas[k] < len(antigos[k]): quotas[k] += 1
    escolhidas, fontes, dias = [], collections.Counter(), collections.Counter()
    def tirar(cands, k):
        pico = collections.Counter(a.get('data', '')[:10] for a in cands).most_common(1)[0][0] if cands else ''
        livres = list(cands)
        for _ in range(k):
            if not livres: break
            melhor = max(livres, key=lambda a: (no_titulo(a), -fontes[a.get('fonte')], -dias[a.get('data', '')[:10]], a.get('data', '')[:10] == pico, a.get('data', '')))
            livres.remove(melhor); escolhidas.append(melhor); fontes[melhor.get('fonte')] += 1; dias[melhor.get('data', '')[:10]] += 1
    for k, q in quotas.items(): tirar(grupos[k], q)
    if len(escolhidas) < maxn: tirar([a for a in r if a not in escolhidas], maxn - len(escolhidas))
    return sorted(escolhidas, key=lambda a: a.get('data', ''))

def ficha(x, r, perguntar, json_da_resposta):
    nivel = nivel_desejado(x); maxn = MAXN[nivel]
    nots = escolher(x, r, maxn)
    meta = f"{x.get('tipoLabel','')} · {x['dataLabel']}{', ' + x['hora'] if x.get('hora') else ''} · UO de referência: {' · '.join(x['uo']) or '—'}"
    datas = sorted({a.get('data', '')[:16] for a in r})
    f = {'titulo': x['tema'], 'meta': meta, 'nivel': nivel, 'origem': 'radar' if perguntar is None else 'amalia',
         'gerado_por': GERADO_RADAR if perguntar is None else GERADO_AMALIA,
         'atencao': [], 'blocos': [], 'tabelas': [], 'fundo': [],
         'amostra': {'analisadas': len(nots), 'encontradas': len(r)},
         'base': {'ultima': datas[-1] if datas else '', 'em': HOJE.isoformat()}, 'novas': 0}
    if not nots:
        f['enquadramento'] = f"Sem notícias sobre esta matéria nos órgãos de comunicação social acompanhados pelo Radar de Notícias nos últimos 60 dias (expressões usadas: {', '.join(x.get('expressoes') or x.get('expressoes_auto') or ['palavras do assunto'])}). A ficha é refeita automaticamente quando surgirem notícias."
        return f
    if perguntar is None:   # sem o Amália: só a seleção de notícias do Radar
        for a in nots:
            f['fundo'].append({'data': a.get('data', '')[:10], 'fonte': a.get('fonte'), 'url': a.get('ligacao'), 'sintese': a.get('titulo') or ''})
        f['enquadramento'] = texto_radar(len(nots), x.get('cobertura') or {}, len(r))
        return f
    lista = '\n'.join(f"{i+1}. [{a.get('data','')[:10]} · {a.get('fonte')}] {a.get('titulo')} — {(a.get('resumo') or '')[:300]}" for i, a in enumerate(nots))
    enq = 'um parágrafo factual (4 a 6 frases) com o que as notícias relatam e como a cobertura evoluiu no período' if nivel == 'completa' else 'duas frases factuais com o que as notícias relatam'
    r_ = json_da_resposta(perguntar(SIS, f"""Matéria na agenda da Assembleia da República: {x['tema']} ({x['dataLabel']} {x.get('hora','')}).
Resumo: {x.get('resumo','')[:400]}
Cobertura: {len(r)} notícias em 60 dias; abaixo, uma amostra de {len(nots)}, por ordem cronológica.
Notícias numeradas:
{lista}

{CRITERIO}

Devolve {{"enquadramento": "{enq}, só com base nestas notícias", "noticias": [{{"n": 1, "sintese": "1 a 2 frases factuais: o que a notícia relata", "natureza": "critica"|"relevante"|"positivo"|"contexto"}}, ...]}}
Inclui todas as notícias, pela mesma numeração. Se uma notícia não for sobre esta matéria, devolve para ela "natureza": "fora".""", 3200 if nivel == 'completa' else 1100)) or {}
    por_n = {int(n.get('n', 0)): n for n in (r_.get('noticias') or []) if isinstance(n, dict) and str(n.get('n', '')).isdigit()}
    for i, a in enumerate(nots, 1):
        n = por_n.get(i, {})
        if n.get('fora') is True or n.get('natureza') == 'fora': continue
        nat = n.get('natureza') if n.get('natureza') in ROT else 'contexto'
        f['fundo'].append({'data': a.get('data', '')[:10], 'fonte': a.get('fonte'), 'url': a.get('ligacao'), 'sintese': n.get('sintese') or a.get('titulo'),
                           'natureza': nat, 'naturezaLabel': ROT[nat]})
    f['amostra']['analisadas'] = len(f['fundo'])
    f['enquadramento'] = (r_.get('enquadramento') or '').strip() or f"{len(f['fundo'])} notícias analisadas no Radar de Notícias; enquadramento por gerar."
    return f

if __name__ == '__main__':
    p = pathlib.Path('dados/agenda.json'); d = json.loads(p.read_text(encoding='utf-8')); d.setdefault('fichas', {})
    trabalho = alvos(d)
    if '--verificar' in sys.argv:
        for x, m in trabalho: print('·', m, '—', x['data'], x['tema'][:60])
        sys.exit(0 if trabalho else 1)
    # ligações: só as da Assembleia da República (as de notícias vêm do Radar, na ficha e na lista completa)
    for x in d['destaques'] + d['agenda'] + d.get('futuro', []):
        if x.get('ligacoes'): x['ligacoes'] = [l for l in x['ligacoes'] if 'parlamento.pt' in (l.get('url') or '')]
    # fichas automáticas: natureza com os rótulos atuais; sem «impacto para a sessão» (juízo que fica para o varrimento feito pela equipa)
    for f_ in d['fichas'].values():
        if f_.get('origem') in ('radar', 'amalia') and not f_.get('revista_por'):
            for n_ in f_.get('fundo') or []:
                n_.pop('impacto', None)
                if f_['origem'] == 'amalia' and n_.get('natureza') in ROT: n_['naturezaLabel'] = ROT[n_['natureza']]
                elif f_['origem'] == 'radar': n_.pop('natureza', None); n_.pop('naturezaLabel', None)
            f_['gerado_por'] = GERADO_AMALIA if f_['origem'] == 'amalia' else GERADO_RADAR
    # fichas manuais que deixam de ser usadas: retiradas
    usadas = {x.get('varrimento') for x in d['destaques'] + d['agenda'] + d.get('futuro', [])}
    for k in [k for k, f in d['fichas'].items() if f.get('origem') not in ('radar', 'amalia') and not f.get('revista_por')]:
        d['fichas'].pop(k)
        for x in d['destaques'] + d['agenda'] + d.get('futuro', []):
            if x.get('varrimento') == k: x.pop('varrimento')
        print('ficha manual retirada:', k)
    # arrumação das fichas automáticas (as revistas por pessoas nunca se tocam):
    todos_ = d['destaques'] + d['agenda'] + d.get('futuro', [])
    registar_nomes(todos_)   # nomes dos ministros publicados noutras reuniões da semana (pesquisa das notícias)
    auto = lambda k: k in d['fichas'] and not d['fichas'][k].get('revista_por')
    por_ficha = {}
    for x in todos_:
        if x.get('varrimento') and not x.get('retirado'): por_ficha.setdefault(x['varrimento'], []).append(x)
    for k, xs in por_ficha.items():
        # 1) ficha partilhada por reuniões diferentes que não são a mesma matéria (mesmas expressões de pesquisa):
        #    acontecia com nomes feitos de dia + comissão (várias reuniões da mesma comissão no mesmo dia)
        assuntos = {tuple(sorted(x.get('expressoes') or x.get('expressoes_auto') or [])) or ('id', x.get('chave')) for x in xs}
        if len(xs) > 1 and len(assuntos) > 1 and auto(k):
            for x in xs: x.pop('varrimento', None)
            d['fichas'].pop(k, None); print('ficha partilhada por reuniões diferentes — refeita para cada uma:', k)
    for x in todos_:
        # 2) matérias em «Registo» não têm ficha (fica a contagem e a lista completa)
        if x.get('pertinencia') == 'Registo' and x.get('varrimento') and auto(x['varrimento']):
            k = x.pop('varrimento')
            if not any(y.get('varrimento') == k for y in todos_): d['fichas'].pop(k, None)
            print('ficha retirada (matéria em Registo):', x['data'], x['tema'][:50])
    # 3) fichas automáticas que já nenhuma matéria usa
    usadas = {x.get('varrimento') for x in todos_}
    for k in [k for k in d['fichas'] if k not in usadas and auto(k)]:
        d['fichas'].pop(k); print('ficha órfã retirada:', k)
    # frase de abertura das fichas do Radar, sempre com os números atuais da cobertura
    for x in todos_:
        f = d['fichas'].get(x.get('varrimento') or '')
        if f and f.get('origem') == 'radar' and not f.get('revista_por') and f.get('fundo'):
            f['enquadramento'] = texto_radar(len(f['fundo']), x.get('cobertura') or {})
    trabalho = alvos(d)
    if not trabalho:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8'); print('Nada a fazer.'); sys.exit(0)
    if SEM_IA: perguntar = json_da_resposta = None
    else: from amalia import perguntar, json_da_resposta
    local = sys.argv[sys.argv.index('--local') + 1] if '--local' in sys.argv else None
    arts = corpus(local)
    feitas = {}   # a mesma matéria em vários dias (ex.: debate do Orçamento em duas sessões) partilha a ficha
    fim_em = time.time() + 60 * float(os.environ.get('AMALIA_MINUTOS', '0') or 0) if not SEM_IA and os.environ.get('AMALIA_MINUTOS') else None
    for x, m in trabalho:
        if fim_em and time.time() > fim_em:   # sem placa gráfica o modelo é lento: o que faltar fica para a próxima corrida (as fichas do Radar mantêm-se)
            print(f'tempo do Amália esgotado ({os.environ.get("AMALIA_MINUTOS")} min) — {len(trabalho)} fichas pendentes passam para a próxima atualização'); break
        assunto = tuple(sorted(x.get('expressoes') or x.get('expressoes_auto') or [])) or None
        if assunto and assunto in feitas and x['pertinencia'] == feitas[assunto][1]:
            x['varrimento'] = feitas[assunto][0]; print('ficha partilhada ·', x['tema'][:60]); continue
        # nome único: dia + número da AR + tema (o dia e o tema não chegam: a mesma comissão reúne várias vezes no mesmo dia)
        chave = x.get('varrimento') or re.sub(r'[^a-z0-9]+', '-', f"{x['data']}-{x.get('id_ar') or x.get('hora', '')}-{x['tema']}".lower())[:60].strip('-')
        d['fichas'][chave] = ficha(x, procurar(x, arts), perguntar, json_da_resposta)
        if assunto: feitas[assunto] = (chave, x['pertinencia'])
        for y in d['destaques'] + d['agenda'] + d.get('futuro', []):     # a mesma matéria pode aparecer em dois dias
            if y is x or (y.get('chave') and y.get('chave') == x.get('chave')): y['varrimento'] = chave
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')   # grava a cada ficha: se o tempo acabar, nada se perde
        f = d['fichas'][chave]
        print(f"ficha {f['origem']} {f['nivel']} · {f['amostra']['analisadas']} de {f['amostra']['encontradas']} notícias · {m} · {x['tema'][:60]}")
