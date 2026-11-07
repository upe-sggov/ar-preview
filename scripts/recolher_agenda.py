"""Passo 1 — recolha diária da Agenda Parlamentar da Assembleia da República.

Fonte principal: https://agenda.parlamento.pt — a mesma exportação «Exportar › Para JSON» do site da agenda, que é a versão
mais atual (o ficheiro dos dados abertos é atualizado com atraso: a 26/10/2026 faltavam-lhe reuniões já publicadas no site).
Fonte de recurso: parlamento.pt › Cidadania › Dados abertos › Agenda Parlamentar › XVII Legislatura › AgendaParlamentar_json.txt,
usada se o site da agenda não responder; a calendarização dos meses seguintes vem sempre dos dados abertos.

Semana-alvo: de segunda a quinta, a semana em curso; de sexta a domingo, a semana seguinte.
Saída: dados/agenda_bruta.json  →  usado por triar.py e montar_edicao.py
Uso: python scripts/recolher_agenda.py [--ficheiro AgendaParlamentar_json.txt] [--semana AAAA-MM-DD]
"""
import json, pathlib, datetime, sys, urllib.request, re, html

URL_AGENDA = "https://app.parlamento.pt/webutils/docs/doc.txt?path=fxkkyG0F2jR%2fL3LMNV0qF1JgWJiaoLvU23RDQflJ4%2fXJwdHaW2uvdFy0D%2bA%2bm7td49uC1M4ipPpx1vOby%2bHpFQjqjUHgC9CR%2fL%2fKZi39QqN%2b8%2bviTj9iPLgwgqj%2b8xe52jxlznSrRwrzeRTK8zv5V8Uu5HBOgvGtaGL%2b1bJWgzGLkV2IqcEYbT7Hpue%2b5vHy5wfR%2bRNZNy9jnEKvaTkW4up7NVxEoZABcdfGv7VRhZ53cHQ1%2fzb1MLTmD9jvqO1kyJ7ePsgv%2bmxt7WeTAPdOiKHCtBSe6DMqL2qcxRHiJsQBIFZcMTamQL95puZga%2bodwh238749aRuSE8hLot%2f6ObkB2VAiDuGX%2fbNlySmM3auUIULk1UWwgozCVOo29y1uySEBmBnvLjk7%2fyMRSSWPDA%3d%3d&fich=AgendaParlamentar_json.txt&Inline=true"
URL_PASTA = "https://www.parlamento.pt/Cidadania/Paginas/DABoletimInformativo.aspx?t=57465a4a5353424d5a576470633278686448567959513d3d"
SECCOES = ('Plenário', 'Comissões Parlamentares', 'Grupo de Trabalho', 'Grupo de Trabalho AR', 'Conferência de Líderes', 'Comissão Permanente')   # o resto (visitas, audiências dos grupos parlamentares, agenda do Presidente) fica de fora

def semana_alvo(hoje=None):
    """De segunda a quinta: a semana em curso. De sexta a domingo: a semana seguinte."""
    hoje = hoje or datetime.date.today()
    seg = hoje - datetime.timedelta(days=hoje.weekday())
    if hoje.weekday() >= 4:
        seg += datetime.timedelta(days=7)
    return seg, seg + datetime.timedelta(days=6)

def descarregar(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (AR Preview; SGGov/DSSD/UPE)'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8-sig')

def obter():
    try:
        return json.loads(descarregar(URL_AGENDA))
    except Exception as e:
        print('Endereço direto falhou (', e, ') — a procurar a ligação na página dos dados abertos')
        pag = descarregar(URL_PASTA)
        m = re.search(r'href="([^"]*fich=AgendaParlamentar_json\.txt[^"]*)"', pag)
        if not m: raise SystemExit('Ligação do AgendaParlamentar_json.txt não encontrada na página dos dados abertos.')
        return json.loads(descarregar(html.unescape(m.group(1))))

SITE = 'https://agenda.parlamento.pt'

