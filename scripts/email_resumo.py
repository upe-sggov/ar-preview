"""Corpo do email de segunda-feira do AR Preview, com o mesmo desenho do email do Radar de Notícias
(cartão branco de 640 px, cabeçalho azul com o logótipo de anel branco fino, contagem em destaque,
matérias agrupadas por dia e rodapé escuro). Gerado do mesmo dados/agenda.json que a página.
Cada matéria leva: hora, comissão/tema, membro do Governo, síntese curta, etiquetas das unidades
e as ligações que existirem (página na AR, varrimento, adicionar ao calendário).
Logótipo servido pela própria página (docs/logo-sggov-email.png); HTML simples com estilos em linha (Outlook).
Uso: PAGINA_URL=https://… python scripts/email_resumo.py dados/agenda.json [assunto.txt] > email.html"""
import json, sys, html, os
sys.path.insert(0, os.path.dirname(__file__))
from sintese import membro_governo, sintese, pagina_ar, cal_nome, CANAL
d = json.loads(open(sys.argv[1], encoding='utf-8').read())
url = os.environ.get('PAGINA_URL', '').strip()
if url and not url.endswith('/'): url += '/'
AGENDA_AR = 'https://agenda.parlamento.pt/'
ed = d['edicao']
# todas as reuniões da semana, como na página: as de Registo também (sem elas, a agenda do email fica com buracos)
todos = [x for x in d['destaques'] + d['agenda'] if not x.get('retirado')]
todos.sort(key=lambda x: (x['data'], x.get('hora') or '99'))
e = html.escape
nomes = d.get('unidades', {})
DIAS = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

def dia_extenso(iso):
    import datetime
    t = datetime.date.fromisoformat(iso)
    return f'{DIAS[t.weekday()]}, {t.day} de {MESES[t.month - 1]}'

def etiqueta(txt, cor, titulo=''):
    return (f'<span title="{e(titulo)}" style="font:600 9px Arial,sans-serif;color:{cor};letter-spacing:.6px;text-transform:uppercase;'
            f'border:1px solid {cor};border-radius:3px;padding:1px 5px;margin-right:5px">{e(txt)}</span>')

def etiquetas(x):
    """Etiqueta de cada unidade (ou «Transversal», que serve todas) a que a matéria se aplica."""
    # como na página: as unidades a que a matéria se aplica, e «Transversal» quando interessa a todas
    t = etiqueta('Transversal', '#2B5683', 'todas as unidades do Suporte à Decisão') if 'Transversal' in x['uo'] else ''
    return t + ''.join(etiqueta(u, '#0E7433', nomes.get(u, '')) for u in ('DACDP', 'DAPL', 'UPE', 'DCIRI') if u in x['uo'])

