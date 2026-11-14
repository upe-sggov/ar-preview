"""Reuniões cuja ordem de trabalhos não diz o assunto («Informações; Propostas de deliberação; Outros assuntos»):
as expressões de pesquisa do fundo mediático são as fixadas pela UPE em dados/regras_uo.json › pertinencia › fundo_mediatico_fixo.
Corre sempre, sem o Amália (o Amália só é chamado quando há matérias novas)."""
import json, pathlib
p = pathlib.Path('dados/agenda.json')
if not p.exists(): raise SystemExit
dados = json.loads(p.read_text(encoding='utf-8'))
regras = json.loads(pathlib.Path('dados/regras_uo.json').read_text(encoding='utf-8'))
import re
FIXO = [(c, f['expressoes']) for f in regras.get('pertinencia', {}).get('fundo_mediatico_fixo', []) for c in f.get('comissoes', [])]
# por assunto: só nas matérias com ficha (Imediato e Vigilância), quando o tema ou a ordem de trabalhos o referem
ASSUNTO = [(re.compile(f['assunto'], re.I), f['expressoes']) for f in regras.get('pertinencia', {}).get('fundo_mediatico_fixo', []) if f.get('assunto')]
n = 0
for x in dados['destaques'] + dados['agenda'] + dados.get('futuro', []):
    fx = next((e for c, e in FIXO if (x.get('orgao') or '').startswith(c)), None)
    if not fx and x.get('pertinencia') in ('Imediato', 'Vigilância') and not x.get('validado'):
        fx = next((e for rx, e in ASSUNTO if rx.search((x.get('tema') or '') + ' ' + (x.get('ordemTrabalhos') or ''))), None)
    if fx and x.get('expressoes') != fx:
        x['expressoes'], x['expressoesFixas'] = list(fx), True; n += 1
p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
print(n, 'matérias com expressões fixas')
