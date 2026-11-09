"""Reuniões cuja ordem de trabalhos não diz o assunto («Informações; Propostas de deliberação; Outros assuntos»):
as expressões de pesquisa do fundo mediático são as fixadas pela UPE em dados/regras_uo.json › pertinencia › fundo_mediatico_fixo.
Corre sempre, sem o Amália (o Amália só é chamado quando há matérias novas)."""
import json, pathlib
p = pathlib.Path('dados/agenda.json')
if not p.exists(): raise SystemExit
dados = json.loads(p.read_text(encoding='utf-8'))
regras = json.loads(pathlib.Path('dados/regras_uo.json').read_text(encoding='utf-8'))
FIXO = [(c, f['expressoes']) for f in regras.get('pertinencia', {}).get('fundo_mediatico_fixo', []) for c in f['comissoes']]
n = 0
for x in dados['destaques'] + dados['agenda']:
    fx = next((e for c, e in FIXO if (x.get('orgao') or '').startswith(c)), None)
    if fx and x.get('expressoes') != fx:
        x['expressoes'], x['expressoesFixas'] = list(fx), True; n += 1
p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
print(n, 'matérias com expressões fixas')
