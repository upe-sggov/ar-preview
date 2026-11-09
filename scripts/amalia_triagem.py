"""Triagem assistida pelo Amália, sobre dados/agenda.json, para as matérias ainda não vistas por ele nem revistas por pessoas:
  - UNIDADE, só quando as regras não deram nenhuma, pelas competências do Despacho n.º 6738/2025 (dados/competencias_dssd.json);
  - ASSUNTO (o tema passa a dizer o assunto, não o nome da comissão), resumo e expressões de pesquisa para o Radar.
A PRIORIDADE (Imediato, Vigilância, Registo) não é do Amália: segue os critérios da UPE (dados/regras_uo.json).
As correções da revisão humana (correcoes.csv) prevalecem sempre."""
import json, pathlib
from amalia import perguntar, json_da_resposta
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sintese import membros_governo
from cobertura import entidades
comp = json.loads(pathlib.Path('dados/competencias_dssd.json').read_text(encoding='utf-8'))
UNIDADES = [k for k in comp if not k.startswith('_')] + ['Transversal']
p = pathlib.Path('dados/agenda.json'); dados = json.loads(p.read_text(encoding='utf-8'))
SISTEMA = f"""És um analista da Direção de Serviços de Suporte à Decisão (DSSD) da Secretaria-Geral do Governo de Portugal.
Classificas matérias da agenda da Assembleia da República. Responde SÓ com JSON, em português europeu.
Unidades e competências (só estas; nunca inventes outras):
{json.dumps({k: v for k, v in comp.items() if not k.startswith('_')}, ensure_ascii=False, indent=1)}
"Transversal" junta-se às unidades quando a matéria é de todo o Governo (Orçamento do Estado, Conta Geral do Estado, Reforma do Estado).
Se nenhuma unidade for claramente competente, devolve "uo": []. Não forces atribuições."""

GENERICAS = re.compile(r'^(\d{4}|or[cç]amento( do estado)?|oe|proposta de lei.*|audi[cç][aã]o( parlamentar)?|governo|parlamento|assembleia da rep[uú]blica|ministr[oa].*|secret[aá]ri[oa] de estado.*|ue|uni[aã]o europeia|comiss[aã]o europeia|parlamento europeu|conselho europeu|diretiva|regulamento|decreto-lei|lei|estado|portugal|vice-presidente.*|presidente.*|comiss[aã]o|grupo de trabalho.*|representa[cç][aã]o da comiss[aã]o europeia.*)$', re.I)
def util(e):
    """Expressão de pesquisa com valor: nem genérica, nem só um ano, nem cargo (o nome da pessoa é que conta)."""
    e = e.strip()
    # só expressões com nome próprio, sigla ou número («Registo de Transparência», «RTRI», «Lei n.º 5-A/2026»):
    # palavras comuns («transparência», «plataforma informática») apanham notícias de tudo
    return 3 <= len(e) <= 60 and not GENERICAS.match(e) and bool(re.search(r'[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]', e))

def nome_ouvido(x):
    """Nome da pessoa ouvida quando o título pelas regras o traz no fim («…, Teresa Ribera»)."""
    if not x.get('tituloRegras'): return None
    m = re.search(r',\s*((?:[A-ZÁÉÍÓÚ][\wÀ-ú-]+\s?){2,4})(?:\s—.*)?$', x.get('tema') or '')
    return m.group(1).strip() if m else None

def titulo(x, quem, assunto):
    """Nas audições, o título diz quem é ouvido e o assunto («Ministro da Presidência, António Leitão Amaro: Orçamento do Estado 2027»)."""
    principal = next((m for m in quem if re.match(r'(Primeir|Ministr)', m[0])), quem[0] if quem else None)
    if principal:
        q = principal[0] + (', ' + principal[1] if principal[1] else '')
        return assunto if principal[0].lower() in assunto.lower() else f'{q}: {assunto}'
    m = re.match(r'Audi(?:ção|ência)(?: conjunta)? d[aeo]s? (.+?)(?=,?\s+(?:no âmbito|sobre)\b|[;\n]|$)', (x.get('ordemTrabalhos') or '').strip())
    if m and len(m.group(1)) < 90 and m.group(1).split()[0].lower() not in assunto.lower():
        return f'{m.group(1).strip()}: {assunto}'
    return assunto

