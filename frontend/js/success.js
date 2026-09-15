/* 미션 성공 (유닛 흐름 3단계, 목업 9/15) — 이 유닛에서 한 것을 숫자로 보여 주고 다음 유닛 / 한 번 더 / 홈 으로 보낸다
 * 숫자는 전부 브라우저 sessionStorage 값: 익힌 표현 = patDone[unit] 통과 수, 말한 문장·고친 규칙 = FLOW[unit].sentences. 서버 호출은 다음 유닛 찾기(/api/units)뿐 */
const state = requireState('level', 'unit');
let NEXT = null;
function goNext() {
  if (!NEXT) { go('units.html'); return; }
  S.set({ unit: NEXT, words: null, patterns: null, lastFix: null }); go('learn.html');   // units.js pickUnit 과 같은 초기화
}
function again() { FLOW.reset(state.unit.unit); const pd = S.get().patDone || {}; delete pd[state.unit.unit]; S.set({ patDone: pd, words: null, patterns: null, lastFix: null }); go('learn.html'); }
(async function init() {
  if (!state) return; renderTopbar(); renderFlow(3); showHealth(); injectChat('success');
  const u = state.unit, f = FLOW.get(u.unit), pats = ((S.get().patDone || {})[u.unit]) || [];
  const ss = f.sentences || [], rules = new Set(ss.map(x => x.rule_id).filter(Boolean));
  $('#doneSub').textContent = `${u.unit} ${u.title} 를 끝냈어요`;
  $('#nPat').textContent = pats.length; $('#nSent').textContent = ss.length; $('#nRule').textContent = rules.size;
  if (!ss.length) $('#doneTitle').textContent = '아직 미션 문장이 없어요';
  $('#doneList').innerHTML = `<div class="lbl">오늘 말한 문장</div>` + (ss.length ? ss.map(x => `<div class="row"><span class="en">${esc(x.ok ? x.text : (x.fixed || x.text))}</span>${x.ok ? '<span class="badge" style="background:var(--primary-soft);color:var(--primary)">바로 ✓</span>' : `<span class="badge" style="background:var(--accent-soft);color:#A9690F">고쳐서 ✓${x.rule_id ? ' · ' + esc(x.rule_id) : ''}</span>`}</div>`).join('') : `<div class="row"><span class="en" style="color:var(--muted)">말해보기에서 미션 문장을 3개 모으면 여기에 나와요</span></div>`);
  if (rules.size) $('#nbHint').style.display = '';
  NEXT = await nextUnit();
  $('#nextSub').textContent = NEXT ? `${NEXT.unit} ${NEXT.title}` : '이 레벨의 마지막 유닛이에요 · 유닛 목록으로';
  if (!NEXT) $('#nextBtn').firstChild.textContent = '유닛 목록으로 →';
})();
