/* 표현 익히기 — 단어(탭하면 TTS) · 문장 패턴(서버 /patterns 없으면 sample-B patterns.csv, 그것도 없으면 /sentences) */
const state = requireState('level', 'unit');
let words = [], pats = [], pi = 0;

async function loadData() {
  const lv = state.level.level, unit = state.unit.unit;
  words = await api(`/api/words?level=${lv}&unit=${unit}`).catch(() => []);
  try { pats = await api(`/api/patterns?level=${lv}&unit=${unit}`); }
  catch (_) {
    await loadSampleB(); pats = SB.patterns.filter(p => p.unit === unit).map(p => ({ id: p.id, text: p.text, meaning: p.meaning, tip: p.tip, rule_id: p.rule_id }));
    if (!pats.length) pats = (await api(`/api/sentences?level=${lv}&unit=${unit}`).catch(() => [])).map(s => ({ id: s.id, text: s.sentence, meaning: s.meaning, tip: '' }));
  }
  S.set({ words, patterns: pats });
}
function renderWords() {
  $('#wordCnt').textContent = `${words.length}개`;
  $('#wordRow').innerHTML = words.map(w => `<button class="mini" onclick="playWord('${w.id}', this)"><b>${esc(w.word)}</b>${esc(w.meaning)}</button>`).join('') || '<div class="empty">단어가 없어요</div>';
}
async function playWord(id, btn) {
  $$('.mini').forEach(b => b.classList.remove('on')); btn.classList.add('on');
  try { await playTTS(id, null); } catch (e) { showResult('#learnResult', '듣기 실패: ' + esc(e.message), 'todo'); }
}
function renderPat() {
  const p = pats[pi];
  if (!p) { $('#patCard').innerHTML = '<div class="word">패턴이 없어요</div>'; $('#patPage').textContent = ''; return; }
  $('#patPage').textContent = `${pi + 1} / ${pats.length}`;
  $('#patCard').innerHTML = `<div class="word">${esc(p.text)}</div><div class="mean">${esc(p.meaning)}</div>${p.tip ? `<div class="ex">💡 ${esc(p.tip)}</div>` : ''}`;
  $('#patDots').innerHTML = pats.map((_, i) => `<i class="${i === pi ? 'now' : ''}"></i>`).join('');
  hideResult('#learnResult'); S.set({ patIdx: pi });
}
function movePat(d) { if (!pats.length) return; pi = (pi + d + pats.length) % pats.length; renderPat(); }
async function playPattern() {
  const p = pats[pi]; if (!p) return;
  try { await playTTS(p.id, $('#patTts')); } catch (e) { showResult('#learnResult', /없음|404/.test(e.message) ? '이 패턴은 음원이 아직 없어요 (골든 데이터 납품 후)' : '듣기 실패: ' + esc(e.message), 'todo'); }
}
(async function init() {
  if (!state) return; renderTopbar(); showHealth(); injectChat('learn');
  await loadData(); pi = S.get().patIdx || 0; if (pi >= pats.length) pi = 0; renderWords(); renderPat();
})();
