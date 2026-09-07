/* 4.4 문제 풀기 + 결과 — /api/quiz · /api/answer. 서버가 빈 응답이면 Unit 단어로 임시 문제 → explain.html */

const state = requireState('level', 'unit');
const quiz = { id: null, questions: [], idx: 0, answers: [], mock: false };

function showSection(name) { $$('.screen').forEach(s => s.classList.toggle('on', s.dataset.screen === name)); window.scrollTo(0, 0); }

async function startQuiz() {
  showSection('quiz');
  quiz.idx = 0; quiz.answers = []; quiz.questions = []; quiz.mock = false;
  $('#quizTitle').textContent = `${state.unit.unit} · ${state.unit.title}`;
  $('#quizPage').textContent = '– / –'; $('#quizDots').innerHTML = ''; $('#quizSrc').textContent = '';
  $('#qPrompt').innerHTML = '문제를 만드는 중… <small>(AI가 생각하는 데 최대 30초)</small>';
  $('#qChoices').innerHTML = ''; hideResult('#qResult'); $('#qNextBtn').disabled = true;

  // 서버(quiz.py)가 문제를 주면 그걸, 아직 빈 응답이면 화면에서 임시 문제를 만든다
  try {
    const r = await api('/api/quiz', { method: 'POST', body: JSON.stringify({
      student: state.student, level: state.level.level, unit: state.unit.unit, count: 3 }) });
    if (r.questions && r.questions.length) { quiz.id = r.quiz_id; quiz.questions = r.questions; }
  } catch (_) {}
  if (!quiz.questions.length) { quiz.mock = true; quiz.id = 'mock'; quiz.questions = mockQuiz(3); }
  $('#quizSrc').textContent = quiz.mock
    ? '임시 문제예요 — quiz.py(AI 문제 생성 · 오답 반영) 구현 전까지 Unit 단어로 화면에서 만듭니다'
    : 'AI가 만든 문제';
  renderQuestion();
}

// 임시 문제: Unit 단어 중 n개, 보기는 같은 Unit의 다른 단어 (PRD 5.4 응답 형식과 동일)
function mockQuiz(n) {
  const pool = [...(S.get().words || [])];
  return shuffle(pool).slice(0, Math.min(n, pool.length)).map((w, i) => {
    const others = shuffle(pool.filter(x => x.id !== w.id)).slice(0, 3).map(x => x.word);
    const choices = shuffle([w.word, ...others]);
    return { id: `q${i + 1}`, type: 'choice', word_id: w.id, word: w.word, meaning: w.meaning,
             prompt: `'${w.meaning}'를 영어로?`, choices, answer: choices.indexOf(w.word), source_chunk_id: null };
  });
}

function renderDots() {
  $('#quizDots').innerHTML = quiz.questions.map((_, i) => {
    const a = quiz.answers[i];
    return `<i class="${i === quiz.idx ? 'now' : a ? (a.correct ? 'ok' : 'bad') : ''}"></i>`;
  }).join('');
}
function renderQuestion() {
  const q = quiz.questions[quiz.idx];
  if (!q) { $('#qPrompt').textContent = '문제를 만들 단어가 없어요'; return; }
  $('#quizPage').textContent = `${quiz.idx + 1} / ${quiz.questions.length}`;
  renderDots();
  $('#qPrompt').textContent = q.prompt;
  $('#qChoices').innerHTML = q.choices.map((c, i) =>
    `<button class="choice" onclick="answerQuestion(${i})"><span class="k">${'ABCD'[i]}</span>${esc(c)}</button>`).join('');
  hideResult('#qResult');
  $('#qNextBtn').disabled = true;
  $('#qNextBtn').textContent = quiz.idx === quiz.questions.length - 1 ? '결과 보기' : '다음 문제';
}

async function answerQuestion(choice) {
  const q = quiz.questions[quiz.idx];
  if (quiz.answers[quiz.idx]) return;
  let correct = choice === q.answer, answer = q.answer;
  if (!quiz.mock) {                                          // 서버 채점 + 오답 기록 (PRD /answer)
    try {
      const r = await api('/api/answer', { method: 'POST', body: JSON.stringify({
        student: state.student, quiz_id: quiz.id, question_id: q.id, choice }) });
      if (typeof r.answer === 'number' && r.answer >= 0) { correct = r.correct; answer = r.answer; }
    } catch (_) {}
  }
  quiz.answers[quiz.idx] = { choice, correct, answer };
  $$('#qChoices .choice').forEach((b, i) => {
    b.disabled = true;
    b.classList.add(i === answer ? 'ok' : i === choice ? 'bad' : 'dim');
  });
  showResult('#qResult', correct ? '정답이에요! 🎉' : `아쉬워요. 정답은 <b>${esc(q.choices[answer])}</b>`, correct ? '' : 'bad');
  $('#qNextBtn').disabled = false;
  renderDots();
}
function nextQuestion() {
  if (quiz.idx < quiz.questions.length - 1) { quiz.idx++; renderQuestion(); return; }
  finishQuiz();
}

function finishQuiz() {
  const total = quiz.questions.length, ok = quiz.answers.filter(a => a && a.correct).length;
  const wrong = quiz.questions.filter((q, i) => quiz.answers[i] && !quiz.answers[i].correct);
  showSection('done');
  $('#doneTitle').textContent = wrong.length ? '다 풀었어요!' : '완벽해요! 🎉';
  $('#doneSub').textContent = wrong.length ? `틀린 단어 ${wrong.length}개는 설명을 보고 다시 풀어봐요` : '이 Unit 단어는 다 아는 것 같아요';
  $('#doneScore').textContent = `${ok} / ${total}`;
  $('#doneList').innerHTML = quiz.questions.map((q, i) => {
    const a = quiz.answers[i];
    return `<div class="card wrong">
      <div class="mark ${a.correct ? 'ok' : 'bad'}">${a.correct ? '○' : '✕'}</div>
      <div class="w">${esc(q.choices[q.answer])}</div>
      <div class="d">${esc(q.prompt)}${a.correct ? '' : ` · 내 답: ${esc(q.choices[a.choice])}`}</div>
    </div>`;
  }).join('');
  $('#explainBtn').hidden = !wrong.length;
  // 오답 설명 화면이 쓸 결과 저장
  S.set({ quizResult: { id: quiz.id, mock: quiz.mock, questions: quiz.questions, answers: quiz.answers } });
}
function goExplain() { go('explain.html'); }

(function init() {
  if (!state) return;
  renderTopbar();
  showHealth();
  startQuiz();
})();