def linha(x):
    cor = {'Imediato': '#D02117', 'Vigilância': '#BE9C54'}.get(x['pertinencia'], '#a3aab3')
    pag, rotulo = pagina_ar(x)
    reg = x['pertinencia'] not in ('Imediato', 'Vigilância')      # Registo: linha mais discreta, só para informação
    ft = 'font:400 13px Arial,sans-serif;color:#3d4249' if reg else 'font:600 14px Arial,sans-serif;color:#171715'
    tema = (f'<a href="{e(pag)}" style="{ft};text-decoration:none;line-height:1.4">{e(x["tema"])}</a>'
            if pag else f'<span style="{ft};line-height:1.4">{e(x["tema"])}</span>')
    novo = (' <span style="font:600 9px Arial,sans-serif;color:#6b5200;background:#fff4c2;border-radius:3px;padding:1px 5px;'
            'letter-spacing:.6px;text-transform:uppercase">novo</span>') if x.get('novo') else ''
    gov, sin = membro_governo(x), ('' if reg else sintese(x))
    org = x.get('orgao') or ''
    info = f'<div style="font:400 11.5px Arial,sans-serif;color:#8a9098;padding-top:2px;line-height:1.45">{e(org)}</div>' if org and org != x['tema'] else ''
    if x.get('conjunta'): info += f'<div style="font:400 11.5px Arial,sans-serif;color:#8a9098;padding-top:2px;line-height:1.45">Audição conjunta com a {e(" e a ".join(x["conjunta"]))}</div>'
    if gov: info += f'<div style="font:400 12px Arial,sans-serif;color:#171715;padding-top:3px;line-height:1.45"><span style="color:#8a9098">Governo:</span> {e(gov)}</div>'
    if sin: info += f'<div style="font:400 12px Arial,sans-serif;color:#5b6068;padding-top:3px;line-height:1.45">{e(sin)}</div>'
    extras = []
    L = 'color:#2B5683;text-decoration:underline'
    if pag: extras.append(f'<a href="{e(pag)}" style="{L}">{rotulo}</a>')
    if x.get('varrimento') and url: extras.append(f'<a href="{e(url)}#{e(x["varrimento"])}" style="{L}">varrimento</a>')
    elif x.get('varrimento'): extras.append('com varrimento')
    if url and x.get('data'): extras.append(f'<a href="{e(url)}cal/{e(cal_nome(x))}" style="{L}">adicionar ao calendário</a>')
    mais = f'<div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:5px">{" · ".join(extras)}</div>' if extras else ''
    return f'''    <tr><td style="padding:9px 24px;border-bottom:1px solid #f1f4f7">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>
        <td width="52" valign="top" style="font:400 12px Arial,sans-serif;color:#5b6068;padding-top:2px">{e(x.get("hora") or "—")}</td>
        <td width="14" valign="top" style="font:400 14px Arial,sans-serif;color:{cor};line-height:1.4">&#9679;</td>
        <td valign="top">{tema}{novo}{info}
          <div style="padding-top:5px">{etiquetas(x)}</div>{mais}
        </td>
      </tr></table>
    </td></tr>'''

def cab_dia(iso, n):
    return f'''    <tr><td style="padding:16px 24px 4px">
      <div style="font:600 10px Arial,sans-serif;color:#5b6068;letter-spacing:1.2px;text-transform:uppercase;border-bottom:1px solid #e2e8f0;padding-bottom:5px">{e(dia_extenso(iso))} · {n}</div>
    </td></tr>'''

corpo = []
for dia in sorted({x['data'] for x in todos}):
    da = [x for x in todos if x['data'] == dia]
    corpo.append(cab_dia(dia, len(da)))
    corpo.extend(linha(x) for x in da)
corpo = '\n'.join(corpo) if corpo else (
    '    <tr><td style="padding:16px 24px;font:400 13px Arial,sans-serif;color:#5b6068">Sem reuniões na agenda da AR à data desta edição.</td></tr>')

n_ime = sum(1 for x in todos if x['pertinencia'] == 'Imediato'); n_vig = sum(1 for x in todos if x['pertinencia'] == 'Vigilância')
n_reg = len(todos) - n_ime - n_vig
quando = ed.get('atualizadoLabel') or ed.get('fechoLabel', '')
n_ed = f'edição n.º {ed["numero"]}' + (' (piloto)' if ed.get('estado') == 'piloto' else '')
legenda = ' · '.join(f'<b style="color:#5b6068">{e(u)}</b> {e(nomes[u])}' for u in ('DACDP', 'DAPL', 'UPE', 'DCIRI') if nomes.get(u))

logo = (f'<td valign="middle" style="padding-right:14px"><img src="{e(url)}logo-sggov-email.png" width="40" height="40" '
        f'alt="Secretaria-Geral do Governo" style="display:block;border:0"></td>') if url else ''
