"""Elementos curtos de cada matéria, partilhados pelo email, pela página e pelos ficheiros de calendário:
  membro_governo(x)  — membro(s) do Governo presentes, tal como a AR os indica na ordem de trabalhos;
  sintese(x)         — síntese muito curta da sessão, tirada da ordem de trabalhos (sem atas, «outros assuntos», tempos);
  pagina_ar(x)       — página própria da matéria ou do órgão no sítio da AR; nunca a agenda geral (agenda.parlamento.pt);
  ics(x, ...)        — evento de calendário (.ics) para acrescentar ao Outlook.
Só se usa o texto publicado pela AR: nada é inferido."""
import re, hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CANAL = 'https://canal.parlamento.pt/'
LX = ZoneInfo('Europe/Lisbon')

# cargos do Governo português como a AR os escreve: «Ministro das Infraestruturas e Habitação, Miguel Pinto Luz, sobre…»,
# «Ministra do Trabalho, Solidariedade e Segurança Social – Maria do Rosário Palma Ramalho»
_CARGO = re.compile(r"\b(Primeir[oa]-Ministr[oa]|Ministr[oa] (?:de Estado(?: e)? )?(?:d[aeo]s? |para (?:[ao]s? )?)|Secretári[oa] de Estado\b)")
_FIM = re.compile(r"\s+(?:sobre|no âmbito|relativ\w*|acerca|a propósito|para efeitos|ao abrigo|em audição|na sequência|conforme)\b|[;:.\n()\[\]]|\s/\s")
_PASTA = set('''Mar Desporto Juventude Ambiente Energia Finanças Estado Administração Pública Negócios Estrangeiros Defesa Nacional Interna
Saúde Trabalho Social Segurança Solidariedade Habitação Infraestruturas Economia Coesão Territorial Agricultura Cultura Educação Ciência
Inovação Justiça Presidência Parlamentares Assuntos Reforma Digital Digitalização Modernização Igualdade Comunidades Portuguesas Turismo
Comércio Serviços Mobilidade Florestas Pescas Desenvolvimento Regional Planeamento Ensino Superior Trabalho Emprego Formação Profissional
Consumidor Europeus Europeu Gabinete Ministro Primeiro-Ministro Adjunto Coordenação Legislação Comunicação Média Proteção Civil Administração
Local Valorização Interior Alimentação Inclusão Ação Climática Tecnologias Indústria Mercados Orçamento Tesouro Fiscais Investimento'''.split())
_ESTRANGEIRO = re.compile(r"(Vice-Primeir|Embaixad|Comissári|Parlamento Europeu|Ucrânia|Espanha|França|Alemanha|Brasil|Angola|Moçambique|Cabo Verde|Itália|Reino Unido|Estados Unidos)", re.I)

def _e_nome(t):
    pal = t.split()
    return 2 <= len(pal) <= 7 and pal[0][:1].isupper() and not any(w in _PASTA for w in pal) and all(w[:1].isupper() or w in ('de', 'da', 'do', 'das', 'dos', 'e') for w in pal)

def membros_governo(x):
    """Membros do Governo referidos na ordem de trabalhos, como pares (cargo, nome); nome vazio quando a AR não o escreve."""
    texto = ' / '.join([x.get('interveniente') or '', x.get('tema') or '', x.get('ordemTrabalhos') or ''])
    achados = {}                                            # cargo -> nome (o primeiro com nome ganha)
    for m in _CARGO.finditer(texto):
        if _ESTRANGEIRO.search(texto[max(0, m.start() - 30):m.start()]): continue
        resto = texto[m.start():m.start() + 200]
        f = _FIM.search(resto, len(m.group(1)))
        trecho = resto[:f.start()] if f else resto
        if _ESTRANGEIRO.search(trecho): continue
        nome = ''
        partes = re.split(r'\s*[–—]\s*|\s+-\s+', trecho, maxsplit=1)
        if len(partes) == 2 and _e_nome(partes[1].split(',')[0].strip()):
            cargo, nome = partes[0], partes[1].split(',')[0].strip()
        else:
            cargo = partes[0]
            pedacos = [q.strip() for q in cargo.split(',')]
            for i in range(1, len(pedacos)):                  # o nome é o primeiro pedaço depois da vírgula que já não é pasta
                if _e_nome(pedacos[i]):
                    cargo, nome = ', '.join(pedacos[:i]), pedacos[i]; break
        cargo = re.sub(r'\s+', ' ', cargo).strip(' ,-–')
        if len(cargo) < 8: continue
        chave = cargo.lower()
        if chave not in achados or (nome and not achados[chave][1]): achados[chave] = (cargo, nome)
    return list(achados.values())

def membro_governo(x, maximo=2):
    vistos = [f'{c}, {n}' if n else c for c, n in membros_governo(x)]
    if not vistos and re.search(r'(^|\n|/)\s*GOV\s*(\n|/|$)', x.get('ordemTrabalhos') or ''):
        return 'Governo (intervenção prevista)'
    extra = len(vistos) - maximo
    return ' · '.join(vistos[:maximo]) + (f' e mais {extra} membro{"s" if extra > 1 else ""} do Governo' if extra > 0 else '')

