"""Passo 2 — triagem automática: propõe unidade orgânica e pertinência a partir de dados/regras_uo.json.
A revisão humana (UPE) confirma ou corrige no ficheiro resultante (dados/triagem_proposta.json) antes do varrimento.
"""
import json, pathlib, re, sys
if not pathlib.Path('dados/agenda_bruta.json').exists():
    print('Sem recolha nova — triagem não feita.'); sys.exit(0)
regras = json.loads(pathlib.Path('dados/regras_uo.json').read_text(encoding='utf-8'))
bruto = json.loads(pathlib.Path('dados/agenda_bruta.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sintese import membros_governo
import csv, unicodedata

def norm(t):
    t = ''.join(c for c in unicodedata.normalize('NFD', (t or '').lower()) if unicodedata.category(c) != 'Mn')
    t = re.sub(r'\bministra\b', 'ministro', t); t = re.sub(r'\bsecretaria de estado\b', 'secretario de estado', t)
    t = re.sub(r'\badjunta\b', 'adjunto', t); t = re.sub(r'\bprimeira-ministra\b', 'primeiro-ministro', t)
    return re.sub(r'\s+', ' ', t).strip()

PERT = regras.get('pertinencia', {})
CLIENTES = [(c['ministerio'], [norm(x) for x in c.get('cargos', [])], [norm(' '.join(n.split()[-2:])) for n in c.get('nomes', [])]) for c in PERT.get('clientes', [])]
PLEN_IME = [(norm(t), t) for t in PERT.get('plenario_imediato', [])]
# comissões da área de cada cliente: as suas reuniões são Imediato mesmo sem o cliente presente (decisão de 7/11/2026)
COM_CLI = [(norm(cm), c['ministerio']) for c in PERT.get('clientes', []) for cm in c.get('comissoes', [])]
COM_AREA = [(norm(cm), c['motivo']) for c in PERT.get('comissoes_imediato', []) for cm in c.get('comissoes', [])]

def ler_csv(nome):
    f = pathlib.Path('dados') / nome
    return list(csv.DictReader(f.open(encoding='utf-8-sig'), delimiter=';')) if f.exists() else []
ENTREGUES = [(r.get('assunto', ''), [norm(e) for e in (r.get('expressoes') or '').split('|') if e.strip()], (r.get('unidade') or '').strip()) for r in ler_csv('varrimentos_entregues.csv')]
DOSSIERS = [((r.get('unidade') or '').strip(), r.get('dossier', ''), [norm(e) for e in (r.get('expressoes') or '').split('|') if e.strip()]) for r in ler_csv('dossiers.csv')]

def tem(expr, txt):
    return re.search(r'\b' + re.escape(expr) + r'\b', txt) is not None

def triar(item):
    texto = ' '.join([item['tema'], item['resumo'], item['ordemTrabalhos'], item['interveniente']]).lower()
    plenario = (item.get('orgao') or item['tema']).startswith('Plenário')
    forte_raw = (item['tema'] + ' ' + (item['ordemTrabalhos'] if plenario else '')).lower()
    forte = norm(forte_raw)
    tn = norm(texto)
    # --- unidade: palavras-chave de cada unidade (dados/regras_uo.json) e dossiers (dados/dossiers.csv)
    uos, crit = set(), []
    for uo, cfg in regras['unidades'].items():
        # 'termos' em todo o texto; os da lista 'imediato' só quando são o assunto principal (tema, ou ordem do dia no Plenário)
        bate = [t for t in cfg['termos'] if re.search(r'\b'+re.escape(t.lower())+r'\b', texto)] + \
               [t for t in cfg.get('imediato', []) if t not in cfg['termos'] and re.search(r'\b'+re.escape(t.lower())+r'\b', forte_raw)]
        if bate: uos.add(uo); crit += [f'«{t}» ({uo})' for t in bate[:2]]
    bt = [t for t in regras.get('transversal', []) if t in texto]
    if bt: uos.add('Transversal'); crit += [f'«{t}» (transversal)' for t in bt[:1]]
    # --- pertinência (critérios da UPE): Imediato › Vigilância › Registo
    pert = 'Registo'
    entregue = next(((a, u) for a, es, u in ENTREGUES if any(tem(e, tn) for e in es)), None)
    visita = 'visitas' in norm(item.get('tipoLabel') or '') or norm(item.get('orgao') or item['tema']).startswith('visitas guiadas')
    # visitas ao Palácio: as delegações são muitas vezes estrangeiras (ex.: «Ministra da Indústria … do Kosovo»), não são o Governo
    membros = [] if visita else [(norm(c), n) for c, n in membros_governo(item)]
    cli = next((m for m, cargos, nomes in CLIENTES
                if any(mc == c or mc.startswith(c) or c.startswith(mc) for mc, _ in membros for c in cargos)
                or any(tem(n, tn) for n in nomes)), None)
    plen = plenario and next((orig for t, orig in PLEN_IME if t in forte), None)
    if entregue:
        pert = 'Imediato'; crit.append(f'já teve varrimento próprio entregue: {entregue[0]} → Imediato')
        if entregue[1]: uos.add(entregue[1])
    if cli:
        pert = 'Imediato'; crit.append(f'presença de cliente com pedidos à UPE ({cli}) → Imediato'); uos.add('DACDP')
    if plen:
        pert = 'Imediato'; crit.append(f'Plenário: «{plen}» → Imediato'); uos.add('DACDP')
    orgao = norm(item.get('orgao') or '')
    comcli = sorted({m for cm, m in COM_CLI if orgao and (orgao == cm or orgao.startswith(cm))})
    if comcli:
        pert = 'Imediato'; crit.append(f"comissão da área de cliente com pedidos à UPE ({'; '.join(comcli)}) → Imediato")
    comarea = next((m for cm, m in COM_AREA if orgao and (orgao == cm or orgao.startswith(cm))), None)
    if comarea:
        pert = 'Imediato'; crit.append(f'comissão acompanhada pela área ({comarea}) → Imediato')
    if pert != 'Imediato':
        if membros or (plenario and re.search(r'(^|\n|/)\s*GOV\s*(\n|/|$)', item['ordemTrabalhos'])):
            pert = 'Vigilância'; crit.append('presença de membro do Governo → Vigilância'); uos.add('DACDP')
        bg = [t for t in regras.get('governo', {}).get('termos', []) if t in texto]
        if bg and pert == 'Registo':
            pert = 'Vigilância'; crit.append(f'«{bg[0]}» → Vigilância'); uos.add('DACDP')
    for u, dossier, es in DOSSIERS:
        if any(tem(e, tn) for e in es):
            if u: uos.add(u)
            if pert == 'Registo': pert = 'Vigilância'
            crit.append(f'dossier acompanhado: {dossier} → Vigilância')
    if pert == 'Registo': crit.append('sem cliente, membro do Governo nem dossier acompanhado → Registo')
    return sorted(uos), pert, crit
for it in bruto['itens'] + bruto.get('futuro', []):
    it['uo'], it['pertinencia'], it['criterio'] = triar(it)
    it['validado'] = False          # a revisão humana muda para true (ou corrige uo/pertinencia)
pathlib.Path('dados/triagem_proposta.json').write_text(json.dumps(bruto, ensure_ascii=False, indent=1), encoding='utf-8')
n = len(bruto['itens']); print(n, 'itens;', sum(1 for i in bruto['itens'] if i['uo']), 'com unidade proposta;', sum(1 for i in bruto['itens'] if i['pertinencia']=='Imediato'), 'imediato')