def pendente(x):
    if x.get('retirado') or x.get('amalia'): return False
    # já não se usam unidades (decisão de 2/11/2026): o Amália só trabalha o assunto e as expressões das matérias com ficha
    return x['pertinencia'] in ('Imediato', 'Vigilância') and not x.get('expressoes')
n = 0
# audição conjunta (uma linha por comissão): as outras linhas da mesma audição herdam o trabalho já feito numa delas
FEITAS = {(x['data'], x['conjuntaId']): x for x in dados['destaques'] + dados['agenda'] if x.get('conjuntaId') and x.get('amalia')}
for x in dados['destaques'] + dados['agenda']:
    if not pendente(x): continue
    irma = x.get('conjuntaId') and FEITAS.get((x['data'], x['conjuntaId']))
    if irma:
        for k in ('amalia', 'expressoes', 'resumo', 'varrimento'):
            if irma.get(k) is not None: x[k] = irma[k]
        if irma.get('tituloRegras') or irma.get('amalia'): x['tema'] = irma['tema']
        continue
    r = json_da_resposta(perguntar(SISTEMA, f"""Reunião: {x['tema']}
Data e hora: {x['data']} {x.get('hora','')}
Tipo: {x.get('tipoLabel','')}
Interveniente: {x.get('interveniente','')}
Ordem de trabalhos: {(x.get('ordemTrabalhos') or x.get('resumo',''))[:3500]}

Devolve: {{"assunto": "título curto com o ASSUNTO principal (não o nome da comissão)", "resumo": "duas frases", "uo": [...], "justificacao": "uma frase: que competência da unidade se aplica", "expressoes": ["3 a 5 expressões curtas como a imprensa as escreve: siglas, nomes próprios de entidades e pessoas, nome do diploma; nada genérico como 'governo' ou 'parlamento'"]}}""", 450))
    if not r: continue
    x['amalia'] = {k: r.get(k) for k in ('assunto', 'resumo', 'uo', 'justificacao', 'expressoes')}
    quem = membros_governo(x)
    audicao = bool(quem or entidades(x))
    ouvido = nome_ouvido(x)   # «Audição com a Vice-Presidente …, Teresa Ribera» → «Teresa Ribera»
    if not x.get('expressoes') and isinstance(r.get('expressoes'), list) and (not audicao or ouvido):   # nas audições, a pesquisa é por quem é ouvido
        x['expressoes'] = ([ouvido] if ouvido else []) + [e for e in r['expressoes'] if isinstance(e, str) and util(e) and e != ouvido][:4]
    if not x.get('validado') and not x['uo']:
        x['uo'] = [u for u in (r.get('uo') or []) if u in UNIDADES]
        if x['uo']: x['criterio'] = (x.get('criterio') or []) + ['unidade pelo Amália: ' + (r.get('justificacao') or 'proposta do modelo')[:140]]
    if r.get('assunto') and not x.get('tituloRegras'):   # o título pelas regras já diz quem é ouvido: fica
        x['orgao'] = x.get('orgao') or x['tema']
        x['tema'] = titulo(x, quem, r['assunto'])
    if r.get('resumo'): x['resumo'] = r['resumo']
    if x.get('conjuntaId'): FEITAS[(x['data'], x['conjuntaId'])] = x
    n += 1
todos = dados['destaques'] + dados['agenda']
ordem = lambda x: (x['data'], x.get('hora') or '99')
dados['destaques'] = sorted([x for x in todos if x['pertinencia'] == 'Imediato'], key=ordem)
dados['agenda'] = sorted([x for x in todos if x['pertinencia'] != 'Imediato'], key=ordem)
p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
print(n, 'matérias classificadas pelo Amália')
