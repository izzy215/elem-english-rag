/* Unit = 말하기 미션 목록. mission 문구는 서버 /units 에 있으면 그것, 없으면 sample-B units.csv */
const state = requireState('level');
async function renderUnits() {
  const lv = state.level.level;
  const [units, nb] = await Promise.all([api(`/api/units?level=${lv}`), fetchNotebook(state.student)]);
  await loadSampleB();
  if (!units.length) { $('#unitCards').innerHTML = '<div class="empty">이 Level에는 아직 미션이 없어요.</div>'; return; }
  $('#unitCards').innerHTML = units.map(u => {
    const meta = unitMeta(u.unit) || {}; const mission = u.mission || meta.mission || `${u.title} 단어로 한 문장 말해봐요`;
    const ruleIds = (u.rule_ids && u.rule_ids.length) ? u.rule_ids : (meta.rule_ids || '').split(';').filter(Boolean);
    const wrong = nb.active.filter(e => ruleIds.includes(e.rule_id)).length;
    const spoken = Object.keys(localStorage).filter(k => k.startsWith(`spoken_${state.student}_${u.unit}_`)).length;
    return `<button class="card" onclick='pickUnit(${JSON.stringify({ unit: u.unit, title: u.title, mission, hint_words: (u.hint_words && u.hint_words.length) ? u.hint_words : (meta.hint_words || '').split(';').filter(Boolean), rule_ids: ruleIds })})'>
      <div class="t">${esc(u.unit)} · ${esc(u.title)} ${wrong ? `<span class="badge b-review">헷갈리는 규칙 ${wrong}</span>` : ''}${spoken >= 5 ? '<span class="badge b-ok">완료 ✓</span>' : ''}</div>
      <div class="d">🎯 ${esc(mission)}</div>
      <div class="d">단어 ${u.words}개 · 말한 문장 ${spoken}</div></button>`;
  }).join('');
}
function pickUnit(u) { S.set({ unit: u, words: null, patterns: null, lastFix: null }); go('learn.html'); }
(async function init() { if (!state) return; renderTopbar(); $('#unitsTitle').textContent = state.level.label; showHealth(); await renderUnits(); })();
