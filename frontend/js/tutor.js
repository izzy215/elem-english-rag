/* 내 문장 말해보기 (핵심) — 🎙 STT(팀원 API) 또는 ⌨ 입력 → /fix (서버 없으면 화면 폴백 진단) → 오답노트 기록 */
const state = requireState('level', 'unit');
let text = '', source = 'typed', typing = false, round = 0, continuing = false;   // round: 같은 문장을 몇 번째 고치는 중인지 (다시 고쳐줘 최대 2회)

// 진단 결과 영역만 초기화 (입력 문장은 그대로). 새 문장을 치면 이전 카드·단계·칩이 이어 붙지 않게
function clearResults() {
  ['#steps', '#diag', '#nav'].forEach(q => $(q).style.display = 'none'); $('#askChips').style.display = 'none'; hideResult('#missionNote');
  round = 0; $$('.diag-prev').forEach(el => el.remove());
}
function reset() {
  text = ''; $('#heard').style.display = 'none'; $('#fixBtn').disabled = true; hideResult('#tNote');
  ['#steps', '#diag', '#nav'].forEach(q => $(q).style.display = 'none'); $('#askChips').style.display = 'none'; $('#typeInput').value = ''; hideResult('#missionNote');
  round = 0; $$('.diag-prev').forEach(el => el.remove());
}
// 다시 고쳐줘: 방금 고친 문장을 새 입력으로 삼아 한 번 더 /fix. 이전 카드는 위에 남겨 둔다
function fixAgain(fixed) {
  const prev = $('#diag').cloneNode(true); prev.id = ''; prev.classList.add('diag-prev'); prev.style.opacity = '.6';
  prev.querySelectorAll('button').forEach(b => b.remove()); prev.insertAdjacentHTML('afterbegin', `<div class="hint" style="margin:0 0 6px">${round}차 고침</div>`);
  $('#diag').before(prev);
  continuing = true; setText(fixed, source); continuing = false; runFix();
}
// 미션 확인 (문법과 별개): 서버 /fix 가 mission 필드를 주면 그것, 아니면 화면 임시로 "힌트 단어가 하나라도 들어갔나"만 본다
function missionHints() {
  const u = state.unit; const h = (u.hint_words && u.hint_words.length) ? u.hint_words : (S.get().words || []).map(w => w.word);
  return h.map(w => w.toLowerCase());
}
function checkMission(text, r) {
  if (r.mission) return r.mission;                                  // 서버 판단 우선 {ok, nudge}
  const hints = missionHints(); if (!hints.length) return null;
  const words = text.toLowerCase().replace(/[^a-z' ]/g, ' ').split(/\s+/);
  const hit = hints.filter(h => words.includes(h) || words.some(w => w.startsWith(h) && w.length - h.length <= 3));   // zoo / lions / eating 정도 허용
  return hit.length ? { ok: true } : { ok: false, nudge: `미션은 "${state.unit.mission}"이에요. ${hints.slice(0, 4).join(' · ')} 같은 단어를 넣어 말해볼까요?`, local: true };
}
function toggleType() { typing = !typing; $('#typeBox').style.display = typing ? 'block' : 'none'; if (typing) $('#typeInput').focus(); }
function onType() { const v = $('#typeInput').value.trim(); if (v) setText(v, 'typed'); }
function setText(t, src) { if (round > 0 && !continuing && t !== text) clearResults(); text = t; source = src; $('#heard').style.display = 'block'; $('#heardLbl').textContent = src === 'stt' ? '들린 문장 (STT)' : '쓴 문장'; $('#heardS').textContent = t; $('#fixBtn').disabled = false; }
async function record() {
  if (BUSY) return;
  const btn = $('#recBtn'); let stopFn = null; btn.classList.add('rec'); btn.textContent = '⏺ 녹음 중… (누르면 끝)'; btn.onclick = () => stopFn && stopFn();
  showResult('#tNote', '미션에 맞춰 영어로 한 문장 말해봐요');
  try {
    const { b64, mime } = await recordOnce({ maxMs: 6000, onStart: s => stopFn = s });
    btn.classList.remove('rec'); btn.textContent = '🎙 말하기'; btn.onclick = record; showResult('#tNote', '듣는 중… (몇 초 걸려요)');
    const r = await speak(b64, '', '🎧 듣는 중… 잠깐만요', mime); // item_id 없이 → heard 만 사용
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
  let r; try { r = await p; console.log(`[fix] ${round + 1}차 응답`, r); }
  catch (e) { $('#st2').className = 'step'; $('#diag').style.display = 'block'; $('#diag').innerHTML = `<div class="type">서버 진단 실패</div><div class="why">${esc(e.message)}</div><div class="src">잠시 후 다시 [고쳐줘]를 눌러 보세요.</div>`; $('#fixBtn').disabled = false; return; }
  $('#st2').className = 'step done'; $('#st3').className = 'step on'; await new Promise(x => setTimeout(x, 350)); $('#st3').className = 'step done';
  round++;
  const d = $('#diag'); d.style.display = 'block';
  const badge = r.mode === 'local' ? `<div class="src" style="opacity:.75">서버 /fix 구현 전 · 화면 임시 진단 (규칙 샘플 기준)</div>`
    : r.mode === 'fallback' ? `<div class="src" style="opacity:.75">서버 /fix · RAG 검색 실패로 규칙 전체를 넣는 폴백 모드${r.fallback_reason ? ' (' + esc(r.fallback_reason) + ')' : ''}</div>` : '';
  if (r.ok) d.innerHTML = `<div class="type ok">${round > 1 ? '✓ 이제 다 맞았어요!' : '✓ 잘 썼어요!'}</div><div class="fixed">${esc(r.fixed)}</div><div class="why">${esc(r.why)}</div>${badge}`;
  else {
    d.innerHTML = `<div class="type">✕ 헷갈린 규칙: ${esc(r.rule.name)}</div><div class="fixed"><s>${esc(r.wrong)}</s><em>${esc(r.fix)}</em> → ${esc(r.fixed)}</div><div class="why">${esc(r.why)}</div><div class="src">📚 <b>${r.mode === 'rag' ? 'RAG가 찾은 근거' : r.mode === 'fallback' ? '참고한 규칙 (검색 없이 전체 규칙 중 고름)' : '참고한 규칙 (화면 샘플)'}</b> · ${esc(r.source?.chunk_id || '')}${r.rule.score != null ? ` · 검색 점수 ${r.rule.score}` : ''}${r.runner_up ? ` · 2위 ${esc(r.runner_up.name)} ${r.runner_up.score}` : ''}<br><span style="opacity:.8;white-space:normal;word-break:keep-all;overflow-wrap:anywhere">${esc(r.source?.text || '')}</span></div>${round < 2 ? `${r.more_errors ? '<div class="result on todo">하나 더 있어요!</div>' : ''}<button class="btn ghost" style="margin-top:8px" onclick='fixAgain(${JSON.stringify(r.fixed)})'>${r.more_errors ? '고친 문장으로 다시 고쳐줘 ✨' : '혹시 더 고칠 곳 있나 한 번 더 봐줘 🔍'}</button>` : (r.more_errors ? `<div class="result on todo">아직 고칠 곳이 남았어요. 다 고치면 이렇게 돼요 👇</div><div class="fixed" style="color:var(--primary)">${esc(r.full_fixed || r.fixed)}</div>` : '')}${badge}`;
    NB.addWrong(state.student, r.rule.id, text, r.fixed, r.log_id);   // 서버 /notebook 이 생기기 전까지 오답노트 화면용 로컬 기록 (서버가 있으면 화면이 서버 것을 씀)
  }
  const m = checkMission(text, r);
  if (m && !m.ok) showResult('#missionNote', `🎯 ${esc(m.nudge)}${m.local ? ' <span style="opacity:.6;font-weight:500">(서버 /fix 미션 판단 전 · 힌트 단어만 확인)</span>' : ''}`, 'todo'); else hideResult('#missionNote');
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
  const why = micSupport(); if (why) { showResult('#tNote', '🎙 ' + esc(why) + ' ⌨ 쓰기는 돼요.', 'todo'); $('#recBtn').disabled = true; }
})();