_RUIDO = re.compile(r"^(ORDEM DO DIA|\d{1,2}H\d{0,2}.*|Tempos.*|\d+(\.º)? Dia|º Dia|Relator[a]?:.*|Total|Notas?\b.*|Nota:.*|\d+ ?m(\s?\d+)?|GOV|PSD|PS|CH|IL|L|PCP|BE|CDS(-PP)?|CDSP-PP|PAN|JPP|DURP.*|"
                    r"(Parte )?[IVX]+( Parte)?|Parte [IVX]+|Informações|Outros assuntos|Comunicações.*|Aprovação d[ao]s? (proposta de )?(ata|ordem do dia).*|"
                    r"Apreciação e votação da ata.*|Datas das próximas.*|Ponto único:?|Conselheiros|Deputad[oa] relator.*|Debate na Generalidade|Debate na Especialidade|Orçamento do Estado para \d{4}|Validação das deliberações.*)$", re.I)

_TEMPOS = re.compile(r'podem transferir|tempo que lhes|minutos (ao|a cada|para)|\bGP e DURP\b|grelha de tempos|sujeito a alteração|pedidos de esclarecimento|inicia(m)?-se|por ordem (crescente|decrescente)|a que se seguem', re.I)

def _limpa(l):
    l = l.strip()
    if _RUIDO.match(l.rstrip(' .;:')): return ''
    l = re.sub(r'^\s*(\d+(\.\d+)*|[A-Za-z]|[IVX]+)\s*[-–.)]\s*', '', l)
    l = re.sub(r'^Ponto único:\s*', '', l, flags=re.I)
    l = l.strip(' ;:/').strip()
    return '' if _RUIDO.match(l.rstrip(' .;:')) else l.rstrip('.;: ')

def sintese(x, limite=140):
    """Primeiros pontos substantivos da ordem de trabalhos, sem repetir o tema."""
    ot = x.get('ordemTrabalhos') or x.get('resumo') or ''
    tema = (x.get('tema') or '').lower()
    pontos = []
    ot = re.sub(r'\n\s*(?=[a-zà-ú])', ' ', ot)              # linha partida a meio da frase («pelouro\nda Transição»)
    ot = re.sub(r'\[(?:audi[cç][aã]o )?conjunt[ao][^\])]*[\])]', '', ot, flags=re.I)   # «[conjunta com …]» ou «[… )»
    ot = re.split(r'\n\s*(?:Delega[cç][aã]o|Convidad[oa]s|Participantes)\s*:', ot)[0]   # a lista da delegação não é o assunto            # a junção já vai na linha da comissão
    for l in re.split(r'\n|\s/\s', ot):
        l = _limpa(l)
        if len(l) < 4 or _RUIDO.match(l) or _TEMPOS.search(l) or re.fullmatch(r'Delega[cç][aã]o:?|Convidad[oa]s?:?|Participantes:?', l): continue
        if l.lower() in tema or (len(l) > 25 and l.lower()[:40] in tema): continue
        if any(l.lower() in p.lower() for p in pontos): continue
        pontos.append(l)
        if sum(len(p) for p in pontos) > limite * 0.6 or len(pontos) == 2: break
    s = '; '.join(pontos)
    # o membro do Governo já vai na sua própria linha: «Audição do Ministro X, Nome, sobre…» → «Audição sobre…»
    s = re.sub(r'\s+d[ao] (?:Primeir[oa]-Ministr[oa]|Ministr[oa]|Secretári[oa] de Estado)\b.*?(?=\s+(?:sobre|no âmbito|ao abrigo|relativ\w*|acerca)\b|;|$)', '', s)
    s = re.sub(r',\s+(?=sobre|no âmbito)', ' ', s)
    if len(s) > limite: s = s[:limite].rsplit(' ', 1)[0].rstrip(',;:–- ') + '…'
    return s

def pagina_ar(x):
    """Página própria no sítio da AR (da matéria ou do órgão). A agenda geral não conta: o conteúdo dela já vai no email."""
    cands = [l.get('url') for l in (x.get('ligacoes') or [])] + [x.get('ligacao')]
    for u in cands:
        if u and 'parlamento.pt' in u and 'agenda.parlamento.pt' not in u:
            return u, ('página da comissão' if '/sites/com/' in u else 'página na AR')
    return None, None

def _inicio(x):
    h = re.match(r'(\d{1,2})h(\d{2})?', x.get('hora') or '')
    hh, mm = (int(h.group(1)), int(h.group(2) or 0)) if h else (9, 0)
    return datetime.fromisoformat(x['data'][:10]).replace(hour=hh, minute=mm, tzinfo=LX)

def _esc(s):
    return re.sub(r'([,;\\])', r'\\\1', s or '').replace('\n', '\\n')

