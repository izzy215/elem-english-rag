/* 오답노트(문법 규칙) — 서버 /notebook 이 정식 (규칙 이름 name · 한 줄 short 도 서버가 준다). 서버 연결 실패 때만 이 브라우저 사본(localStorage)
 * 연습은 카드 안에서 (목업 9/14 B안 채택 — 별도 규칙 연습 화면 폐기): "이 규칙 연습하기 ▾" 를 누르면 카드가 펼쳐져 4지선다 2문제.
 * 문제·채점은 서버 /drill · /drill/answer 그대로. 한 번에 한 카드만 펼침. 튜터의 🙋 타일에서 오면(S.nbOpen) 그 규칙 카드를 펼친 채로 연다. */
const student = S.get().student || 'A';
let NB_DATA = null, nbOpen = null;
const D = {};   // rule_id → { drill_id, qs, qi, ok, name, msg }

async function render() {
  renderTopbar({ crumbs: false });
  const nb = NB_DATA = await fetchNotebook(student);
  $('#noteSub').textContent = nb.active.length ? `아직 헷갈리는 규칙 ${nb.active.length}개 · 연습에서 연속 2번 맞히면 극복!` : '헷갈리는 규칙이 없어요 🎉';
  $('#noteList').innerHTML = nb.active.length ? nb.active.map((e, i) => { const ex = (e.examples || [])[0]; const open = nbOpen === e.rule_id; return `
    <div class="card note${open ? ' open' : ''}" id="card-${esc(e.rule_id)}"><div class="mark">✕</div><div class="w">${esc(e.name || e.rule_id)}</div><div class="meta">${e.count}회 · ${esc(e.last || '')}</div>
      ${ex ? `<div class="my">내 문장: <s>${esc(ex.text)}</s><br>→ <em>${esc(ex.fixed)}</em></div>` : ''}
      <div class="srcline">📚 ${esc(e.short || e.name || e.rule_id)} · ${esc(e.rule_id)}${e.streak ? ` · 연속 정답 ${e.streak}/2` : ''}</div>
      <button type="button" class="btn${open ? ' ghost' : ''}" data-rule="${esc(e.rule_id)}" data-name="${esc(e.name || e.rule_id)}">${open ? '접기 ▴' : '이 규칙 연습하기 ▾'}</button>
      <div class="nbdrill" id="nb-${esc(e.rule_id)}" style="display:${open ? 'block' : 'none'}"></div></div>`; }).join('')
    : '<div class="empty">말하기에서 틀린 규칙이 여기에 모여요</div>';
  $$('#noteList button[data-rule]').forEach(b => b.addEventListener('click', () => toggle(b.dataset.rule, b.dataset.name)));   // 값은 onclick 속성에 넣지 않는다
  $('#noteDone').innerHTML = nb.overcome.length ? `<div class="hint" style="margin:0"><b style="color:var(--ink)">극복한 규칙 ${nb.overcome.length}</b> · 연속 2번 정답</div><div class="overcome">${nb.overcome.map(e => `<span>○ ${esc(e.name || e.rule_id)}</span>`).join('')}</div>` : '';
  $('#noteHint').textContent = nb.local ? '서버 연결 실패 · 이 브라우저에 저장된 오답노트만 보여요 (연습은 서버가 있어야 해요)' : '';
  if (nbOpen) { const c = $('#nb-' + CSS.escape(nbOpen)); if (c) { await loadDrill(nbOpen); c.closest('.card')?.scrollIntoView({ block: 'center', behavior: 'smooth' }); } else nbOpen = null; }
}
async function toggle(ruleId, name) {
  nbOpen = nbOpen === ruleId ? null : ruleId;
  if (nbOpen) D[ruleId] = { name, drill_id: null, qs: [], qi: 0, ok: 0, msg: '' };
  await render();
}
// ── 카드 안 연습: 서버 /drill 로 2문제 → 답은 /drill/answer 로 채점 → 끝나면 서버가 streak 갱신 → 오답노트 다시 읽기 ──
async function loadDrill(ruleId) {
  const d = D[ruleId] || (D[ruleId] = { name: '', drill_id: null, qs: [], qi: 0, ok: 0, msg: '' });
  const box = $('#nb-' + CSS.escape(ruleId)); if (!box) return;
  if (!d.qs.length) {
    box.innerHTML = '<div class="prog">문제 가져오는 중…</div>';
    try { const r = await api(`/api/drill?student=${encodeURIComponent(student)}&rule=${encodeURIComponent(ruleId)}&count=2`); d.drill_id = r.drill_id; d.qs = r.questions || []; if (r.rule_name) d.name = r.rule_name; }
    catch (e) { box.innerHTML = `<div class="prog">${e.status === 404 ? '이 규칙은 아직 연습 문제가 없어요' : '연습 문제를 가져오지 못했어요: ' + esc(e.message)}</div>`; return; }
    if (!d.qs.length) { box.innerHTML = '<div class="prog">이 규칙은 아직 연습 문제가 없어요</div>'; return; }
  }
  renderQ(ruleId);
}
function renderQ(ruleId) {
  const d = D[ruleId], q = d.qs[d.qi], box = $('#nb-' + CSS.escape(ruleId)); if (!q || !box) return;
  const s = String(q.sentence), m = new RegExp('(^|[^A-Za-z])(' + escapeRe(q.target) + ')(?![A-Za-z])').exec(s);   // target 에 . 이 있어도 밑줄
  const sent = m ? esc(s.slice(0, m.index + m[1].length)) + '<u>' + esc(m[2]) + '</u>' + esc(s.slice(m.index + m[0].length)) : esc(s);
  box.innerHTML = `<div class="prog">문제 ${d.qi + 1}/${d.qs.length} · 밑줄 친 곳을 어떻게 고칠까요?</div>
    <div class="q"><div class="sent">${sent}</div><div class="choices">${q.choices.map((c, i) => `<button type="button" class="choice" data-i="${i}"><span class="k">${'ABCD'[i]}</span>${esc(c)}</button>`).join('')}</div><div class="result" id="nbR-${esc(ruleId)}"></div></div>
    <div class="src" id="nbS-${esc(ruleId)}" style="display:none"></div>
    <button type="button" class="btn" id="nbN-${esc(ruleId)}" disabled>${d.qi === d.qs.length - 1 ? '끝' : '다음'}</button>`;
  $$('.choice', box).forEach(b => b.addEventListener('click', () => answer(ruleId, +b.dataset.i)));
  $('#nbN-' + CSS.escape(ruleId)).addEventListener('click', () => next(ruleId));
}
async function answer(ruleId, i) {
  const d = D[ruleId], q = d.qs[d.qi], box = $('#nb-' + CSS.escape(ruleId)); if (!q || BUSY) return;
  $$('.choice', box).forEach(b => b.disabled = true);
  let r; try { r = await api('/api/drill/answer', { method: 'POST', body: JSON.stringify({ student, drill_id: d.drill_id, question_id: q.id, choice: i }) }); }
  catch (e) { showResult('#nbR-' + CSS.escape(ruleId), '채점 실패: ' + esc(e.message) + ' — 다시 눌러 보세요', 'bad'); $$('.choice', box).forEach(b => b.disabled = false); return; }
  $$('.choice', box).forEach((b, j) => { b.classList.add(j === r.answer ? 'ok' : j === i ? 'bad' : 'dim'); });
  showResult('#nbR-' + CSS.escape(ruleId), r.correct ? '정답이에요! 🎉' : `아쉬워요. 정답은 ${esc(q.choices[r.answer])}`, r.correct ? '' : 'bad');
  const src = $('#nbS-' + CSS.escape(ruleId)); if (r.rule_text) { src.style.display = 'block'; src.innerHTML = `📚 ${esc(r.rule_text)}`; }
  if (r.correct) d.ok++; d.last = r; $('#nbN-' + CSS.escape(ruleId)).disabled = false;
}
async function next(ruleId) {
  const d = D[ruleId];
  if (d.qi < d.qs.length - 1) { d.qi++; renderQ(ruleId); return; }
  const r = d.last || {}; NB.drillResult(student, ruleId, d.ok === d.qs.length);   // 브라우저 사본도 갱신 (화면은 서버 값을 먼저 쓴다)
  nbOpen = null; delete D[ruleId]; await render();
  const msg = r.overcome ? `🌳 ${esc(d.name || ruleId)} 극복! 연속 2번 다 맞혔어요` : d.ok === d.qs.length ? `👍 다 맞았어요 · 연속 ${r.streak ?? 1}/2 — 한 번 더 맞히면 극복!` : `다시 도전! 연속 정답이 0으로 돌아갔어요`;
  $('#noteHint').textContent = msg;
}
(async function init() { showHealth(); injectChat('notebook'); nbOpen = S.get().nbOpen || null; if (nbOpen) { S.set({ nbOpen: null }); D[nbOpen] = { name: '', drill_id: null, qs: [], qi: 0, ok: 0, msg: '' }; } await render(); })();
