/* Unit = 말하기 미션 목록. mission · hint_words · rule_ids 는 서버 /units 값만 쓴다 (sample-B units.csv 안 봄) */
const state = requireState('level');
let UNITS = [];   // 카드 index → 서버 유닛 (JSON 을 onclick 속성에 넣지 않고 index 로 찾는다)
async function renderUnits() {
  const lv = state.level.level;
  const [units, nb] = await Promise.all([api(`/api/units?level=${lv}`), fetchNotebook(state.student)]);
  if (!units.length) { $('#unitCards').innerHTML = '<div class="empty">이 Level에는 아직 미션이 없어요.</div>'; return; }
  UNITS = units.map(u => ({ unit: u.unit, title: u.title, mission: u.mission || `${u.title} 단어로 한 문장 말해봐요`, hint_words: u.hint_words || [], rule_ids: u.rule_ids || [] }));
  $('#unitCards').innerHTML = units.map((u, i) => {
    const m = UNITS[i];
    const wrong = nb.active.filter(e => m.rule_ids.includes(e.rule_id)).length;
    const spoken = nb.stats ? (nb.stats.by_unit[u.unit] || 0) : Object.keys(localStorage).filter(k => k.startsWith(`spoken_${state.student}_${u.unit}_`)).length;
    return `<button type="button" class="card" data-i="${i}">
      <div class="t">${esc(u.unit)} · ${esc(u.title)} ${wrong ? `<span class="badge b-review">헷갈리는 규칙 ${wrong}</span>` : ''}${spoken >= 5 ? '<span class="badge b-ok">완료 ✓</span>' : ''}</div>
      <div class="d">🎯 ${esc(m.mission)}</div>
      <div class="d">단어 ${u.words}개 · 말한 문장 ${spoken}</div></button>`;
  }).join('');
  $$('#unitCards button[data-i]').forEach(b => b.addEventListener('click', () => pickUnit(UNITS[+b.dataset.i])));
}
function pickUnit(u) { S.set({ unit: u, words: null, patterns: null, lastFix: null }); go('learn.html'); }
(async function init() { if (!state) return; renderTopbar(); $('#unitsTitle').textContent = state.level.label; showHealth(); await renderUnits(); })();
