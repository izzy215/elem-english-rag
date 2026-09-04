/* 4.5 오답 설명 — /api/explain. explain.py 구현 전에는 '준비 중' + 교재 예문만 */

const state = requireState('level', 'unit', 'quizResult');

async function renderExplain() {
  const { id: quizId, questions, answers } = state.quizResult;
  const wrong = questions.filter((q, i) => answers[i] && !answers[i].correct);
  if (!wrong.length) {
    $('#explainList').innerHTML = '<div class="empty">틀린 문제가 없어요 🎉</div>';
    return;
  }
  $('#explainList').innerHTML = wrong.map(q => `
    <div class="card explain" id="ex-${q.id}">
      <div class="w">${esc(q.choices[q.answer])} <span class="d">${esc(q.meaning || '')}</span></div>
      <div class="text">설명을 준비하는 중…</div>
    </div>`).join('');

  const words = state.words || [];
  await Promise.all(wrong.map(async q => {
    const el = $(`#ex-${q.id}`);
    let r = null;
    try { r = await api('/api/explain', { method: 'POST', body: JSON.stringify({
      student: state.student, quiz_id: quizId, question_id: q.id }) }); } catch (_) {}
    if (r && r.explanation) {
      $('.text', el).textContent = r.explanation;
      if (r.source && (r.source.page || r.source.text))
        el.insertAdjacentHTML('beforeend', `<div class="src">교재 <b>p.${r.source.page ?? '?'}</b> · ${esc(r.source.text || '')}</div>`);
    } else {
      const w = words.find(x => x.id === q.word_id);
      $('.text', el).innerHTML = `<span class="tag">준비 중</span> AI 설명은 explain.py 구현 후 나와요.` +
        (w ? `<div class="src">교재 <b>p.${w.source_page}</b> · ${esc(w.example)}</div>` : '');
    }
  }));
}

(function init() {
  if (!state) return;
  renderTopbar();
  showHealth();
  renderExplain();
})();
