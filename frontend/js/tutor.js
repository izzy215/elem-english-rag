/* 내 문장 말해보기 (핵심) — 🎙 STT(팀원 API) 또는 ⌨ 입력 → /fix (서버 없으면 화면 폴백 진단) → 오답노트 기록 */
const state = requireState('level', 'unit');
let text = '', source = 'typed', typing = false;

function reset() {
  text = ''; $('#heard').style.display = 'none'; $('#fixBtn').disabled = true; hideResult('#tNote');
  ['#steps', '#diag', '#nav'].forEach(q => $(q).style.display = 'none'); $('#askChips').style.display = 'none'; $('#typeInput').value = '';
}
function toggleType() { typing = !typing; $('#typeBox').style.display = typing ? 'block' : 'none'; if (typing) $('#typeInput').focus(); }
function onType() { const v = $('#typeInput').value.trim(); if (v) setText(v, 'typed'); }
function setText(t, src) { text = t; source = src; $('#heard').style.display = 'block'; $('#heardLbl').textContent = src === 'stt' ? '들린 문장 (STT)' : '쓴 문장'; $('#heardS').textContent = t; $('#fixBtn').disabled = false; }
async function record() {
  if (BUSY) return;
  const btn = $('#recBtn'); let stopFn = null; btn.classList.add('rec'); btn.textContent = '⏺ 녹음 중… (누르면 끝)'; btn.onclick = () => stopFn && stopFn();
  showResult('#tNote', '미션에 맞춰 영어로 한 문장 말해봐요');
  try {
    const { b64 } = await recordOnce({ maxMs: 6000, onStart: s => stopFn = s });
    btn.classList.remove('rec'); btn.textContent = '🎙 말하기'; btn.onclick = record; showResult('#tNote', '듣는 중… (몇 초 걸려요)');
    const r = await speak(b64, '', '🎧 듣는 중… 잠깐만요'); // item_id 없이 → heard 만 사용
    if (r.error) { showResult('#tNote', '잘 안 들렸어요: ' + esc(r.error), 'bad'); return; }
    if (!r.heard) { showResult('#tNote', '잘 안 들렸어요. 한 번 더 말해볼까요?', 'bad'); return; }
    hideResult('#tNote'); setText(r.heard.replace(/\s+$/, '') + (/[.!?]$/.test(r.heard) ? '' : '.'), 'stt');
  } catch (e) { btn.classList.remove('rec'); btn.textContent = '🎙 말하기'; btn.onclick = record; showResult('#tNote', esc(e.message), 'bad'); }
}
async function runFix() {
  if (!text) return; $('#fixBtn').disabled = true; $('#steps').style.display = 'grid'; $('#diag').style.display = 'none';
  const st = ['#st1', '#st2', '#st3']; st.forEach(s => $(s).className = 'step'); $('#st1').className = 'step on';
  const p = fixSentence(text, { level: state.level.level, unit: state.unit.unit, source });
  await new Promise(r => setTimeout(r, 350)); $('#st1').className = 'step done'; $('#st2').className = 'step on';
  const r = await p;
  $('#st2').className = 'step done'; $('#st3').className = 'step on'; await new Promise(x => setTimeout(x, 350)); $('#st3').className = 'step done';
  const d = $('#diag'); d.style.display = 'block';
  const badge = r.mode === 'fallback' ? `<div class="src" style="opacity:.75">서버 /fix 구현 전 · 화면 임시 진단 (규칙 샘플 기준)</div>` : '';
  if (r.ok) d.innerHTML = `<div class="type ok">✓ 잘 썼어요!</div><div class="fixed">${esc(r.fixed)}</div><div class="why">${esc(r.why)}</div>${badge}`;
  else {
    d.innerHTML = `<div class="type">✕ 헷갈린 규칙: ${esc(r.rule.name)}</div><div class="fixed"><s>${esc(r.wrong)}</s><em>${esc(r.fix)}</em> → ${esc(r.fixed)}</div><div class="why">${esc(r.why)}</div><div class="src">📚 <b>RAG가 찾은 근거</b> · ${esc(r.source?.chunk_id || '')}${r.rule.score ? ` · 검색 점수 ${r.rule.score}` : ''}${r.runner_up ? ` · 2위 ${esc(r.runner_up.name)} ${r.runner_up.score}` : ''}<br><span style="opacity:.8">${esc((r.source?.text || '').slice(0, 120))}</span></div>${r.more_errors ? '<div class="result on todo">하나 더 있어요 — 고친 문장으로 다시 고쳐줘 눌러봐요</div>' : ''}${badge}`;
    if (r.mode === 'fallback') NB.addWrong(state.student, r.rule.id, text, r.fixed, r.log_id);
  }
  localStorage.setItem(`spoken_${state.student}_${state.unit.unit}_${Date.now()}`, '1'); S.set({ lastFix: { log_id: r.log_id, rule_id: r.rule?.id || null } });
  const chips = $('#askChips'); chips.style.display = 'flex';
  chips.innerHTML = `<span class="hint" style="width:100%;margin:0">더 물어보기</span>` + (r.suggested_questions || []).map(q => `<button class="chip" onclick='openChat({rule_id:${JSON.stringify(r.rule?.id || null)},log_id:${JSON.stringify(r.log_id)}}).then(()=>askChat(${JSON.stringify(q)}))'>${esc(q)}</button>`).join('') + `<button class="chip" onclick='openChat({rule_id:${JSON.stringify(r.rule?.id || null)},log_id:${JSON.stringify(r.log_id)}})'>🙋 직접 물어보기</button>`;
  $('#nav').style.display = 'grid';
}
(async function init() {
  if (!state) return; renderTopbar(); showHealth(); injectChat('tutor'); await loadSampleB();
  const u = state.unit; $('#mission').textContent = u.mission || `${u.title} 단어로 한 문장 말해봐요`;
  const hint = (u.hint_words && u.hint_words.length) ? u.hint_words : (S.get().words || []).slice(0, 4).map(w => w.word);
  $('#hintWords').textContent = hint.length ? '힌트: ' + hint.join(' · ') : ''; reset();
})();
