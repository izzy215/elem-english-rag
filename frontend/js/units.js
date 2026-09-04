/* 4.2 Unit 목록 — Unit 카드 + 진행률 → learn.html */

const state = requireState('level');

async function renderUnits() {
  const lv = state.level.level;
  const units = await api(`/api/units?level=${lv}`);
  if (!units.length) {
    $('#unitCards').innerHTML = '<div class="empty">이 Level에는 아직 Unit이 없어요.<br>데이터팀 납품 후 채워집니다.</div>';
    return;
  }
  // 진행률은 Unit마다 따로 조회 (PRD 5.1 /progress)
  const progress = await Promise.all(units.map(u =>
    api(`/api/progress?student=${state.student}&level=${lv}&unit=${u.unit}`).catch(() => null)));
  $('#unitCards').innerHTML = units.map((u, i) => {
    const p = progress[i];
    const pct = p && p.total ? Math.round(p.learned / p.total * 100) : 0;
    const wrong = p && p.wrong_words && p.wrong_words.length;
    return `
    <button class="card unit" onclick='pickUnit(${JSON.stringify(u)})'>
      <div>
        <div class="t">${esc(u.unit)} · ${esc(u.title)}</div>
        <div class="d">단어 ${u.words}개 · 문장 ${u.sentences}개${wrong ? ` · <span style="color:var(--danger)">복습할 단어 ${wrong}</span>` : ''}</div>
      </div>
      <div class="pct">${pct}%</div>
      <div class="prog"><i style="width:${pct}%"></i></div>
    </button>`;
  }).join('');
}

function pickUnit(u) {
  S.set({ unit: { unit: u.unit, title: u.title }, words: null, sentences: null, quizResult: null });
  go('learn.html');
}

(async function init() {
  if (!state) return;
  renderTopbar();
  $('#unitsTitle').textContent = state.level.label;
  showHealth();
  await renderUnits();
})();