def _dobra(linha):
    b = linha.encode('utf-8'); out = []
    while len(b) > 74:
        corte = 74
        while (b[corte] & 0xC0) == 0x80: corte -= 1      # não partir caracteres acentuados
        out.append(b[:corte].decode()); b = b' ' + b[corte:]
    out.append(b.decode()); return '\r\n'.join(out)

def vevento(x, pagina_url=''):
    ini = _inicio(x)
    fim = ini + timedelta(hours=2)
    utc = lambda d: d.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')
    uid = f"ar-{x.get('id_ar') or hashlib.md5((x['data'] + x['tema']).encode()).hexdigest()[:12]}@ar-preview"
    gov, sin = membro_governo(x), sintese(x)
    pag, _ = pagina_ar(x)
    desc = [x.get('tipoLabel') or '']   # inclui «conjunta com …» nas audições conjuntas
    if gov: desc.append('Governo: ' + gov)
    if sin: desc.append('Síntese: ' + sin)
    desc += [
             'Página na AR: ' + pag if pag else '',
             'Emissões em direto (quando houver): ' + CANAL,
             'AR Preview: ' + pagina_url if pagina_url else '',
             'Hora de fim indicativa; a agenda da AR pode mudar.']
    seg = [t.strip() for t in (x.get('tipoLabel') or '').split('·') if not t.strip().startswith('conjunta com')]
    sala = seg[-1] if len(seg) >= 3 and not seg[-1].startswith('Reunião') else ''
    if x.get('hora'):
        quando = [f'DTSTART:{utc(ini)}', f'DTEND:{utc(fim)}']
    else:   # a AR não publica hora (audiências dos grupos parlamentares, visitas): evento de dia inteiro, não às 9h
        d0 = datetime.fromisoformat(x['data'][:10]); quando = [f"DTSTART;VALUE=DATE:{d0:%Y%m%d}", f"DTEND;VALUE=DATE:{d0 + timedelta(days=1):%Y%m%d}"]
        desc[-1] = 'A AR não publicou hora para esta entrada; a agenda da AR pode mudar.'
    linhas = ['BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{utc(datetime.now(LX))}'] + quando + [
              f"SUMMARY:{_esc('AR · ' + x['tema'])}",
              f"LOCATION:{_esc('Assembleia da República' + (' · ' + ('Sala das Sessões' if sala == 'Plenário' else sala) if sala else ''))}",
              f"DESCRIPTION:{_esc(chr(10).join(d for d in desc if d))}",
              f'URL:{pag or CANAL}', 'TRANSP:TRANSPARENT', 'END:VEVENT']
    return '\r\n'.join(_dobra(l) for l in linhas)

def ics(itens, pagina_url='', nome='AR Preview', subscricao=False):
    cab = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//SGGov Suporte à Decisão//AR Preview//PT', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', f'X-WR-CALNAME:{_esc(nome)}']
    if subscricao:   # calendário subscrito: o Outlook volta a lê-lo de tempos a tempos
        cab += ['X-WR-TIMEZONE:Europe/Lisbon', 'X-PUBLISHED-TTL:PT6H', 'REFRESH-INTERVAL;VALUE=DURATION:PT6H',
                f"X-WR-CALDESC:{_esc('Matérias Imediato e Vigilância da agenda da Assembleia da República (AR Preview). Atualização automática.')}"]
    return '\r\n'.join(cab + [vevento(x, pagina_url) for x in itens] + ['END:VCALENDAR']) + '\r\n'

def cal_nome(x):
    """Nome do ficheiro .ics da matéria (docs/cal/…), estável entre atualizações."""
    return f"{x.get('id_ar') or hashlib.md5((x['data'] + x['tema']).encode()).hexdigest()[:12]}.ics"

def outlook_web(x, pagina_url=''):
    """Ligação que abre a reunião já preenchida no Outlook na web (Microsoft 365): basta carregar em «Guardar»."""
    from urllib.parse import urlencode
    ini = _inicio(x); fim = ini + timedelta(hours=2)
    gov, sin = membro_governo(x), sintese(x)
    pag, _ = pagina_ar(x)
    corpo = '\n'.join(t for t in [x.get('tipoLabel') or '', 'Governo: ' + gov if gov else '', sin,
                                   'Página na AR: ' + pag if pag else '', 'AR Preview: ' + pagina_url if pagina_url else ''] if t)
    q = {'path': '/calendar/action/compose', 'rru': 'addevent', 'subject': 'AR · ' + x['tema'],
         'startdt': ini.isoformat(), 'enddt': fim.isoformat(), 'location': 'Assembleia da República', 'body': corpo[:900]}
    if not x.get('hora'):   # sem hora publicada pela AR: dia inteiro
        q.update(allday='true', startdt=x['data'][:10], enddt=x['data'][:10])
    return 'https://outlook.office.com/calendar/0/deeplink/compose?' + urlencode(q)
