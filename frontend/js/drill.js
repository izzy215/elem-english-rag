/* 규칙 연습 — 서버 /drill 우선, 없으면 sample-B errors.jsonl 에서 2문제. 다 맞히면 streak+1 (연속 2회 = 극복) */
const state = requireState('drillRule');
const student = S.get().student || 'A';
let qs = [], qi = 0, okCount = 0, drillId = null, local = false;

async function load() {
  await loadSampleB(); const rule = ruleOf(state.drillRule); $('#drillTitle').textContent = `${rule?.type || state.drillRule} 연습`;
  try { const r = await api(`/api/drill?student=${student}&rule=${state.drillRule}&count=2`); drillId = r.drill_id; qs = r.questions; }
  catch (_) {
    local = true; qs = shuffle(SB.errors.filter(e => e.rule_id === state.drillRule)).slice(0, 2).map((e, i) => ({ id: 'd' + i, sentence: e.error, target: e.target, choices: shuffle([e.fix, ...e.distractors]), answer: null, fix: e.fix }));
    qs.forEach(q => q.answer = q.choices.indexOf(q.fix));
    $('#drillHint').textContent = '서버 /drill 구현 전 · 오류 예시 샘플로 임시 출제';
  }
  if (!qs.length) { $('#drillSent').textContent = '이 규칙의 연습 문제가 아직 없어요'; return; }
  render();
}
function render() {
  const q = qs[qi]; $('#drillPage').textContent = `${qi + 1} / ${qs.length}`;
  $('#drillSent').innerHTML = esc(q.sentence).replace(new RegExp(`\\b${q.target}\\b`), `<u>${esc(q.target)}</u>`);
  $('#drillChoices').innerHTML = q.choices.map((c, i) => `<button class="choice" onclick="answer(${i})"><span class="k">${'ABCD'[i]}</span>${esc(c)}</button>`).join('');
  hideResult('#drillResult'); $('#drillSrc').style.display = 'none'; $('#drillNext').disabled = true; $('#drillNext').textContent = qi === qs.length - 1 ? '끝' : '다음';
}
async function answer(i) {
  const q = qs[qi]; let correct = i === q.answer, ans = q.answer, ruleText = ruleOf(state.drillRule)?.text || '';
  if (!local) { try { const r = await api('/api/drill/answer', { method: 'POST', body: JSON.stringify({ student, drill_id: drillId, question_id: q.id, choice: i }) }); correct = r.correct; ans = r.answer; ruleText = r.rule_text || ruleText; } catch (_) {} }
  $$('#drillChoices .choice').forEach((b, j) => { b.disabled = true; b.classList.add(j === ans ? 'ok' : j === i ? 'bad' : 'dim'); });
  showResult('#drillResult', correct ? '정답이에요! 🎉' : `아쉬워요. 정답은 ${esc(q.choices[ans])}`, correct ? '' : 'bad');
  $('#drillSrc').style.display = 'block'; $('#drillSrc').innerHTML = `📚 ${esc(ruleText)}`; if (correct) okCount++; $('#drillNext').disabled = false;
}
function next() { if (qi < qs.length - 1) { qi++; render(); return; } if (local) NB.drillResult(student, state.drillRule, okCount === qs.length); go('notebook.html'); }
(async function init() { if (!state) return; renderTopbar({ crumbs: false }); showHealth(); injectChat('drill'); await load(); })();
