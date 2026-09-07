/* 오답노트(문법 규칙) — 서버 /notebook 우선, 없으면 로컬(localStorage) */
const student = S.get().student || 'A';
async function render() {
  renderTopbar({ crumbs: false }); await loadSampleB();
  const nb = await fetchNotebook(student);
  $('#noteSub').textContent = nb.active.length ? `아직 헷갈리는 규칙 ${nb.active.length}개 · 연습에서 연속 2번 맞히면 극복!` : '헷갈리는 규칙이 없어요 🎉';
  $('#noteList').innerHTML = nb.active.length ? nb.active.map(e => { const r = ruleOf(e.rule_id); const ex = (e.examples || [])[0]; return `
    <div class="card note"><div class="mark">✕</div><div class="w">${esc(e.name || r?.type || e.rule_id)}</div><div class="meta">${e.count}회 · ${esc(e.last || '')}</div>
      ${ex ? `<div class="my">내 문장: <s>${esc(ex.text)}</s><br>→ <em>${esc(ex.fixed)}</em></div>` : ''}
      <div class="srcline">📚 ${esc(r?.short || e.rule_id)} · ${esc(e.rule_id)}</div>
      <button class="btn ghost" onclick="startDrill('${esc(e.rule_id)}')">이 규칙 연습하기</button></div>`; }).join('')
    : '<div class="empty">말하기에서 틀린 규칙이 여기에 모여요</div>';
  $('#noteDone').innerHTML = nb.overcome.length ? `<div class="hint" style="margin:0"><b style="color:var(--ink)">극복한 규칙 ${nb.overcome.length}</b> · 연속 2번 정답</div><div class="overcome">${nb.overcome.map(e => `<span>○ ${esc(e.name)}</span>`).join('')}</div>` : '';
  $('#noteHint').textContent = nb.local ? '서버 /notebook 구현 전 · 이 브라우저에만 저장됨' : '';
}
function startDrill(ruleId) { S.set({ drillRule: ruleId }); go('drill.html'); }
(async function init() { showHealth(); injectChat('notebook'); await render(); })();
