/* 규칙 연습 — 서버 /drill 이 정식 (규칙 이름 rule_name · 정답 뒤 규칙 문구 rule_text 도 서버가 준다). 다 맞히면 streak+1 (연속 2회 = 극복)
 * 서버 /drill 자체가 없을 때(404/405)만 sample-B errors.jsonl 로 임시 출제. 서버가 "그 규칙의 문제 없음"(404) 을 주면 샘플로 덮지 않고 그대로 알린다 (id 체계가 달라 다른 규칙 문제가 나온다) */
const state = requireState('drillRule');
const student = S.get().student || 'A';
let qs = [], qi = 0, okCount = 0, drillId = null, local = false, ruleName = S.get().drillRuleName || '', ruleTextLocal = '';

async function load() {
  $('#drillTitle').textContent = `${ruleName || state.drillRule} 연습`;   // 오답노트가 넘겨 준 서버 규칙 이름. /drill 응답이 오면 그걸로
  try { const r = await api(`/api/drill?student=${student}&rule=${state.drillRule}&count=2`); drillId = r.drill_id; qs = r.questions; if (r.rule_name) { ruleName = r.rule_name; $('#drillTitle').textContent = `${ruleName} 연습`; } }
  catch (e) {
    const noRoute = !e.status || e.status === 405 || (e.status === 404 && !/연습 문제가 없음/.test(e.message));
    if (!noRoute) { $('#drillSent').textContent = e.status === 404 ? '이 규칙은 아직 연습 문제가 없어요' : '연습 문제를 가져오지 못했어요: ' + e.message; $('#drillHint').textContent = e.status === 404 ? '' : '서버 연결 실패 · 잠시 후 다시 열어 보세요'; return; }
    local = true; await loadSampleB(); ruleTextLocal = ruleOf(state.drillRule)?.text || '';
    qs = shuffle(SB.errors.filter(x => x.rule_id === state.drillRule)).slice(0, 2).map((x, i) => ({ id: 'd' + i, sentence: x.error, target: x.target, choices: shuffle([x.fix, ...x.distractors]), answer: null, fix: x.fix }));
    qs.forEach(q => q.answer = q.choices.indexOf(q.fix));
    $('#drillHint').textContent = qs.length ? '서버 연결 실패 · 화면 샘플로 임시 출제 (규칙 이름·문제가 실제와 다를 수 있어요)' : '서버 연결 실패';
  }
  if (!qs.length) { $('#drillSent').textContent = '이 규칙은 아직 연습 문제가 없어요'; return; }
  render();
}
function render() {
  const q = qs[qi]; $('#drillPage').textContent = `${qi + 1} / ${qs.length}`;
  const s = String(q.sentence), m = new RegExp('(^|[^A-Za-z])(' + escapeRe(q.target) + ')(?![A-Za-z])').exec(s);   // target 에 . 이 있어도(E-0009 "Please help me.") 밑줄이 되게 — 정규식 이스케이프 + \b 대신 글자 경계
  $('#drillSent').innerHTML = m ? esc(s.slice(0, m.index + m[1].length)) + '<u>' + esc(m[2]) + '</u>' + esc(s.slice(m.index + m[0].length)) : esc(s);
  $('#drillChoices').innerHTML = q.choices.map((c, i) => `<button class="choice" onclick="answer(${i})"><span class="k">${'ABCD'[i]}</span>${esc(c)}</button>`).join('');
  hideResult('#drillResult'); $('#drillSrc').style.display = 'none'; $('#drillNext').disabled = true; $('#drillNext').textContent = qi === qs.length - 1 ? '끝' : '다음';
}
async function answer(i) {
  const q = qs[qi]; let correct = i === q.answer, ans = q.answer, ruleText = ruleTextLocal;
  if (!local) { try { const r = await api('/api/drill/answer', { method: 'POST', body: JSON.stringify({ student, drill_id: drillId, question_id: q.id, choice: i }) }); correct = r.correct; ans = r.answer; ruleText = r.rule_text || ruleText; } catch (_) {} }
  $$('#drillChoices .choice').forEach((b, j) => { b.disabled = true; b.classList.add(j === ans ? 'ok' : j === i ? 'bad' : 'dim'); });
  showResult('#drillResult', correct ? '정답이에요! 🎉' : `아쉬워요. 정답은 ${esc(q.choices[ans])}`, correct ? '' : 'bad');
  $('#drillSrc').style.display = ruleText ? 'block' : 'none'; $('#drillSrc').innerHTML = `📚 ${esc(ruleText)}`; if (correct) okCount++; $('#drillNext').disabled = false;
}
function next() { if (qi < qs.length - 1) { qi++; render(); return; } NB.drillResult(student, state.drillRule, okCount === qs.length); go('notebook.html'); }   // 로컬 오답노트도 같이 갱신 (화면은 서버 /notebook 을 먼저 쓴다)
(async function init() { if (!state) return; renderTopbar({ crumbs: false }); showHealth(); injectChat('drill'); await load(); })();
