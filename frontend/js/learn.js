/* 표현 익히기 = 단어 듣기 + 문장 패턴 듣기 + 따라 말하기(STT 채점) 를 한 화면에 (목업 9/14 "합친 안" 채택. 옛 shadow.html 은 여기로 넘어온다)
 * 단어(탭하면 TTS) · 패턴(서버 /patterns, 없으면 /sentences, 그것도 없으면 화면 sample-B) · 따라 말하기(/tts 듣기 + /speak 채점, 팀원 API 그대로)
 * 통과(70점 이상)한 패턴은 단계 칩에 ✓ — 같은 세션 안에서 유지(sessionStorage patDone[unit]) */
const state = requireState('level', 'unit');
let words = [], pats = [], pi = 0, teacherWave = null, teacherWaveP = null, autoAll = false;
const LIKE = [null, ['🌱', '조금 달라요 — 선생님 소리를 다시 들어볼까요?'], ['🌿', '꽤 비슷해요!'], ['🌳', '거의 똑같아요! 👏']];
// 서버가 pronunciation_level("상/중/하")을 주면 그걸, 옛 pronunciation_score(0~100)만 있으면 임시 경계값으로
const likeLevel = r => r.pronunciation_level ? ({ '상': 3, '중': 2, '하': 1 }[r.pronunciation_level] || 0)
  : r.pronunciation_score == null ? 0 : r.pronunciation_score >= 60 ? 3 : r.pronunciation_score >= 40 ? 2 : 1;

// ── 통과 기록 (유닛별 패턴 id) ──
const doneSet = () => new Set(((S.get().patDone || {})[state.unit.unit]) || []);
function markDone(id) { const all = S.get().patDone || {}; const u = new Set(all[state.unit.unit] || []); u.add(id); all[state.unit.unit] = [...u]; S.set({ patDone: all }); }

async function loadData() {
  const lv = state.level.level, unit = state.unit.unit;
  words = await api(`/api/words?level=${lv}&unit=${unit}`).catch(() => []);
  // 1) 서버 /patterns → 2) 서버 /sentences (A 샘플, TTS 되는 id) → 3) 화면 sample-B patterns.csv (TTS·채점 안 됨)
  try { pats = await api(`/api/patterns?level=${lv}&unit=${unit}`); }
  catch (_) {
    pats = (await api(`/api/sentences?level=${lv}&unit=${unit}`).catch(() => [])).map(s => ({ id: s.id, text: s.sentence, meaning: s.meaning, tip: '' }));
    if (!pats.length) { await loadSampleB(); pats = SB.patterns.filter(p => p.unit === unit).map(p => ({ id: p.id, text: p.text, meaning: p.meaning, tip: p.tip, rule_id: p.rule_id, noAudio: true })); }
  }
  S.set({ words, patterns: pats });
}

// ── 단어: 누르면 듣기. 첫 재생은 서버가 음원을 만들어 몇 초 걸림 — 누른 칩은 점선(로딩), 다른 칩은 그동안 잠김. 마지막에 누른 것만 재생 (common.playTTS) ──
function renderWords() {
  $('#wordCnt').textContent = `${words.length}개`;
  $('#wordRow').innerHTML = words.map(w => `<button type="button" class="mini" data-id="${esc(w.id)}" data-tts-group="words" data-tts-keep="1"><b>${esc(w.word)}</b>${esc(w.meaning)}</button>`).join('') || '<div class="empty">단어가 없어요</div>';
  $$('#wordRow button[data-id]').forEach(b => b.addEventListener('click', () => playWord(b.dataset.id, b)));
}
async function playWord(id, btn) {
  hideResult('#learnResult');
  try { await playTTS(id, btn); } catch (e) { showResult('#learnResult', '듣기 실패: ' + esc(e.message), 'todo'); }
}

// ── 패턴: 단계 칩 + 카드 ──
function renderStep() {
  const done = doneSet();
  // 유닛에 패턴이 8개까지 있어 좁은 화면에서 칩이 넘치지 않게: 현재 = "▶ 지금", 통과 = "✓", 나머지 = 번호만 (칩은 줄바꿈 허용)
  $('#patStep').innerHTML = pats.map((p, i) => `<span class="${i === pi ? 'cur' : ''} ${done.has(p.id) ? 'done' : ''}" data-i="${i}" title="${esc(p.text)}">${i === pi ? (done.has(p.id) ? '✓ 지금' : '▶ 지금') : done.has(p.id) ? '✓' : String(i + 1)}</span>`).join('');
  $$('#patStep span[data-i]').forEach(el => el.addEventListener('click', () => { pi = +el.dataset.i; renderPat(); }));
  $('#goTutor').classList.toggle('glow', pats.length > 0 && pats.every(p => done.has(p.id)));
}
function renderPat() {
  const p = pats[pi];
  if (!p) { $('#patCard').innerHTML = '<div class="word">패턴이 없어요</div>'; $('#patStep').innerHTML = ''; return; }
  $('#patCard').innerHTML = `<div class="word">${esc(p.text)}</div><div class="mean">${esc(p.meaning)}</div>${p.tip ? `<div class="ex">💡 ${esc(p.tip)}</div>` : ''}`;
  ['#shWave', '#shHeard', '#shResult', '#shLike'].forEach(q => $(q).style.display = 'none'); hideResult('#learnResult');
  const b = $('#shRec'); b.classList.remove('rec'); b.textContent = '🎙 따라 말하기'; b.onclick = record;
  $('#wvTTxt').textContent = p.text; renderStep(); S.set({ patIdx: pi }); loadTeacherWave(p);
}
function movePat(d) { if (!pats.length) return; pi = (pi + d + pats.length) % pats.length; renderPat(); }
async function playPattern() {
  const p = pats[pi]; if (!p) return; hideResult('#learnResult');
  if (p.noAudio) { showResult('#learnResult', '이 패턴은 서버에 없는 화면 샘플이라 음원이 없어요 (서버 patterns.csv 반영 후 가능)', 'todo'); return; }
  try { await playTTS(p.id, $('#patTts')); if (!teacherWave) await loadTeacherWave(p); }
  catch (e) { showResult('#learnResult', /없음|404|Not Found/.test(e.message) ? '이 문장은 서버가 모르는 id예요 (음원 없음)' : '듣기 실패: ' + esc(e.message), 'todo'); }
}

