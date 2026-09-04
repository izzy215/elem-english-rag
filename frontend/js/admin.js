/* 4.6 관리자 — 골든 데이터 상태 · RAG 정확도(/api/rag/eval) · 소스 등록 + 검수 경고(/api/rag/check)
 * 서버가 스텁이면: 정확도는 "측정 전", 검수는 "경고 없음(구현 전엔 항상 통과)", 등록은 API 필요 안내.
 */

// ---------- 골든 데이터 상태 ----------
async function loadData(health) {
  if (!health) { $('#dataStatus').textContent = '서버 연결 실패'; return; }
  $('#dataStatus').innerHTML = health.using_sample
    ? '<span class="pill warn">임시 샘플</span> data/golden/_sample · 데이터팀 납품 전'
    : `<span class="pill ok">골든 데이터</span> ${esc(health.golden_files.join(', '))}`;
  const levels = await api('/api/levels');
  const rows = [];
  for (const l of levels) {
    const units = l.units ? await api(`/api/units?level=${l.level}`) : [];
    rows.push(`<tr><td>${esc(l.label)}</td><td>${units.length}</td>
      <td>${units.reduce((a, u) => a + u.words, 0)}</td><td>${units.reduce((a, u) => a + u.sentences, 0)}</td></tr>`);
  }
  $('#dataTable').innerHTML = `<tr><th>Level</th><th>Unit</th><th>단어</th><th>문장</th></tr>${rows.join('')}`;
}

// ---------- RAG 정확도 ----------
async function loadEval() {
  let r = null;
  try { r = await api('/api/rag/eval'); } catch (_) {}
  if (!r || r.hit_at_3 == null) {
    $('#evalHint').innerHTML = '<span class="tag">측정 전</span> RAG 담당이 <code>tests/</code>에서 eval.csv를 돌리면 여기에 숫자가 나와요. 목표 hit@3 ≥ 80%';
    return;
  }
  const pct = v => v == null ? '–' : Math.round(v * 100) + '%';
  $('#hit3').textContent = pct(r.hit_at_3); $('#hit3').className = 'num' + (r.hit_at_3 >= .8 ? '' : ' na');
  $('#hit1').textContent = pct(r.hit_at_1); $('#hit1').className = 'num';
  $('#evalN').textContent = r.n; $('#evalN').className = 'num';
  const best = Math.max(...(r.runs || []).map(x => x.hit_at_3 || 0));
  $('#runs').innerHTML = (r.runs || []).map(x => `
    <div class="bar"><span>${esc(x.label)}</span>
      <div class="track"><i class="${x.hit_at_3 === best ? 'best' : ''}" style="width:${Math.round((x.hit_at_3 || 0) * 100)}%"></i></div>
      <span class="v">${pct(x.hit_at_3)}</span></div>`).join('');
  $('#evalHint').textContent = r.hit_at_3 >= .8 ? '목표(80%) 달성' : '목표 80%까지 ' + Math.round((.8 - r.hit_at_3) * 100) + '%p 남음';
}

// ---------- 소스 등록 + 검수 경고 ----------
function parseLines() {
  return $('#srcText').value.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const [en, ko = ''] = l.split('|').map(s => s.trim());
    return { en, ko };
  });
}
async function runCheck() {
  const lines = parseLines();
  if (!lines.length) { $('#srcHint').textContent = '문장을 먼저 입력하세요.'; return; }
  const level = parseInt($('#srcLevel').value);
  $('#checkBtn').disabled = true; $('#srcHint').textContent = 'RAG로 검사 중…';
  $('#checks').innerHTML = lines.map((l, i) => `<div class="check" id="ck-${i}"><span class="ic">…</span><div><div class="t">${esc(l.en)}</div><div class="w">검사 중</div></div></div>`).join('');
  let warnTotal = 0, stub = true;
  await Promise.all(lines.map(async (l, i) => {
    const el = $(`#ck-${i}`);
    try {
      const r = await api('/api/rag/check', { method: 'POST', body: JSON.stringify({ text: l.en, level }) });
      const warns = r.warnings || [];
      if (warns.length) { stub = false; warnTotal += warns.length; }
      el.className = 'check ' + (warns.length ? 'warn' : 'ok');
      $('.ic', el).textContent = warns.length ? '!' : '✓';
      $('.w', el).innerHTML = warns.length ? warns.map(esc).join('<br>') : (l.ko ? esc(l.ko) : '뜻 없음 — "| 한국어 뜻"을 붙여주세요');
    } catch (e) {
      el.className = 'check warn'; $('.ic', el).textContent = '?'; $('.w', el).textContent = '검사 실패: ' + e.message;
    }
  }));
  $('#checkBtn').disabled = false;
  $('#submitBtn').disabled = false;
  $('#srcHint').innerHTML = warnTotal
    ? `경고 ${warnTotal}건. 고치거나 그대로 등록할 수 있어요 (최종 판단은 관리자).`
    : (stub ? '경고 없음 — <span class="tag">주의</span> rag.py 구현 전에는 검사가 항상 통과합니다.' : '경고 없음. 등록해도 됩니다.');
}
async function submitSource() {
  const lines = parseLines();
  const body = { title: $('#srcTitle').value.trim(), level: parseInt($('#srcLevel').value), lines };
  $('#submitBtn').disabled = true;
  try {
    await api('/api/sources', { method: 'POST', body: JSON.stringify(body) });
    $('#srcHint').textContent = `${lines.length}문장 등록됨.`;
    $('#srcText').value = ''; $('#srcTitle').value = ''; $('#checks').innerHTML = '';
  } catch (e) {
    $('#srcHint').innerHTML = `<span class="tag">API 필요</span> 등록을 저장할 <code>POST /api/sources</code> 가 아직 없어요 (PRD 4.6 소스 등록 — 담당 결정 필요). 보낸 내용: ${lines.length}문장 · Level ${body.level}`;
    $('#submitBtn').disabled = false;
  }
}

(async function init() {
  renderTopbar({ crumbs: false });      // 관리자 화면은 학습 위치(Level·Unit)와 무관
  const h = await showHealth();
  await Promise.all([loadData(h), loadEval()]);
})();
