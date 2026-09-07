/* 따라 말하기 — /tts(듣기) + /speak(STT 일치율 · pronunciation_score) 는 팀원 완성 API를 그대로 사용 */
const state = requireState('level', 'unit');
let pats = [], pi = 0, teacherWave = null;
const LIKE = [null, ['🌱', '조금 달라요 — 선생님 소리를 다시 들어볼까요?'], ['🌿', '꽤 비슷해요!'], ['🌳', '거의 똑같아요! 👏']];
// 서버가 pronunciation_level("상/중/하")을 주면 그걸, 옛 pronunciation_score(0~100)만 있으면 임시 경계값으로
const likeLevel = r => r.pronunciation_level ? ({ '상': 3, '중': 2, '하': 1 }[r.pronunciation_level] || 0)
  : r.pronunciation_score == null ? 0 : r.pronunciation_score >= 60 ? 3 : r.pronunciation_score >= 40 ? 2 : 1;

function render() {
  const p = pats[pi]; if (!p) { $('#shTarget').textContent = '패턴이 없어요'; return; }
  $('#shTarget').textContent = p.text; $('#shMean').textContent = p.meaning; $('#wvTTxt').textContent = p.text;
  $('#shDots').innerHTML = pats.map((_, i) => `<i class="${i === pi ? 'now' : ''}"></i>`).join('');
  ['#shWave', '#shHeard', '#shResult', '#shLike'].forEach(q => $(q).style.display = 'none'); hideResult('#shNote'); teacherWave = null;
}
function move(d) { pi = (pi + d + pats.length) % pats.length; render(); }
async function playTarget() {
  const p = pats[pi]; if (!p) return;
  if (p.noAudio) { showResult('#shNote', '이 패턴은 서버에 없는 화면 샘플이라 음원·채점이 안 돼요', 'todo'); return; }
  try { await playTTS(p.id, $('#shTts')); if (!teacherWave) { const b = await (await fetch(`/api/tts/${p.id}`)).blob(); teacherWave = await waveFromBlob(b); } }
  catch (e) { showResult('#shNote', /없음|404|Not Found/.test(e.message) ? '이 문장은 서버가 모르는 id예요 (음원 없음)' : '듣기 실패: ' + esc(e.message), 'todo'); }
}
async function record() {
  const p = pats[pi]; if (!p || BUSY) return; const btn = $('#shRec');
  let stopFn = null; btn.classList.add('rec'); btn.textContent = '⏺ 녹음 중… (누르면 끝)'; btn.onclick = () => stopFn && stopFn();
  showResult('#shNote', '따라 말해 보세요: ' + esc(p.text));
  try {
    const { blob, b64 } = await recordOnce({ maxMs: 5000, onStart: s => stopFn = s });
    btn.classList.remove('rec'); btn.textContent = '🎙 따라 말하기'; btn.onclick = record;
    showResult('#shNote', '채점 중… (몇 초 걸려요)');
    const [myWave, r] = await Promise.all([waveFromBlob(blob), speak(b64, p.id, '🎧 채점 중… 잠깐만요')]);
    $('#shWave').style.display = 'block'; drawWave($('#wvT'), teacherWave); drawWave($('#wvM'), myWave); $('#wvMTxt').textContent = r.heard || '';
    $('#shHeard').style.display = 'block'; $('#shHeardS').textContent = r.heard || '(안 들렸어요)';
    if (r.error) { showResult('#shNote', '채점 실패: ' + esc(r.error), 'bad'); return; }
    const ok = r.passed; const el = $('#shResult'); el.style.display = 'block';
    el.innerHTML = `<div class="type ${ok ? 'ok' : ''}">${ok ? '✓ 잘 들렸어요' : '✕ 한 번 더 해볼까요?'}</div><div class="fixed" style="color:${ok ? 'var(--primary)' : 'var(--danger)'}">${r.score}점</div><div class="why">원문: ${esc(r.expected)}<br>들린 말: ${esc(r.heard)}</div><div class="src">🎙 STT 단어 일치율 · 통과 70</div>`;
    if (r.pronunciation_level || r.pronunciation_score != null) { const lv = likeLevel(r); $('#shLike').style.display = 'block'; $('#shLv').innerHTML = [1, 2, 3].map(i => `<span class="${i <= lv ? 'on' : ''}"></span>`).join('') + `<b>${LIKE[lv][0]}</b>`; $('#shLikeMsg').textContent = LIKE[lv][1]; }
    hideResult('#shNote'); localStorage.setItem(`spoken_${state.student}_${state.unit.unit}_${p.id}_${Date.now()}`, '1');
  } catch (e) { btn.classList.remove('rec'); btn.textContent = '🎙 따라 말하기'; btn.onclick = record; showResult('#shNote', esc(e.message), 'bad'); }
}
(async function init() {
  if (!state) return; renderTopbar(); showHealth(); injectChat('shadow');
  pats = S.get().patterns || [];
  if (!pats.length) { const lv = state.level.level, unit = state.unit.unit; pats = (await api(`/api/sentences?level=${lv}&unit=${unit}`).catch(() => [])).map(s => ({ id: s.id, text: s.sentence, meaning: s.meaning })); }
  if (!pats.length) { await loadSampleB(); pats = SB.patterns.filter(p => p.unit === state.unit.unit).map(p => ({ ...p, noAudio: true })); }
  pi = S.get().patIdx || 0; if (pi >= pats.length) pi = 0; render();
})();
