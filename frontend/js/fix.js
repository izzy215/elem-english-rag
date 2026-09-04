/* 문장 고치기 — 데이터팀 샘플(data/golden_sample.json)로 동작하는 데모
 * 서버 API 없음. JSON을 화면이 직접 읽는다. 오답은 학생별로 sessionStorage에 쌓아 "오답노트" 개념을 보여준다.
 */

let items = [], view = [], idx = 0, type = '전체';
const student = S.get().student || 'A';
const noteKey = `fixNote_${student}`;
const note = JSON.parse(sessionStorage.getItem(noteKey) || '{}');   // {id: {count, last}}

const norm = s => s.toLowerCase().replace(/[^\w\s']/g, '').replace(/\s+/g, ' ').trim();

function renderChips() {
  const types = ['전체', ...new Set(items.map(i => i.error_type))];
  $('#chips').innerHTML = types.map(t => `<button class="chip ${t === type ? 'on' : ''}" onclick="setType('${t}')">${esc(t)}</button>`).join('');
}
function setType(t) {
  type = t; view = type === '전체' ? items : items.filter(i => i.error_type === type);
  // 오답노트에 있는 문장을 앞으로 (오답 반영)
  view = [...view].sort((a, b) => (note[b.id]?.count || 0) - (note[a.id]?.count || 0));
  idx = 0; renderChips(); render();
}
function render() {
  const it = view[idx]; if (!it) return;
  $('#pos').textContent = `${idx + 1} / ${view.length}`;
  $('#errSent').textContent = it.student_error;
  $('#errType').textContent = it.error_type + (note[it.id] ? ` · 오답노트 ${note[it.id].count}회` : '');
  $('#fixInput').value = ''; $('#fixInput').disabled = false; $('#checkBtn').disabled = false;
  $('#verdict').className = 'verdict'; $('#rag').className = 'rag';
  $$('#flow div').forEach(d => d.classList.remove('now'));
  $('#f1').classList.add('now'); $('#f2').classList.add('now');
  renderStat();
}
function renderStat() {
  const wrong = Object.keys(note).length;
  $('#stat').innerHTML = `<span>학생 ${student}</span><span>전체 ${items.length}문장</span><span class="${wrong ? 'bad' : ''}">오답노트 ${wrong}</span>`;
}

function check() {
  const it = view[idx], mine = norm($('#fixInput').value);
  if (!mine) { $('#fixInput').focus(); return; }
  const ok = mine === norm(it.correct_expression);
  showVerdict(it, ok, false);
}
function giveUp() { showVerdict(view[idx], false, true); }
function showVerdict(it, ok, gaveUp) {
  $('#fixInput').disabled = true; $('#checkBtn').disabled = true;
  const v = $('#verdict');
  v.className = 'verdict on ' + (ok ? 'ok' : 'bad');
  v.innerHTML = ok
    ? `<div class="big">정답이에요! 🎉</div><div class="ans">${esc(it.correct_expression)}</div>`
    : `<div class="big">${gaveUp ? '같이 볼까요?' : '아쉬워요, 조금 달라요'}</div><div class="ans">정답: ${esc(it.correct_expression)}</div>`;
  $('#ragCtx').textContent = it.retrieved_context;
  $('#ragFb').innerHTML = esc(it.feedback);
  $('#rag').className = 'rag on';
  $$('#flow div').forEach(d => d.classList.remove('now'));
  $('#f3').classList.add('now'); $('#f4').classList.add('now'); $('#f5').classList.add('now');
  if (!ok) { note[it.id] = { count: (note[it.id]?.count || 0) + 1, last: new Date().toISOString().slice(0, 10) }; }
  else if (note[it.id]) { delete note[it.id]; }          // 데모: 한 번 맞히면 오답노트에서 제거
  sessionStorage.setItem(noteKey, JSON.stringify(note));
  $('#errType').textContent = it.error_type + (note[it.id] ? ` · 오답노트 ${note[it.id].count}회` : '');
  renderStat();
}
function move(d) { idx = (idx + d + view.length) % view.length; render(); }

(async function init() {
  renderTopbar({ crumbs: false });
  showHealth();
  try {
    const r = await fetch('data/golden_sample.json'); const j = await r.json();
    items = j.data;
    $('.sub').textContent = `${j.title.replace(' - RAG 골든데이터셋 예시', '')} · ${items.length}문장 · ${j.level}`;
  } catch (e) { $('#errSent').textContent = '데이터를 못 읽었어요: data/golden_sample.json'; return; }
  setType('전체');
  $('#fixInput').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); check(); } });
})();
