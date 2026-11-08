"""Ficheiros de calendário (.ics) para o Outlook: um por matéria (docs/cal/<id>.ics) e um com as matérias imediatas e em
vigilância da semana (docs/cal/semana.ics). Abrir o ficheiro no Outlook acrescenta o evento ao calendário de quem o abre.
Horas convertidas para UTC (o Outlook mostra-as na hora local); hora de fim indicativa (2 horas).
Uso: PAGINA_URL=https://… python scripts/calendario.py dados/agenda.json docs/cal"""
import json, sys, os, pathlib
sys.path.insert(0, os.path.dirname(__file__))
from sintese import ics, cal_nome

d = json.loads(open(sys.argv[1], encoding='utf-8').read())
pasta = pathlib.Path(sys.argv[2]); pasta.mkdir(parents=True, exist_ok=True)
url = os.environ.get('PAGINA_URL', 'https://upe-sggov.github.io/ar-preview/')
itens = [x for x in d['destaques'] + d['agenda'] + d.get('futuro', []) if not x.get('retirado') and x.get('data')]
for velho in pasta.glob('*.ics'): velho.unlink()                # só ficam os da edição em vigor
for x in itens:
    (pasta / cal_nome(x)).write_text(ics([x], url), encoding='utf-8', newline='')
semana = [x for x in d['destaques'] + d['agenda'] if not x.get('retirado') and x.get('data') and x.get('pertinencia') in ('Imediato', 'Vigilância')]
def um_por_audicao(xs):   # audição conjunta: a AR publica-a em cada comissão, mas no calendário é um só evento
    vistos = set(); out = []
    for x in xs:
        k = x.get('conjuntaId') and (x['data'], x['conjuntaId'])
        if k and k in vistos: continue
        if k: vistos.add(k)
        out.append(x)
    return out
semana = um_por_audicao(semana)
semana.sort(key=lambda x: (x['data'], x.get('hora') or '99'))
(pasta / 'semana.ics').write_text(ics(semana, url, f"AR Preview · {d['edicao'].get('semana', '')}"), encoding='utf-8', newline='')
# calendário para subscrever (docs/cal/ar-preview.ics): matérias Imediato e Vigilância das duas últimas semanas (edições
# anteriores), da semana em curso e das seguintes já publicadas; o Outlook relê-o sozinho e acompanha as alterações
import datetime, glob
desde = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
PRIMEIRA = 3   # edições anteriores à n.º 3 seguiam outros critérios de prioridade: não entram no calendário subscrito
sub, vistos = [], set()
fontes = [d] + [e for e in (json.loads(open(f, encoding='utf-8').read()) for f in sorted(glob.glob(os.path.join(os.path.dirname(sys.argv[1]), '..', 'docs', 'edicoes', 'n*.json')), reverse=True))
                if e.get('edicao', {}).get('numero', 0) >= PRIMEIRA]
for e in fontes:
    for x in e.get('destaques', []) + e.get('agenda', []) + (e.get('futuro', []) if e is d else []):
        k = x.get('id_ar') or (x.get('data'), x.get('tema'))
        if k in vistos or x.get('retirado') or not x.get('data') or x['data'] < desde or x.get('pertinencia') not in ('Imediato', 'Vigilância'): continue
        vistos.add(k); sub.append(x)
sub = um_por_audicao(sub)
sub.sort(key=lambda x: (x['data'], x.get('hora') or '99'))
(pasta / 'ar-preview.ics').write_text(ics(sub, url, 'AR Preview', subscricao=True), encoding='utf-8', newline='')
print(f'{len(itens)} ficheiros de calendário + semana.ics ({len(semana)} matérias) + ar-preview.ics para subscrever ({len(sub)} matérias)')