def obter_site():
    """Exportação JSON do site agenda.parlamento.pt (o que o botão «Exportar › Para JSON» faz), convertida para o formato
    dos dados abertos (Id, EventStartDate dd/mm/aaaa, EventStartTime, Section, Title, Subtitle, Local, Link, InternetText)."""
    import http.cookiejar, uuid
    abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    cab = {'User-Agent': 'Mozilla/5.0 (AR Preview; SGGov/DSSD/UPE)'}
    ler = lambda url, dados=None, extra={}: abridor.open(urllib.request.Request(url, data=dados, headers={**cab, **extra}), timeout=90).read().decode('utf-8-sig')
    pagina = ler(SITE + '/')
    tok = re.search(r'"XSRF-TOKEN",\s*"([^"]+)"', pagina)
    if not tok: raise RuntimeError('token de exportação não encontrado na página da agenda')
    ids = list(dict.fromkeys(re.findall(r'id="card_(\d+)"', ler(SITE + '/Index?handler=SectionContents'))))
    if not ids: raise RuntimeError('nenhuma reunião na página da agenda')
    fronteira = uuid.uuid4().hex
    corpo = ''.join(f'--{fronteira}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in
                    (('Input.ContentIds', ','.join(ids)), ('Input.Format', 'JSON'))) + f'--{fronteira}--\r\n'
    return converter_site(json.loads(ler(SITE + '/ContentExport?tz=Europe/Lisbon', corpo.encode(), {'XSRF-TOKEN': tok.group(1), 'Content-Type': f'multipart/form-data; boundary={fronteira}'})))

def converter_site(lista):
    out = []
    for x in lista:
        dt = x.get('eventStartDate') or ''
        try: d = datetime.datetime.fromisoformat(dt[:19])
        except ValueError: continue
        out.append({'Id': x.get('id'), 'EventStartDate': d.strftime('%d/%m/%Y'),
                    'EventStartTime': d.strftime('%H:%M:%S') if (d.hour or d.minute) else None,
                    'Section': x.get('section'), 'Title': x.get('title'), 'Subtitle': x.get('subtitle'), 'Local': x.get('local'),
                    'Link': x.get('link'), 'InternetText': x.get('intranetText')})
    return out

def obter_tudo():
    """Site da agenda (principal) + dados abertos (recurso e calendarização dos meses seguintes)."""
    try:
        site = obter_site(); print(f'agenda.parlamento.pt: {len(site)} registos')
    except Exception as e:
        site = None; print('agenda.parlamento.pt indisponível (', e, ') — usam-se só os dados abertos')
    try: abertos = obter()
    except BaseException as e:
        if site is None: raise
        abertos = []; print('dados abertos indisponíveis (', e, ')')
    if site is None: return abertos, 'Dados abertos da Assembleia da República — AgendaParlamentar_json.txt'
    # a página do site só mostra os dias mais próximos (a 7/11/2026 só trazia 9 e 10 de novembro): as reuniões que já estão nos
    # dados abertos e não estão no site entram também; quando estão nos dois, vale a versão do site (mais atual)
    chave = lambda x: (x.get('EventStartDate'), (x.get('EventStartTime') or '')[:5], re.sub(r'\W+', ' ', (x.get('Title') or '')).strip().lower()[:60])
    vistos, chaves = {str(x['Id']) for x in site}, {chave(x) for x in site}
    extra = [x for x in abertos if str(x.get('Id')) not in vistos and chave(x) not in chaves]
    print(f'dados abertos: {len(abertos)} registos, {len(extra)} acrescentados (não estavam no site)')
    return site + extra, 'Agenda Parlamentar da Assembleia da República — agenda.parlamento.pt (exportação JSON), completada pelos dados abertos; calendarização: dados abertos'

