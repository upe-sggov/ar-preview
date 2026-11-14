// Converte o HTML em PDF com o Chromium do Playwright. Uso: node scripts/pdf.js saida/semana-ar.html saida/semana-ar.pdf
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + require('path').resolve(process.argv[2])); await p.waitForTimeout(800);
  await p.emulateMedia({ media: 'print' });
  // «notícias ›», «Ver fundo mediático» e «Ver a lista completa»: no PDF levam à ficha na página da edição (lista completa
  // e contagem atual); as ligações internas do PDF não funcionam em todos os leitores (Outlook, telemóvel).
  const base = (process.env.PAGINA_URL || 'https://upe-sggov.github.io/ar-preview/').replace(/\/?$/, '/');
  let num = null; try { num = JSON.parse(require('fs').readFileSync('dados/agenda.json', 'utf8')).edicao.numero; } catch (e) {}
  await p.evaluate(([base, num]) => {
    const n = num ? String(num).padStart(2, '0') : null;   // página da edição: a ligação continua a funcionar nas semanas seguintes
    const url = k => n ? `${base}edicoes/n${n}.html#${k}` : `${base}#${k}`;
    document.querySelectorAll('a[href^="#f-"], a.web-ficha').forEach(a => {
      const k = a.getAttribute('href').replace(/^#(f-)?/, ''); a.setAttribute('href', url(k)); a.removeAttribute('data-ver');
    });
    document.querySelectorAll('a[href^="#lista-"]').forEach(a => { a.setAttribute('href', url(a.getAttribute('href').slice(1))); a.removeAttribute('data-lista'); });
  }, [base, num]);
  await p.pdf({ path: process.argv[3], format: 'A4', printBackground: true, margin: { top: '11mm', bottom: '11mm', left: '10mm', right: '10mm' } });
  await b.close();
})();
