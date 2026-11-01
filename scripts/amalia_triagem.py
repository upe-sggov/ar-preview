"""Triagem assistida pelo Amália, sobre dados/agenda.json, para as matérias ainda não vistas por ele nem revistas por pessoas:
  - UNIDADE, só quando as regras não deram nenhuma, pelas competências do Despacho n.º 6738/2025 (dados/competencias_dssd.json);
  - ASSUNTO (o tema passa a dizer o assunto, não o nome da comissão), resumo e expressões de pesquisa para o Radar.
A PRIORIDADE (Imediato, Vigilância, Registo) não é do Amália: segue os critérios da UPE (dados/regras_uo.json).
As correções da revisão humana (correcoes.csv) prevalecem sempre."""
import json, pathlib
from amalia import perguntar, json_da_resposta
comp = json.loads(pathlib.Path('dados/competencias_dssd.json').read_text(encoding='utf-8'))
UNIDADES = [k for k in comp if not k.startswith('_')] + ['Transversal']
p = pathlib.Path('dados/agenda.json'); dados = json.loads(p.read_text(encoding='utf-8'))
SISTEMA = f"""És um analista da Direção de Serviços de Suporte à Decisão (DSSD) da Secretaria-Geral do Governo de Portugal.
Classificas matérias da agenda da Assembleia da República. Responde SÓ com JSON, em português europeu.
Unidades e competências (só estas; nunca inventes outras):
{json.dumps({k: v for k, v in comp.items() if not k.startswith('_')}, ensure_ascii=False, indent=1)}
"Transversal" junta-se às unidades quando a matéria é de todo o Governo (Orçamento do Estado, Conta Geral do Estado, Reforma do Estado).
Se nenhuma unidade for claramente competente, devolve "uo": []. Não forces atribuições."""
def pendente(x):
    if x.get('retirado') or x.get('amalia'): return False
    sem_uo = not x['uo'] and not x.get('validado')
    sem_exp = x['pertinencia'] in ('Imediato', 'Vigilância') and not x.get('expressoes')
    return sem_uo or sem_exp
n = 0
for x in dados['destaques'] + dados['agenda']:
    if not pendente(x): continue
    r = json_da_resposta(perguntar(SISTEMA, f"""Reunião: {x['tema']}
Data e hora: {x['data']} {x.get('hora','')}
Tipo: {x.get('tipoLabel','')}
Interveniente: {x.get('interveniente','')}
Ordem de trabalhos: {(x.get('ordemTrabalhos') or x.get('resumo',''))[:3500]}

Devolve: {{"assunto": "título curto com o ASSUNTO principal (não o nome da comissão)", "resumo": "duas frases", "uo": [...], "justificacao": "uma frase: que competência da unidade se aplica", "expressoes": ["3 a 5 expressões curtas como a imprensa as escreve: siglas, nomes próprios de entidades e pessoas, nome do diploma; nada genérico como 'governo' ou 'parlamento'"]}}""", 450))
    if not r: continue
    x['amalia'] = {k: r.get(k) for k in ('assunto', 'resumo', 'uo', 'justificacao', 'expressoes')}
    if not x.get('expressoes') and isinstance(r.get('expressoes'), list):
        x['expressoes'] = [e for e in r['expressoes'] if isinstance(e, str) and 3 <= len(e) <= 60][:5]
    if not x.get('validado') and not x['uo']:
        x['uo'] = [u for u in (r.get('uo') or []) if u in UNIDADES]
        if x['uo']: x['criterio'] = (x.get('criterio') or []) + ['unidade pelo Amália: ' + (r.get('justificacao') or 'proposta do modelo')[:140]]
    if r.get('assunto'): x['orgao'] = x.get('orgao') or x['tema']; x['tema'] = r['assunto']
    if r.get('resumo'): x['resumo'] = r['resumo']
    n += 1
todos = dados['destaques'] + dados['agenda']
ordem = lambda x: (x['data'], x.get('hora') or '99')
dados['destaques'] = sorted([x for x in todos if x['pertinencia'] == 'Imediato'], key=ordem)
dados['agenda'] = sorted([x for x in todos if x['pertinencia'] != 'Imediato'], key=ordem)
p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
print(n, 'matérias classificadas pelo Amália')
