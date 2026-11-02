"""Gera a página de cartões (HTML autónomo) a partir de dados/agenda.json e do modelo.
Embebe também o histórico (edições anteriores em docs/edicoes/*.json), para o calendário
permitir navegar semana a semana: edições anteriores, semana em curso e semanas seguintes.
Uso: python scripts/gerar.py dados/agenda.json saida/ar-preview.html
"""
import sys, pathlib, json
raiz = pathlib.Path(__file__).resolve().parent.parent
dados, destino = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
modelo = (raiz/'modelo'/'template_cartoes.html').read_text(encoding='utf-8')
logo = (raiz/'modelo'/'logo_sggov_b64.txt').read_text().strip()
d = json.loads(dados.read_text(encoding='utf-8'))          # valida o JSON
d['produto'] = 'AR Preview'                                # nome da ferramenta (também nas edições arquivadas)

CAMPOS = ('data', 'hora', 'tema', 'pertinencia', 'uo', 'tipoLabel', 'interveniente', 'id_ar', 'orgao')
hist, pasta = [], raiz/'docs'/'edicoes'

# páginas das comissões no site da AR (ficam depois de a reunião passar; a agenda da AR só mostra de hoje em diante):
# aprendidas das ligações das próprias edições, por nome, número («12.ª Comissão») e sigla («COFAP»)
import re
PAG_COM = {}
for f in [dados] + (sorted(pasta.glob('n*.json')) if pasta.exists() else []):
    try: e = json.loads(f.read_text(encoding='utf-8'))
    except Exception: continue
    for x in e.get('destaques', []) + e.get('agenda', []) + e.get('futuro', []):
        for l in x.get('ligacoes') or []:
            m = re.search(r'/sites/com/XVIILeg/(\d+)([A-Z]+)/', (l or {}).get('url', ''))
            if not m: continue
            u = l['url']
            if x.get('orgao'): PAG_COM.setdefault(x['orgao'].strip(), u)
            PAG_COM.setdefault(f'{m.group(1)}.ª Comissão', u); PAG_COM.setdefault(m.group(2), u)
def pagina_comissao(x):
    txt = ' '.join(filter(None, [x.get('orgao'), x.get('tema'), x.get('tipoLabel')]))
    for k, u in sorted(PAG_COM.items(), key=lambda kv: -len(kv[0])):
        if (k.isupper() and re.search(rf'\b{k}\b', txt)) or (not k.isupper() and k in txt): return u
    return None
for f in sorted(pasta.glob('*.json')) if pasta.exists() else []:
    if f.name == 'indice.json': continue
    try: e = json.loads(f.read_text(encoding='utf-8'))
    except Exception: continue
    ed = e.get('edicao', {})
    if not ed.get('inicio') or ed['inicio'] >= d['edicao']['inicio']: continue   # só semanas anteriores
    itens = []
    for x in e.get('destaques', []) + e.get('agenda', []):
        if x.get('retirado') or not x.get('data'): continue
        i = {k: x.get(k) for k in CAMPOS}; i['uo'] = i['uo'] or []
        i['resumo'] = (x.get('resumo') or '')[:300]
        i['ligacoes'] = [l for l in (x.get('ligacoes') or []) if isinstance(l, dict)][:3]
        if not any('parlamento.pt' in (l.get('url') or '') and 'agenda.parlamento.pt' not in (l.get('url') or '') for l in i['ligacoes']):
            u = pagina_comissao(x)
            if u: i['ligacoes'].append({'titulo': 'Página da comissão', 'url': u})
        i['varrimento'] = x.get('varrimento') or ''; itens.append(i)   # nome da ficha (para abrir e imprimir a ficha da edição)
    hist.append({'numero': ed.get('numero', 0), 'estado': ed.get('estado', ''), 'semana': ed.get('semana', ''), 'inicio': ed['inicio'],
                 'fim': ed.get('fim', ed['inicio']), 'ficheiro': f.with_suffix('.html').name, 'itens': itens})
d['historico'] = sorted(hist, key=lambda e: e['inicio'])

json_txt = json.dumps(d, ensure_ascii=False).replace('</script', '<\\/script')
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text(modelo.replace('__LOGO__', logo).replace('__DATA__', json_txt), encoding='utf-8')
print('gerado', destino, f"{len(d['destaques'])} destaques, {len(d['agenda'])} matérias, {len(d['fichas'])} fichas, {len(hist)} edições anteriores")