def texto(h):
    t = html.unescape(html.unescape(h or ''))
    t = re.sub(r'<br\s*/?>|</p>|</li>', '\n', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    return re.sub(r'[ \t​]+', ' ', re.sub(r'\n\s*\n+', '\n', t)).strip()

def hora(x, txt):
    if x.get('Section') == 'Plenário':                      # no Plenário, a hora certa vem na ordem do dia
        m = re.search(r'\b(\d{1,2})H(\d{2})\b', txt)
        if m: return f"{int(m.group(1)):02d}h{m.group(2)}"
    t = x.get('EventStartTime') or ''
    return f"{int(t[:2]):02d}h{t[3:5]}" if re.match(r'\d{2}:\d{2}', t) else ''   # 09h00, como no site da AR (e para ordenar bem)

def tema(x, txt):
    if x.get('Section') == 'Plenário':
        t = re.sub(r'ORDEM DO DIA|\(sujeito a altera\w+\)|\b\d{1,2}H\d{2}\b|^\s*\d+\s*-\s*', ' ', txt)
        t = re.sub(r'^\d+\s*-\s*', '', re.sub(r'\s+', ' ', t).strip())
        t = re.split(r'\s(?:Proposta|Projeto|Debate na Generalidade|Tempos\b|Notas?\b|GOV \d|\d+\s*-)\s?', t)[0]
        return ('Plenário — ' + t.strip(' -:'))[:120] if t.strip() else 'Plenário'
    return (x.get('OrgDes') or x.get('Title') or '').split(' | ')[0].strip()

def normalizar(bruto, ini, fim):
    saida = []
    for x in bruto:
        if x.get('Section') not in SECCOES: continue
        try: data = datetime.datetime.strptime(x['EventStartDate'], '%d/%m/%Y').date()
        except Exception: continue
        if not (ini <= data <= fim): continue
        txt = texto(x.get('InternetText'))
        saida.append({
            'id_ar': x.get('Id'), 'data': data.isoformat(), 'hora': hora(x, txt),
            'tema': tema(x, txt), 'orgao': (x.get('OrgDes') or x.get('Title') or '').split(' | ')[0].strip(),
            'interveniente': '', 'tipo': [x.get('Section')], 'tipoLabel': ' · '.join(filter(None, [x.get('Section'), x.get('Subtitle'), x.get('Local')])),
            'resumo': txt[:300], 'ordemTrabalhos': txt, 'ligacao': x.get('Link') or '',
        })
    return saida

MESES = {m: i + 1 for i, m in enumerate(['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'])}

def calendarizacao(bruto):
    """«Resumo da Calendarização» da AR (um registo por mês): dias de Plenário, comissões, feriados, jornadas parlamentares."""
    out = []
    for x in bruto:
        if x.get('Section') != 'Resumo da Calendarização': continue
        m = re.search(r'de (\w+) de (\d{4})', x.get('Title') or '')
        if not m or m.group(1).lower() not in MESES: continue
        mes, ano = MESES[m.group(1).lower()], int(m.group(2))
        h = html.unescape(html.unescape(x.get('InternetText') or ''))
        for linha in re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S):
            cel = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', c)).replace('\xa0', ' ').strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', linha, re.S)]
            cel = [c for c in cel if c]
            d = re.match(r'Dia (\d+)', cel[0]) if cel else None
            if not d or len(cel) < 3: continue
            horas = ' · '.join(re.findall(r'\d{1,2}h\d{2}', ' '.join(cel[3:])))
            try: dia = datetime.date(ano, mes, int(d.group(1)))
            except ValueError: continue
            sem = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo'][dia.weekday()]
            if cel[1] and not cel[1].lower().startswith(sem):
                print(f'calendarização: «Dia {d.group(1)} {cel[1]}» não bate com {dia} ({sem}) no resumo de {m.group(1)} de {ano} — ignorado')
                continue                                     # dia da semana da AR não bate com a data: linha não fiável
            out.append({'data': datetime.date(ano, mes, int(d.group(1))).isoformat(), 'diaSemana': cel[1], 'atividade': cel[2], 'horas': horas})
    return sorted({c['data'] + c['atividade']: c for c in out}.values(), key=lambda c: c['data'])

if __name__ == '__main__':
    args = sys.argv[1:]
    hoje = datetime.date.fromisoformat(args[args.index('--semana') + 1]) if '--semana' in args else None
    ini, fim = semana_alvo(hoje)
    if '--ficheiro' in args:
        bruto, fonte = json.loads(pathlib.Path(args[args.index('--ficheiro') + 1]).read_text(encoding='utf-8-sig')), 'ficheiro local'
    else:
        bruto, fonte = obter_tudo()
    itens = normalizar(bruto, ini, fim)
    futuro = normalizar(bruto, fim + datetime.timedelta(days=1), fim + datetime.timedelta(days=70))   # semanas seguintes (o que a AR já publicou)
    cal = calendarizacao(bruto)
    pathlib.Path('dados').mkdir(exist_ok=True)
    pathlib.Path('dados/agenda_bruta.json').write_text(json.dumps({'inicio': ini.isoformat(), 'fim': fim.isoformat(), 'recolha': datetime.datetime.now().isoformat(timespec='minutes'), 'fonte': fonte, 'itens': itens, 'futuro': futuro, 'calendarizacao': cal}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(bruto)} registos na fonte; {len(itens)} para a semana de {ini} a {fim}; {len(futuro)} nas semanas seguintes; {len(cal)} dias de calendarização')
