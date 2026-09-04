/* 4.3 학습 — 단어 카드 → 문장 카드 · 듣기(TTS) · 따라 말하기(STT) → quiz.html */

const state = requireState('level', 'unit');
const L = { words: [], sentences: [], phase: 'words', idx: 0, learned: new Set() };

// ---------- 카드 ----------
function cards() { return L.phase === 'words' ? L.words : L.sentences; }
function current() { return cards()[L.idx]; }

function renderCard() {
  const list = cards(), c = current(), isWord = L.phase === 'words';
  $('#learnPhase').textContent = isWord ? '단어 카드' : '문장 카드';
  $('#learnPage').textContent = list.length ? `${L.idx + 1} / ${list.length}` : '';
  $('#learnCnt').textContent = `단어 ${L.words.length} · 문장 ${L.sentences.length}`;
  $('#ph1').className = isWord ? 'now' : 'done';
  $('#ph2').className = isWord ? '' : 'now';

  if (!c) {
    $('#fWord').textContent = '카드가 없어요';
    ['#fMean', '#fEx', '#fSrc', '#dots'].forEach(s => $(s).textContent = '');
    return;
  }
  $('#fWord').className = 'word' + (isWord ? '' : ' sent');
  $('#fWord').textContent = isWord ? c.word : c.sentence;
  $('#fMean').textContent = c.meaning;
  $('#fEx').textContent = isWord ? c.example : '';
  $('#fSrc').innerHTML = c.source_page ? `교재 <b>p.${c.source_page}</b>` : '';
  $('#dots').innerHTML = list.map((x, i) =>
    `<i class="${i === L.idx ? 'now' : L.learned.has(x.id) ? 'done' : ''}"></i>`).join('');

  $('#prevBtn').disabled = isWord && L.idx === 0;
  const last = L.idx === list.length - 1;
  $('#nextBtn').textContent = !isWord && last ? '다 봤어요' : (isWord && last ? '문장 카드로' : '다음');
  hideResult('#result');
  L.learned.add(c.id);
  updateQuizBtn();
}
function updateQuizBtn() {
  const allWords = L.words.length && L.words.every(w => L.learned.has(w.id));
  $('#quizBtn').disabled = !allWords;
  $('#learnHint').textContent = allWords
    ? '단어를 다 봤어요. 문장까지 보거나 바로 문제를 풀 수 있어요.'
    : '단어 카드를 다 보면 문제를 풀 수 있어요.';
}
function nextCard() {
  const list = cards();
  if (L.idx < list.length - 1) { L.idx++; renderCard(); return; }
  if (L.phase === 'words' && L.sentences.length) { L.phase = 'sentences'; L.idx = 0; renderCard(); return; }
  goQuiz();
}
function prevCard() {
  if (L.idx > 0) { L.idx--; renderCard(); return; }
  if (L.phase === 'sentences') { L.phase = 'words'; L.idx = L.words.length - 1; renderCard(); }
}
function goQuiz() { go('quiz.html'); }

// ---------- 듣기 (D. TTS — 구현 전엔 '준비 중') ----------
function stopAudio() { const p = $('#player'); p.pause(); p.currentTime = 0; $('#ttsBtn').classList.remove('on'); }
async function playTTS() {
  const c = current(); if (!c) return;
  const p = $('#player'), btn = $('#ttsBtn');
  btn.classList.add('on'); btn.textContent = '🔊 …';
  try {
    const r = await fetch(`/api/tts/${c.id}`);
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw Object.assign(new Error(d.detail || r.statusText), { status: r.status }); }
    p.src = `/api/tts/${c.id}`;
    await p.play();
    p.onended = () => { btn.classList.remove('on'); btn.textContent = '🔊 듣기'; };
  } catch (e) {
    btn.classList.remove('on'); btn.textContent = '🔊 듣기';
    showResult('#result', e.status === 501 ? '듣기는 준비 중이에요 (TTS 담당 구현 예정)' : '음성을 불러오지 못했어요: ' + e.message, 'todo');
  }
}

// ---------- 따라 말하기 (E. STT — 녹음은 브라우저, 채점은 서버) ----------
let recorder = null, chunks = [], recTimer = null;
async function toggleRec() {
  if (recorder) { recorder.stop(); return; }
  const c = current(); if (!c) return;
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { showResult('#result', '마이크를 사용할 수 없어요. 브라우저 권한을 확인하세요.', 'bad'); return; }
  chunks = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = e => chunks.push(e.data);
  recorder.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    clearTimeout(recTimer); recorder = null;
    $('#recBtn').classList.remove('rec'); $('#recBtn').textContent = '🎙 따라 말하기';
    const blob = new Blob(chunks, { type: 'audio/webm' });
    const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(',')[1]); fr.readAsDataURL(blob); });
    showResult('#result', '채점 중…');
    try {
      const r = await api('/api/speak', { method: 'POST', body: JSON.stringify({
        student: state.student, item_id: c.id, audio_base64: b64, mime: 'audio/webm' }) });
      if (r.todo) { showResult('#result', `말하기 평가는 준비 중이에요 (녹음 ${Math.round(blob.size / 1024)}KB 전송됨 · STT 담당 구현 예정)`, 'todo'); return; }
      showResult('#result', `<span class="score">${r.score}점</span> ${r.passed ? '잘했어요! 🎉' : '한 번 더 해볼까요?'}<br><small>들린 말: "${esc(r.heard)}" · 정답: "${esc(r.expected)}"</small>`, r.passed ? '' : 'bad');
    } catch (e) { showResult('#result', '채점 실패: ' + e.message, 'bad'); }
  };
  recorder.start();
  $('#recBtn').classList.add('rec'); $('#recBtn').textContent = '⏺ 녹음 중… (누르면 끝)';
  showResult('#result', '따라 말해 보세요: ' + (L.phase === 'words' ? c.word : c.sentence));
  recTimer = setTimeout(() => recorder && recorder.stop(), 4000);     // 최대 4초
}

// ---------- 시작 ----------
(async function init() {
  if (!state) return;
  renderTopbar();
  showHealth();
  $('#learnTitle').textContent = `${state.unit.unit} · ${state.unit.title}`;
  const lv = state.level.level, unit = state.unit.unit;
  [L.words, L.sentences] = await Promise.all([
    api(`/api/words?level=${lv}&unit=${unit}`),
    api(`/api/sentences?level=${lv}&unit=${unit}`),
  ]);
  S.set({ words: L.words, sentences: L.sentences });   // 문제 화면(임시 문제·오답 설명)이 쓴다
  renderCard();
})();
