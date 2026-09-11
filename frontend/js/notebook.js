/* 오답노트(문법 규칙) — 서버 /notebook 이 정식 (규칙 이름 name · 한 줄 short 도 서버가 준다). 서버 연결 실패 때만 이 브라우저 사본(localStorage) */
const student = S.get().student || 'A';
async function render() {
  renderTopbar({ crumbs: false });
  const nb = await fetchNotebook(student);
  $('#noteSub').textContent = nb.active.length ? `아직 헷갈리는 규칙 ${nb.active.length}개 · 연습에서 연속 2번 맞히면 극복!` : '헷갈리는 규칙이 없어요 🎉';
  $('#noteList').innerHTML = nb.active.length ? nb.active.map((e, i) => { const ex = (e.examples || [])[0]; return `
    <div class="card note"><div class="mark">✕</div><div class="w">${esc(e.name || e.rule_id)}</div><div class="meta">${e.count}회 · ${esc(e.last || '')}</div>
      ${ex ? `<div class="my">내 문장: <s>${esc(ex.text)}</s><br>→ <em>${esc(ex.fixed)}</em></div>` : ''}
      <div class="srcline">📚 ${esc(e.short || e.name || e.rule_id)} · ${esc(e.rule_id)}</div>
      <button type="button" class="btn ghost" data-i="${i}">이 규칙 연습하기</button></div>`; }).join('')
    : '<div class="empty">말하기에서 틀린 규칙이 여기에 모여요</div>';
  $$('#noteList button[data-i]').forEach(b => b.addEventListener('click', () => { const e = nb.active[+b.dataset.i]; startDrill(e.rule_id, e.name); }));   // 값은 onclick 속성에 넣지 않는다
  $('#noteDone').innerHTML = nb.overcome.length ? `<div class="hint" style="margin:0"><b style="color:var(--ink)">극복한 규칙 ${nb.overcome.length}</b> · 연속 2번 정답</div><div class="overcome">${nb.overcome.map(e => `<span>○ ${esc(e.name || e.rule_id)}</span>`).join('')}</div>` : '';
  $('#noteHint').textContent = nb.local ? '서버 연결 실패 · 이 브라우저에 저장된 오답노트만 보여요' : '';
}
function startDrill(ruleId, name) { S.set({ drillRule: ruleId, drillRuleName: name || '' }); go('drill.html'); }   // 규칙 이름은 서버 /notebook 값 → 연습 화면 제목에 씀
(async function init() { showHealth(); injectChat('notebook'); await render(); })();