// ── 따라 말하기: 선생님 파형은 문장이 바뀌면 백그라운드로 받아 계산 (같은 id 는 한 번만) ──
function loadTeacherWave(p) {
  if (!p || p.noAudio) { teacherWave = null; teacherWaveP = Promise.resolve(null); return teacherWaveP; }
  teacherWave = null;
  teacherWaveP = fetch(`/api/tts/${p.id}`).then(r => r.ok ? r.blob() : null).then(b => b ? waveFromBlob(b) : null).catch(() => null).then(w => (teacherWave = w));
  return teacherWaveP;
}
async function record() {
  const p = pats[pi]; if (!p || BUSY) return; const btn = $('#shRec');
  if (p.noAudio) { showResult('#learnResult', '이 패턴은 서버에 없는 화면 샘플이라 채점이 안 돼요', 'todo'); return; }
  let stopFn = null; btn.classList.add('rec'); btn.textContent = '⏺ 녹음 중… (누르면 끝)'; btn.onclick = () => stopFn && stopFn();
  showResult('#learnResult', '따라 말해 보세요: ' + esc(p.text));
  try {
    const { blob, b64, mime } = await recordOnce({ maxMs: 5000, onStart: s => stopFn = s });
    btn.classList.remove('rec'); btn.textContent = '🎙 따라 말하기'; btn.onclick = record;
    showResult('#learnResult', '채점 중… (몇 초 걸려요)');
    const [myWave, r] = await Promise.all([waveFromBlob(blob), speak(b64, p.id, '🎧 채점 중… 잠깐만요', mime)]);
    if (!teacherWave) await (teacherWaveP || loadTeacherWave(p));   // 듣기를 안 눌렀어도 선생님 파형은 그린다
    $('#shWave').style.display = 'block'; drawWave($('#wvT'), teacherWave); drawWave($('#wvM'), myWave);
    $('#wvTTxt').textContent = teacherWave ? p.text : '(선생님 음원 없음)'; $('#wvMTxt').textContent = r.heard || '';
    $('#shHeard').style.display = 'block'; $('#shHeardS').textContent = r.heard || '(안 들렸어요)';
    if (r.error) { showResult('#learnResult', '채점 실패: ' + esc(r.error), 'bad'); return; }
    const ok = r.passed; const el = $('#shResult'); el.style.display = 'block';
    el.innerHTML = `<div class="type ${ok ? 'ok' : ''}">${ok ? '✓ 잘 들렸어요' : '✕ 한 번 더 해볼까요?'}</div><div class="fixed" style="color:${ok ? 'var(--primary)' : 'var(--danger)'}">${esc(r.score)}점</div><div class="why">원문: ${esc(r.expected)}<br>들린 말: ${esc(r.heard)}</div>`;
    if (r.pronunciation_level || r.pronunciation_score != null) { const lv = likeLevel(r); $('#shLike').style.display = 'block'; $('#shLv').innerHTML = [1, 2, 3].map(i => `<span class="${i <= lv ? 'on' : ''}"></span>`).join('') + `<b>${LIKE[lv][0]}</b>`; $('#shLikeMsg').textContent = LIKE[lv][1]; }
    hideResult('#learnResult'); localStorage.setItem(`spoken_${state.student}_${state.unit.unit}_${p.id}_${Date.now()}`, '1');
    if (ok) { markDone(p.id); renderStep(); }
    if (autoAll && ok && pi < pats.length - 1) setTimeout(() => { if (!autoAll) return; movePat(1); record(); }, 1300);   // 전부 따라 말하기: 통과하면 다음 문장으로 이어서
    else if (autoAll && pi === pats.length - 1) toggleAll(false);
  } catch (e) { btn.classList.remove('rec'); btn.textContent = '🎙 따라 말하기'; btn.onclick = record; showResult('#learnResult', esc(e.message), 'bad'); if (autoAll) toggleAll(false); }
}
function toggleAll(force) {
  autoAll = typeof force === 'boolean' ? force : !autoAll;
  $('#allBtn').textContent = autoAll ? '⏹ 순서대로 멈추기' : '▶ 전부 따라 말하기 (순서대로)';
  if (autoAll) { const done = doneSet(); const first = pats.findIndex(p => !done.has(p.id)); pi = first < 0 ? 0 : first; renderPat(); record(); }
}
(async function init() {
  if (!state) return; renderTopbar(); showHealth(); injectChat('learn');
  await loadData(); pi = S.get().patIdx || 0; if (pi >= pats.length) pi = 0; renderWords(); renderPat();
  const why = micSupport(); if (why) { showResult('#learnResult', '🎙 ' + esc(why) + ' 듣기는 돼요.', 'todo'); $('#shRec').disabled = true; $('#allBtn').disabled = true; }
})();
