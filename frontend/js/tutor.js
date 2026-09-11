/* 내 문장 말해보기 (핵심) — 🎙 STT(팀원 API) 또는 ⌨ 입력 → /fix (서버가 404 일 때만 화면 임시 진단) → 오답노트 기록 */
const state = requireState('level', 'unit');
let text = '', source = 'typed', typing = false, round = 0, continuing = false;   // round: 같은 문장을 몇 번째 고치는 중인지 (최대 2차 = 다시 고쳐줘 버튼 1회)

// 진단 결과 영역만 초기화 (입력 문장은 그대로). 새 문장을 치면 이전 카드·단계·칩이 이어 붙지 않게
function clearResults() {
  ['#steps', '#diag', '#nav'].forEach(q => $(q).style.display = 'none'); $('#askChips').style.display = 'none'; hideResult('#missionNote');
  round = 0; rounds = []; $$('.diag-prev').forEach(el => el.remove());
}
function reset() {
  text = ''; $('#heard').style.display = 'none'; $('#fixBtn').disabled = true; hideResult('#tNote');
  ['#steps', '#diag', '#nav'].forEach(q => $(q).style.display = 'none'); $('#askChips').style.display = 'none'; $('#typeInput').value = ''; hideResult('#missionNote');
  round = 0; rounds = []; $$('.diag-prev').forEach(el => el.remove());
}
// 다시 고쳐줘: 방금 고친 문장을 새 입력으로 삼아 한 번 더 /fix. 이전 카드는 위에 남겨 둔다
function fixAgain(fixed) {
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
let rounds = [];   // 이 문장의 회차별 /fix 결과 [1차, 2차]. 발표용 토글 때 전부 다시 그리려고 보관
// 진단 카드. 근거 박스는 두 겹 — 학생용(기본): 규칙 한 줄 / 발표·개발용(상단 학생 칩 길게 누르기·더블클릭): id·점수·순위·2위·후보 5·원문·모델·시간·모드
function evidenceBox(r) {
  if (!DEV.on()) {   // 학생용: 서버가 준 규칙 이름 + 근거 조각 첫 문장만 (화면 샘플 규칙표는 안 본다 — id 체계가 달라 다른 규칙이 찍힌다)
    const first = (r.source?.text || '').split(/(?<=[.!?])\s+/)[0];
    return `<div class="src">📚 <b>${esc(r.rule.name)}</b>${first ? ` · ${esc(first)}` : ''}</div>`;
  }
  // 발표용: "검색(RAG)이 고른 것" 과 "LLM 이 고른 것" 을 구분 — 검색 후보 5 + 유닛·공통 규칙(extra_rules) 을 순서대로 보여 주고 LLM 이 고른 규칙에 ✓ 강조
  const chosen = r.rule?.id, cands = r.candidates || [], extras = r.extra_rules || [];
  const mark = (name, id) => id === chosen ? `<b style="color:var(--primary)">✓${esc(name)}</b>` : esc(name);
  const candLine = cands.map((c, i) => `${i + 1}위 ${mark(c.name, c.id)} ${c.score}`).join(' · ');
  const from = x => x.from === 'unit' ? '유닛' : '공통';
  const extraLine = extras.map(x => `${mark(x.name, x.id)}(${from(x)}${x.rank ? `, 검색 ${x.rank}위` : ''})`).join(' · ');
  const inTop = cands.some(c => c.id === chosen), extra = extras.find(x => x.id === chosen);
  const name = esc(r.rule?.name || r.rule?.id || ''), nTop = cands.length || 5;
  const pick = r.rule?.rank == null ? `검색 없이 규칙 전부를 보고 LLM이 ${name} 규칙을 골랐어요`   // rank 없음 = 검색 실패·폴백·화면 임시 진단
    : inTop ? `RAG 후보 ${nTop}개 중 LLM이 ${r.rule.rank}위 ${name} 규칙을 골라 설명했어요`
    : `RAG 후보 ${nTop}개 밖의 ${extra ? from(extra) : '다른'} 규칙 ${name}(검색 ${r.rule.rank}위)를 LLM이 골랐어요`;
  const top1 = r.runner_up && r.rule?.rank !== 1 ? `RAG ${r.runner_up.rank || 1}위는 ${esc(r.runner_up.name)}(${r.runner_up.score})` : '';   // 고른 게 1위면 생략 (그때 runner_up 은 2위)
  const sec = ms => `${(ms / 1000).toFixed(1)}초`;
  const embLine = r.embedding ? `검색 모델: ${esc(r.embedding.provider || '')} · ${esc(r.embedding.model || '')}` : '';   // 서버가 embedding 을 안 주면 생략
  const t = r.timing;
  const llmLine = r.llm ? `답변 모델: ${esc(r.llm.backend)} · ${esc(r.llm.model || '')} · ${sec(t ? t.total_ms : r.llm.ms)}${t ? ` (검색 ${sec(t.search_ms)} · 모델 호출 ${t.llm_calls}회)` : ''}${r.llm.fallback_from ? ` · ${esc(r.llm.fallback_from)} 실패 → 대체` : ''}` : '';
  return `<div class="src">📚 <b>근거</b> — ${pick} · ${esc(r.source?.chunk_id || '')}${r.rule.score != null ? ` · 검색 점수 ${r.rule.score}` : ''}${top1 ? ` · ${top1}` : ''}
    <br><span style="opacity:.8;white-space:normal;word-break:keep-all;overflow-wrap:anywhere">${esc(r.source?.text || '')}</span>
    ${candLine ? `<br><span style="opacity:.7">검색 후보 ${cands.length}: ${candLine}</span>` : ''}${extraLine ? `<br><span style="opacity:.7">유닛·공통 규칙: ${extraLine}</span>` : ''}${embLine ? `<br><span style="opacity:.7">${embLine}</span>` : ''}${llmLine ? `<br><span style="opacity:.7">${llmLine}</span>` : ''}</div>`;
}
function diagHTML(r, n, isLast) {
  const badge = !DEV.on() ? '' : r.mode === 'local' ? `<div class="src" style="opacity:.75">서버 /fix 없음(404) · 화면 임시 진단 (규칙 샘플 기준)</div>`
    : r.mode === 'fallback' ? `<div class="src" style="opacity:.75">서버 /fix · RAG 검색 실패로 규칙 전체를 넣는 폴백 모드${r.fallback_reason ? ' (' + esc(r.fallback_reason) + ')' : ''}</div>` : '';
  const spell = (r.spelling || []).length ? `<div class="hint" style="margin-top:10px">✏️ 철자만 살짝 고치면</div><div class="fixed">${spellHTML(r.fixed, r.spelling)}</div>` : '';
  if (r.ok) return `<div class="type ok">${n > 1 ? '✓ 이제 다 맞았어요!' : '✓ 잘 썼어요!'}</div><div class="fixed">${esc(r.fixed)}</div><div class="why">${esc(r.why)}</div>${spell}${badge}`;
  if (r.rule?.id === 'OTHER') return `<div class="type">✎ 우리 규칙 밖이에요</div><div class="fixed">${esc(r.fixed)}</div><div class="why">${esc(r.why)}</div><div class="hint" style="margin-top:6px">교과서 규칙에는 없는 부분이라 오답노트에는 안 들어가요. 하려던 말이 다르면 문장을 다시 써 주세요.</div>${badge}`;
  const tail = !isLast ? '' : n < 2
    ? `${r.more_errors ? '<div class="result on todo">하나 더 있어요!</div>' : ''}<button type="button" class="btn ghost" style="margin-top:8px" data-fixed="${esc(r.fixed)}">${r.more_errors ? '고친 문장으로 다시 고쳐줘 ✨' : '혹시 더 고칠 곳 있나 한 번 더 봐줘 🔍'}</button>`
    : (r.more_errors ? `<div class="result on todo">아직 고칠 곳이 남았어요. 다 고치면 이렇게 돼요 👇</div><div class="fixed" style="color:var(--primary)">${esc(r.full_fixed || r.fixed)}</div>` : '');
  const spell2 = (r.spelling || []).length ? `<div class="hint" style="margin-top:4px">✏️ 철자도 살짝: ${r.spelling.map(s => `<s>${esc(s.wrong)}</s> → <b>${esc(s.fix)}</b>`).join(', ')}</div>` : '';
  return `<div class="type">✕ 헷갈린 규칙: ${esc(r.rule.name)}</div><div class="fixed"><s>${esc(r.wrong)}</s><em>${esc(r.fix)}</em> → ${esc(r.fixed)}</div>${spell2}<div class="why">${esc(r.why)}</div>${evidenceBox(r)}${tail}${badge}`;
}
function spellHTML(text, pairs) {   // 원문에서 틀린 단어를 <s>틀림</s><em>맞음</em> 으로 (틀린 규칙 카드의 wrong→fix 표기와 같은 모양)
  let html = esc(text);
  for (const p of pairs) html = html.replace(new RegExp('(^|[^A-Za-z])(' + escapeRe(p.wrong) + ')(?![A-Za-z])', 'i'), (m, pre, w) => pre + '<s>' + esc(w) + '</s><em>' + esc(p.fix) + '</em>');
  return html;
}
function renderAll() {   // 이전 회차는 흐린 카드(버튼 없음)로 위에, 마지막 회차는 #diag 에
  $$('.diag-prev').forEach(el => el.remove());
  const d = $('#diag'); if (!rounds.length) { d.style.display = 'none'; return; }
  rounds.slice(0, -1).forEach((r, i) => d.insertAdjacentHTML('beforebegin', `<div class="diag diag-prev" style="opacity:.6"><div class="hint" style="margin:0 0 6px">${i + 1}차 고침</div>${diagHTML(r, i + 1, false)}</div>`));
  d.style.display = 'block'; d.innerHTML = diagHTML(rounds[rounds.length - 1], rounds.length, true);
  $$('#diag button[data-fixed]').forEach(b => b.addEventListener('click', () => fixAgain(b.dataset.fixed)));   // 문장을 onclick 속성에 넣지 않는다 (따옴표가 들어가면 속성이 깨짐)
}
window.addEventListener('devview', () => { if (rounds.length) renderAll(); });
async function runFix() {
  if (!text || BUSY) return; $('#fixBtn').disabled = true; $('#steps').style.display = 'grid'; $('#diag').style.display = 'none';
  const st = ['#st1', '#st2', '#st3']; st.forEach(s => $(s).className = 'step'); $('#st1').className = 'step on';
  const t0 = performance.now();
  setBusy(true, '✨ 고치는 중… 잠깐만요');                       // 상단 진행바 + 하단 메시지, 다른 버튼 잠금 (speak 와 같은 방식)
  const tick = setInterval(() => { const s = Math.round((performance.now() - t0) / 1000); if (s >= 3) $('#loadmsg').textContent = `✨ 고치는 중… ${s}초`; }, 1000);
  const p = fixSentence(text, { level: state.level.level, unit: state.unit.unit, source });
  await new Promise(r => setTimeout(r, 350)); $('#st1').className = 'step done'; $('#st2').className = 'step on';
  let r; try { r = await p; if (DEV.on()) console.log(`[fix] ${round + 1}차 응답 ${Math.round(performance.now() - t0)}ms`, r); }
  catch (e) { clearInterval(tick); setBusy(false); $('#st2').className = 'step'; $('#diag').style.display = 'block'; $('#diag').innerHTML = `<div class="type">서버 진단 실패</div><div class="why">${esc(e.message)}</div><div class="src">잠시 후 다시 [고쳐줘]를 눌러 보세요.</div>`; $('#fixBtn').disabled = false; return; }
  clearInterval(tick); setBusy(false);
  $('#st2').className = 'step done'; $('#st3').className = 'step on'; await new Promise(x => setTimeout(x, 350)); $('#st3').className = 'step done';
  $('#st3').title = `${Math.round(performance.now() - t0)}ms`;
  round++;
  const d = $('#diag'); d.style.display = 'block';
  rounds.push(r); renderAll();
  if (!r.ok) {
    NB.addWrong(state.student, r.rule.id, text, r.fixed, r.log_id);   // 브라우저 사본 (정식 기록은 서버 notebook.json — 화면은 서버 것을 먼저 쓴다)
  }
  const m = checkMission(text, r);
  if (m && !m.ok) showResult('#missionNote', `🎯 ${esc(m.nudge)}${m.local ? ' <span style="opacity:.6;font-weight:500">(서버 없이 힌트 단어만 확인한 결과)</span>' : ''}`, 'todo'); else hideResult('#missionNote');
  localStorage.setItem(`spoken_${state.student}_${state.unit.unit}_${Date.now()}`, '1'); S.set({ lastFix: { log_id: r.log_id, rule_id: r.rule?.id || null } });
  const chips = $('#askChips'); chips.style.display = 'flex';
  const sugg = (r.suggested_questions || []).filter(q => typeof q === 'string' && q);
  const chatCtx = { rule_id: r.rule?.id || null, rule_name: r.rule?.name || '', log_id: r.log_id, suggested: sugg };   // 전부 서버 /fix 응답 값
  chips.innerHTML = `<span class="hint" style="width:100%;margin:0">더 물어보기</span>` + sugg.map(q => `<button type="button" class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join('') + `<button type="button" class="chip" data-q="">🙋 직접 물어보기</button>`;
  $$('#askChips button[data-q]').forEach(b => b.addEventListener('click', () => openChat(chatCtx).then(() => { if (b.dataset.q) askChat(b.dataset.q); })));   // 질문 문구는 data 속성 + 이벤트로 (renderSugg 와 같은 방식)
  $('#nav').style.display = 'grid';
}
(async function init() {
  if (!state) return; renderTopbar(); showHealth(); injectChat('tutor');
  const u = state.unit; $('#mission').textContent = u.mission || `${u.title} 단어로 한 문장 말해봐요`;
  const hint = (u.hint_words && u.hint_words.length) ? u.hint_words : (S.get().words || []).slice(0, 4).map(w => w.word);
  $('#hintWords').textContent = hint.length ? '힌트: ' + hint.join(' · ') : ''; reset();
  const why = micSupport(); if (why) { showResult('#tNote', '🎙 ' + esc(why) + ' ⌨ 쓰기는 돼요.', 'todo'); $('#recBtn').disabled = true; }
})();