BS = 'display:inline-block;font:600 13px Arial,sans-serif;text-decoration:none;padding:9px 16px;border-radius:6px;margin:0 6px 8px 0'
botoes = ''
if url: botoes += f'<a href="{e(url)}" style="{BS};background:#0E7433;color:#ffffff">Abrir o AR Preview</a>'
if url and todos: botoes += f'<a href="{e(url)}cal/semana.ics" style="{BS};background:#ffffff;color:#2B5683;border:1px solid #2B5683">Todas no calendário</a>'
botoes += f'<a href="{AGENDA_AR}" style="{BS};background:#ffffff;color:#2B5683;border:1px solid #2B5683">Agenda parlamentar</a>'
botoes += f'<a href="{CANAL}" style="{BS};background:#ffffff;color:#2B5683;border:1px solid #2B5683">Canal Parlamento</a>'

print(f'''<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f6f8">
<tr><td align="center" style="padding:24px 12px">

<table width="640" cellpadding="0" cellspacing="0" role="presentation" style="max-width:640px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(23,23,21,.08)">

  <tr><td style="background:#2B5683;padding:20px 24px">
    <table cellpadding="0" cellspacing="0" role="presentation"><tr>
      {logo}
      <td valign="middle">
        <div style="font:600 10px Arial,sans-serif;color:#ffffff;opacity:.8;letter-spacing:1.4px;text-transform:uppercase">Secretaria-Geral do Governo</div>
        <div style="font:600 20px Arial,sans-serif;color:#ffffff;padding-top:5px">AR Preview</div>
        <div style="font:400 13px Arial,sans-serif;color:#ffffff;opacity:.85;padding-top:4px">{e(ed["semana"])} · {n_ed} · atualizada a {e(quando)}</div>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:16px 24px 12px;background:#fbfcfd;border-bottom:1px solid #e2e8f0">
    <span style="font:600 24px Arial,sans-serif;color:#0E7433">{len(todos)}</span>
    <span style="font:400 13px Arial,sans-serif;color:#5b6068">matérias para a área de Suporte à Decisão:
      <b style="color:#D02117">&#9679; {n_ime}</b> imediatas, <b style="color:#BE9C54">&#9679; {n_vig}</b> em vigilância, <b style="color:#8a9098">&#9679; {n_reg}</b> para registo; {len({x["varrimento"] for x in todos if x.get("varrimento")})} com ficha de varrimento</span>
    {f'<div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:6px;line-height:1.5">{legenda}</div>' if legenda else ''}
  </td></tr>

{corpo}

  <tr><td align="center" style="padding:22px 24px 18px">
    <div style="font:400 13px Arial,sans-serif;color:#5b6068;line-height:1.55;padding-bottom:12px">
      Calendário, cartões e fichas de varrimento estão na página do AR Preview, atualizada diariamente; o PDF segue em anexo.</div>
    {botoes}
    <div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:6px;line-height:1.5">«Adicionar ao calendário» descarrega o evento para o Outlook (hora de fim indicativa).
      As emissões em direto, quando as há, estão no Canal Parlamento. A agenda da Assembleia da República pode mudar depois desta edição.</div>
  </td></tr>

  <tr><td style="padding:18px 24px;background:#171715">
    <div style="font:400 11px Arial,sans-serif;color:#ffffff;opacity:.85;line-height:1.6">
      Direção de Serviços de Suporte à Decisão · Unidade de Pesquisa e Estatísticas<br>
      Pedidos de varrimento adicionais:
      <a href="mailto:upe@sggoverno.gov.pt?subject=AR%20Preview%20%E2%80%94%20pedido%20de%20varrimento" style="color:#ffffff;text-decoration:underline">upe@sggoverno.gov.pt</a><br>
      Agenda recolhida dos dados publicados pela Assembleia da República. A leitura e a verificação são de quem recebe.
    </div>
  </td></tr>

</table>
</td></tr></table>''')

# assunto do email (usado pelo envio): «AR Preview n.º N · semana»
if len(sys.argv) > 2:
    open(sys.argv[2], 'w', encoding='utf-8').write(f'AR Preview n.º {ed["numero"]} · {ed["semana"]} — agenda da Assembleia da República')
