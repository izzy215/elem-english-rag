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
  // 패턴 3개(패턴이 3개 미만이면 전부) 통과하면 "말해보기"가 빛난다. 잠그지는 않는다 (9/15 팀장: 테스트 편하게 늘 열어 두기)
  const need = Math.min(3, pats.length), got = pats.filter(p => done.has(p.id)).length;
  $('#patCnt').textContent = pats.length ? `${got} / ${pats.length}` : '';
  $('#goTutor').classList.toggle('glow', pats.length > 0 && got >= need);
  $('#goTutorSub').textContent = got >= need ? '준비됐어요! 미션 문장을 말해봐요' : `패턴 ${pats.length}개 중 ${got}개 통과 · 3개 통과하면 빛나요`;
}
function goTutor() { FLOW.set(state.unit.unit, { learned: true }); go('tutor.html'); }
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
// /speak 결과를 화면에 그린다 (9/17). 돌려주는 값: true=통과, false=점수는 나왔지만 미달, null=점수 없이 안내만.
//   heard 가 비어 있으면 "(안 들렸어요)" — Whisper 가 아무 말도 못 알아들은 경우(무음·너무 짧음)
//   한글만 있으면 "영어로 말해 주세요", 한글과 영어가 섞여 있으면 "영어로만 한 번 더" — 따라 말하기는 영어 문장이라 점수를 매기지 않는다
// 영어(라틴 글자)가 아닌 글자가 있으면 어느 말인지 이름을 돌려준다 (없으면 ''). Whisper 가 중국어·아랍어로 알아듣는 일도 있어서 한글만 보지 않는다
const SCRIPT_NAMES = [['Hangul', '한국어'], ['Han', '중국어'], ['Hiragana', '일본어'], ['Katakana', '일본어'], ['Arabic', '아랍어'], ['Cyrillic', '러시아어'], ['Thai', '태국어'], ['Devanagari', '힌디어'], ['Hebrew', '히브리어'], ['Greek', '그리스어']];
// 라틴 글자를 쓰는 다른 말(불어·스페인어·독일어·이탈리아어·포르투갈어)은 글자로 못 가르니 흔한 낱말로 추정 — 두 개 이상 겹치고 영어 점수가 낮을 때만
const LATIN_LANGS = [
  ['프랑스어', 'le la les des un une est et je tu il elle nous vous ils sont pas ne que qui dans avec pour mon ma mes ton ta bonjour merci oui non très'],
  ['스페인어', 'el la los las un una es y yo tú él ella nosotros son no que con para mi mis hola gracias sí muy pero está'],
  ['독일어', 'der die das ein eine ist und ich du er sie wir sind nicht mit für mein meine hallo danke ja nein sehr aber'],
  ['이탈리아어', 'il lo la gli le un una è e io tu lui lei noi sono non che con per mio mia ciao grazie sì molto ma'],
  ['포르투갈어', 'o os as um uma é e eu tu ele ela nós são não que com para meu minha olá obrigado sim muito mas'],
].map(([n, w]) => [n, new Set(w.split(' '))]);
const ACCENTS = /[àâäáãåæçèéêëìíîïñòóôöõøùúûüýÿœß]/i;
function latinLanguage(text) {
  const words = text.toLowerCase().replace(/[^\p{L}' ]/gu, ' ').split(/\s+/).filter(Boolean);
  let best = ['', 0];
  for (const [name, set] of LATIN_LANGS) { const n = words.filter(w => set.has(w)).length; if (n > best[1]) best = [name, n]; }
  if (best[1] >= 2) return best[0];
  return ACCENTS.test(text) && best[1] >= 1 ? best[0] : '';
}
const LANG_NAMES = { ko: '한국어', zh: '중국어', ja: '일본어', ar: '아랍어', ru: '러시아어', fr: '프랑스어', es: '스페인어', de: '독일어', it: '이탈리아어', pt: '포르투갈어', th: '태국어', hi: '힌디어', vi: '베트남어' };
function otherLanguage(text, r) {
  if (r && r.language && r.language !== 'en') return LANG_NAMES[r.language] || '다른 언어';   // 서버가 감지한 언어가 응답에 오면 그걸 믿는다 (TTS 담당에게 요청)
  for (const [script, name] of SCRIPT_NAMES) if (new RegExp('\\p{Script=' + script + '}', 'u').test(text)) return name;
  if ([...text].some(c => /\p{L}/u.test(c) && !/\p{Script=Latin}/u.test(c))) return '다른 언어';
  return (r && (r.score || 0) < 40) ? latinLanguage(text) : '';
}
function renderSpeakResult(r, p) {
  const heard = (r.heard || '').trim(), other = otherLanguage(heard, r), hasKo = !!other;
  const hasEn = /\p{Script=Latin}/u.test(heard) && !LATIN_LANGS.some(([n]) => n === other);   // 라틴 글자를 쓰는 다른 말로 판정됐으면 '영어 섞임'이 아니라 '영어 아님'으로
  $('#shHeard').style.display = 'block'; $('#shHeardS').textContent = heard || '(안 들렸어요)';
  $('#shLike').style.display = 'none';
  const el = $('#shResult'); el.style.display = 'block';
  if (r.error) { el.style.display = 'none'; showResult('#learnResult', '채점 실패: ' + esc(r.error), 'bad'); return null; }
  if (!heard) { el.innerHTML = `<div class="type">🎙 소리가 안 들렸어요</div><div class="why">마이크에 가까이 대고 또박또박 말해 볼까요? 원문: ${esc(r.expected || p.text)}</div>`; hideResult('#learnResult'); return null; }
  if (hasKo && !hasEn) { el.innerHTML = `<div class="type">🗣️ 영어로 말해 주세요</div><div class="why">${esc(other)}로 들렸어요. 이 문장을 영어로 따라 말해 봐요: <b>${esc(r.expected || p.text)}</b><br>들린 말: ${esc(heard)}</div>`; hideResult('#learnResult'); return null; }
  if (hasKo && hasEn) { el.innerHTML = `<div class="type">✕ 한 번 더 해볼까요?</div><div class="why">${esc(other)}와 영어가 섞여 들렸어요. 영어로만 말해 봐요: <b>${esc(r.expected || p.text)}</b><br>들린 말: ${esc(heard)}</div>`; hideResult('#learnResult'); return null; }
  const ok = !!r.passed;
  el.innerHTML = `<div class="type ${ok ? 'ok' : ''}">${ok ? '✓ 잘 들렸어요' : '✕ 한 번 더 해볼까요?'}</div><div class="fixed" style="color:${ok ? 'var(--primary)' : 'var(--danger)'}">${esc(r.score)}점</div><div class="why">원문: ${esc(r.expected)}<br>들린 말: ${esc(heard)}</div>`;
  if (r.pronunciation_level || r.pronunciation_score != null) { const lv = likeLevel(r); $('#shLike').style.display = 'block'; $('#shLv').innerHTML = [1, 2, 3].map(i => `<span class="${i <= lv ? 'on' : ''}"></span>`).join('') + `<b>${LIKE[lv][0]}</b>`; $('#shLikeMsg').textContent = LIKE[lv][1]; }
  hideResult('#learnResult');
  return ok;
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
    const ok = renderSpeakResult(r, p);
    if (ok == null) { if (autoAll) toggleAll(false); return; }          // 안 들림·한국어·섞임: 점수 없이 안내만, 통과 아님
    localStorage.setItem(`spoken_${state.student}_${state.unit.unit}_${p.id}_${Date.now()}`, '1');
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
  if (!state) return; renderTopbar(); renderFlow(1); showHealth(); injectChat('learn');
  await loadData(); pi = S.get().patIdx || 0; if (pi >= pats.length) pi = 0; renderWords(); renderPat();
  const why = micSupport(); if (why) { showResult('#learnResult', '🎙 ' + esc(why) + ' 듣기는 돼요.', 'todo'); $('#shRec').disabled = true; $('#allBtn').disabled = true; }
})();
