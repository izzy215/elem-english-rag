/* 내 문장 말해보기 (핵심) — 🎙 STT(팀원 API) 또는 ⌨ 입력 → /fix (서버가 404 일 때만 화면 임시 진단) → 오답노트 기록
 * 결과 카드는 아이용(목업 9/14): 규칙 칩 + 한 줄 구호 → 고친 문장 크게 → 타일(📖 교과서 문장 · 🙋 친구들 실수 · ✏️ 새 단어) → 접힌 "왜 그래요?"(규칙 문서) · "어떻게 찾았어요?"(근거)
 * 타일 자료: 서버 /fix 가 textbook·peer_example·outside_words 를 주면 그걸 쓰고, 아직 없으면 화면이 /api/admin/textbook(교과서 검색)·/api/drill(같은 규칙의 틀린 예문 1개)로 채운다. */
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
function hintHit(text) {   // 힌트 단어가 문장에 들어 있나 (zoo / lions / eating 정도 허용)
  const hints = missionHints(); if (!hints.length) return false;
  const words = text.toLowerCase().replace(/[^a-z' ]/g, ' ').split(/\s+/);
  return hints.some(h => words.includes(h) || words.some(w => w.startsWith(h) && w.length - h.length <= 3));
}
function checkMission(text, r) {
  // 서버(모델) 판단이 우선이지만, 힌트 단어를 넣어 말했으면 미션으로 친다 (9/15 팀장: 힌트 넣었는데 안 올라가면 안 됨). 모델은 "좋아하는 색깔" 같은 뜻까지 따져서 더 깐깐하다
  if (r.mission) return (!r.mission.ok && hintHit(text)) ? { ok: true, hint: true } : r.mission;
  const hints = missionHints(); if (!hints.length) return null;
  return hintHit(text) ? { ok: true } : { ok: false, nudge: `미션은 "${state.unit.mission}"이에요. ${hints.slice(0, 4).join(' · ')} 같은 단어를 넣어 말해볼까요?`, local: true };
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

// ── 근거 (접힌 "어떻게 찾았어요?" 안) — 학생용: 규칙 이름 + 근거 첫 문장 / 발표용(DEV): 검색 후보·순위·모델·시간 ──
function evidenceBox(r) {
  if (!DEV.on()) {
    const first = (r.source?.text || '').split(/(?<=[.!?])\s+/)[0];
    return `<div class="src">📚 <b>${esc(r.rule.name)}</b>${first ? ` · ${esc(first)}` : ''}<br><span style="opacity:.75">검색이 찾은 규칙 후보 중에서 골랐어요. 설명과 예문은 교과서 규칙 문서 그대로예요.</span></div>`;
  }
  const chosen = r.rule?.id, cands = r.candidates || [], extras = r.extra_rules || [];
  const mark = (name, id) => id === chosen ? `<b style="color:var(--primary)">✓${esc(name)}</b>` : esc(name);
  const candLine = cands.map((c, i) => `${i + 1}위 ${mark(c.name, c.id)} ${c.score}`).join(' · ');
  const from = x => x.from === 'unit' ? '유닛' : x.from === 'textbook' ? '교과서 문장' : '공통';
  const extraLine = extras.map(x => `${mark(x.name, x.id)}(${from(x)}${x.rank ? `, 검색 ${x.rank}위` : ''})`).join(' · ');
  const inTop = cands.some(c => c.id === chosen), extra = extras.find(x => x.id === chosen);
  const name = esc(r.rule?.name || r.rule?.id || ''), nTop = cands.length || 5;
  const pick = r.rule?.rank == null ? `검색 없이 규칙 전부를 보고 LLM이 ${name} 규칙을 골랐어요`
    : inTop ? `RAG 후보 ${nTop}개 중 LLM이 ${r.rule.rank}위 ${name} 규칙을 골라 설명했어요`
    : `RAG 후보 ${nTop}개 밖의 ${extra ? from(extra) : '다른'} 규칙 ${name}(검색 ${r.rule.rank}위)를 LLM이 골랐어요`;
  const top1 = r.runner_up && r.rule?.rank !== 1 ? `RAG ${r.runner_up.rank || 1}위는 ${esc(r.runner_up.name)}(${r.runner_up.score})` : '';
  const sec = ms => `${(ms / 1000).toFixed(1)}초`;
  const embLine = r.embedding ? `검색 모델: ${esc(r.embedding.provider || '')} · ${esc(r.embedding.model || '')}` : '';
  const t = r.timing;
  const llmLine = r.llm ? `답변 모델: ${esc(r.llm.backend)} · ${esc(r.llm.model || '')} · ${sec(t ? t.total_ms : r.llm.ms)}${t ? ` (검색 ${sec(t.search_ms)} · 모델 호출 ${t.llm_calls}회)` : ''}${r.llm.fallback_from ? ` · ${esc(r.llm.fallback_from)} 실패 → 대체` : ''}` : '';
  const tb = r._tb ? `교과서 검색: 패턴 ${r._tb.patterns.length} · 단어 ${r._tb.words.length} · ${r._tb.query_ms}ms${r._tb.patterns[0] ? ` · 1위 ${esc(r._tb.patterns[0].text)} (${r._tb.patterns[0].score})` : ''}` : '';
  const gr = r.grounded != null ? `설명 출처: ${r.grounded ? '규칙 문서(rules.jsonl)' : '모델 문장'}` : '';
  return `<div class="src">📚 <b>근거</b> — ${pick} · ${esc(r.source?.chunk_id || '')}${r.rule.score != null ? ` · 검색 점수 ${r.rule.score}` : ''}${top1 ? ` · ${top1}` : ''}
    <br><span style="opacity:.8;white-space:normal;word-break:keep-all;overflow-wrap:anywhere">${esc(r.source?.text || '')}</span>
    ${candLine ? `<br><span style="opacity:.7">검색 후보 ${cands.length}: ${candLine}</span>` : ''}${extraLine ? `<br><span style="opacity:.7">유닛·공통 규칙: ${extraLine}</span>` : ''}${tb ? `<br><span style="opacity:.7">${tb}</span>` : ''}${gr ? `<br><span style="opacity:.7">${gr}</span>` : ''}${embLine ? `<br><span style="opacity:.7">${embLine}</span>` : ''}${llmLine ? `<br><span style="opacity:.7">${llmLine}</span>` : ''}
    ${r.model_why ? `<br><span style="opacity:.7">모델이 쓴 설명(화면엔 안 씀): ${esc(r.model_why)}</span>` : ''}</div>`;
}
// "왜 그래요?" 안: 설명은 검색된 규칙 문서(rules.jsonl 의 text·examples). 옛 서버(explanation 없음)면 모델 설명
function whyHTML(r) {
  const ex = r.explanation;
  if (!ex || ex.source !== 'rule' || !ex.text) return `<div class="why">${esc(r.why)}</div>`;
  const exs = (ex.examples || []).map(e => `<b>${esc(e)}</b>`).join(' · ');
  return `<div class="why doc"><span class="doc-tag">📖 교과서 규칙 · ${esc(ex.short || r.rule?.name || '')}</span>${esc(ex.text)}${exs ? `<div class="doc-ex">예: ${exs}</div>` : ''}</div>`;
}
// 타일 3개 — 서버 값 우선(textbook · peer_example · outside_words), 없으면 화면이 채운 값(_tb · _peer)
function tilesHTML(r) {
  const pat = r.textbook?.patterns?.[0] || r._tb?.patterns?.[0] || null;
  const peer = r.peer_example || r._peer || null;
  const outside = (r.outside_words || []).filter(Boolean);
  const unitOf = u => u ? esc(String(u).replace(/^Unit0?/, 'Unit ')) : '교과서';
  const peerSent = peer ? (peer.target ? (() => { const s = String(peer.text || peer.sentence || ''); const m = new RegExp('(^|[^A-Za-z])(' + escapeRe(peer.target) + ')(?![A-Za-z])').exec(s); return m ? esc(s.slice(0, m.index + m[1].length)) + '<u>' + esc(m[2]) + '</u>' + esc(s.slice(m.index + m[0].length)) : esc(s); })() : esc(peer.text || peer.sentence || '')) : '';
  const t = [];
  if (pat) t.push(`<div class="tile book"><div class="ti">📖</div><div><div class="tl">교과서 문장</div><div class="tv">${esc(pat.text)}</div><div class="ts">${unitOf(pat.unit)}에서 배운 말${r.textbook?.used_pattern ? ' · 이 표현으로 고쳤어요' : ''}</div></div></div>`);
  if (peer) t.push(`<div class="tile peer"><div class="ti">🙋</div><div><div class="tl">친구들도 이렇게 실수해요</div><div class="tv">${peerSent}</div><div class="ts">밑줄 친 곳을 어떻게 고칠까요?</div><div class="go"><button type="button" data-drill="${esc(r.rule.id)}">이 문제 풀어보기 ▸</button></div></div></div>`);
  if (outside.length) t.push(`<div class="tile new"><div class="ti">✏️</div><div><div class="tl">새 단어</div><div class="tv">${outside.map(esc).join(', ')}</div><div class="ts">아직 안 배운 말이에요. 써도 괜찮아요</div></div></div>`);
  return t.length ? `<div class="tiles">${t.join('')}</div>` : '';
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
  const kid = r.explanation?.short && r.explanation.short !== r.rule.name ? `<span class="kid">${esc(r.explanation.short)}</span>` : '';   // 한 줄 구호 (rules.jsonl short)
  return `<div class="type">✕ ${esc(r.rule.name)}</div>${kid}<div class="fixed"><s>${esc(r.wrong)}</s><em>${esc(r.fix)}</em> → ${esc(r.fixed)}</div>${spell2}${tilesHTML(r)}
    <details${DEV.on() ? ' open' : ''}><summary>왜 그래요? 📖 교과서 규칙 보기</summary>${whyHTML(r)}</details>
    <details${DEV.on() ? ' open' : ''}><summary>🔍 어떻게 찾았어요? (근거)</summary>${evidenceBox(r)}</details>${tail}${badge}`;
}
function spellHTML(text, pairs) {   // 원문에서 틀린 단어를 <s>틀림</s><em>맞음</em> 으로
  let html = esc(text);
  for (const p of pairs) html = html.replace(new RegExp('(^|[^A-Za-z])(' + escapeRe(p.wrong) + ')(?![A-Za-z])', 'i'), (m, pre, w) => pre + '<s>' + esc(w) + '</s><em>' + esc(p.fix) + '</em>');
  return html;
}
function renderAll() {   // 이전 회차는 흐린 카드(버튼 없음)로 위에, 마지막 회차는 #diag 에
  $$('.diag-prev').forEach(el => el.remove());
  const d = $('#diag'); if (!rounds.length) { d.style.display = 'none'; return; }
  rounds.slice(0, -1).forEach((r, i) => d.insertAdjacentHTML('beforebegin', `<div class="diag diag-prev" style="opacity:.6"><div class="hint" style="margin:0 0 6px">${i + 1}차 고침</div>${diagHTML(r, i + 1, false)}</div>`));
  d.style.display = 'block'; d.innerHTML = diagHTML(rounds[rounds.length - 1], rounds.length, true);
  $$('#diag button[data-fixed]').forEach(b => b.addEventListener('click', () => fixAgain(b.dataset.fixed)));   // 문장을 onclick 속성에 넣지 않는다
  $$('.diag button[data-drill]').forEach(b => b.addEventListener('click', () => { S.set({ nbOpen: b.dataset.drill }); go('notebook.html'); }));   // 🙋 타일 → 오답노트가 그 규칙 카드를 펼친 채로 열림
}
window.addEventListener('devview', () => { if (rounds.length) renderAll(); });
// 🙋 를 고쳐줘 전에 눌러도 챗이 지금 입력한 문장을 알게 (context.text). 고쳐줘 뒤에는 더 물어보기 칩이 rule_id·log_id 를 넘긴다
window.chatExtra = () => (text ? { text, source } : {});
// 타일 자료 보충 (서버 /fix 가 아직 안 주는 것만): 교과서 검색(관리자 API 재사용) · 같은 규칙의 틀린 예문 1개(/drill). 실패해도 카드는 그린다
async function enrich(r) {
  if (r.ok || !r.rule || r.rule.id === 'OTHER') return r;
  const jobs = [];
  if (!r.textbook) jobs.push(api(`/api/admin/textbook?q=${encodeURIComponent(text)}&level=${state.level.level}&k=3`).then(x => { if (x.result && !x.result.error) r._tb = x.result; }).catch(() => {}));
  if (!r.peer_example) jobs.push(api(`/api/drill?student=${encodeURIComponent(S.get().student || 'A')}&rule=${encodeURIComponent(r.rule.id)}&count=1`).then(x => { const q = (x.questions || [])[0]; if (q) r._peer = { text: q.sentence, target: q.target, error_id: q.error_id }; }).catch(() => {}));
  await Promise.all(jobs); return r;
}
async function runFix() {
  if (!text || BUSY) return; $('#fixBtn').disabled = true; $('#steps').style.display = 'grid'; $('#diag').style.display = 'none';
  const st = ['#st1', '#st2', '#st3']; st.forEach(s => $(s).className = 'step'); $('#st1').className = 'step on';
  const t0 = performance.now();
  setBusy(true, '✨ 고치는 중… 잠깐만요');
  const tick = setInterval(() => { const s = Math.round((performance.now() - t0) / 1000); if (s >= 3) $('#loadmsg').textContent = `✨ 고치는 중… ${s}초`; }, 1000);
  const p = fixSentence(text, { level: state.level.level, unit: state.unit.unit, source });
  await new Promise(r => setTimeout(r, 350)); $('#st1').className = 'step done'; $('#st2').className = 'step on';
  let r; try { r = await p; if (DEV.on()) console.log(`[fix] ${round + 1}차 응답 ${Math.round(performance.now() - t0)}ms`, r); }
  catch (e) { clearInterval(tick); setBusy(false); $('#st2').className = 'step'; $('#diag').style.display = 'block'; $('#diag').innerHTML = `<div class="type">서버 진단 실패</div><div class="why">${esc(e.message)}</div><div class="src">잠시 후 다시 [고쳐줘]를 눌러 보세요.</div>`; $('#fixBtn').disabled = false; return; }
  $('#st2').className = 'step done'; $('#st3').className = 'step on';
  await enrich(r);
  clearInterval(tick); setBusy(false);
  await new Promise(x => setTimeout(x, 250)); $('#st3').className = 'step done';
  $('#st3').title = `${Math.round(performance.now() - t0)}ms`;
  round++;
  rounds.push(r); renderAll();
  if (!r.ok && r.rule && r.rule.id !== 'OTHER') NB.addWrong(state.student, r.rule.id, text, r.fixed, r.log_id);   // 브라우저 사본 (정식 기록은 서버 notebook.json)
  const m = checkMission(text, r);
  // 유닛 흐름 (9/15): 미션에 맞는 문장을 FLOW.need(3)개 모으면 미션 성공. 문법이 틀렸어도 고친 문장이 미션에 맞으면 센다 (고쳐서 ✓)
  const missionOk = !!(m && m.ok);
  if (missionOk && round === 1) FLOW.addSentence(state.unit.unit, { text, fixed: r.fixed, ok: !!r.ok, rule_id: (!r.ok && r.rule && r.rule.id !== 'OTHER') ? r.rule.id : null });
  const flow = FLOW.get(state.unit.unit), left = Math.max(0, FLOW.need - flow.sentences.length);
  renderMissionCnt();
  if (m && !m.ok) showResult('#missionNote', `🎯 ${esc(m.nudge)}${m.local ? ' <span style="opacity:.6;font-weight:500">(서버 없이 힌트 단어만 확인한 결과)</span>' : ''}`, 'todo');
  else if (missionOk && left > 0) showResult('#missionNote', `🎯 미션에 맞는 문장이에요! ${left}문장만 더 하면 미션 성공`);
  else if (missionOk) showResult('#missionNote', '🎉 미션 문장을 다 모았어요! 아래 버튼으로 결과를 봐요');
  else hideResult('#missionNote');
  // 마무리 버튼: 미션 완료면 "미션 성공 보기", 아니면 "한 문장 더" (틀린 문장이면 오답노트 버튼을 살린다)
  const more = $('#moreBtn');
  if (flow.done) { more.textContent = '미션 성공! 결과 보기 🎉'; more.onclick = () => go('success.html'); more.classList.add('glow'); }
  else { more.innerHTML = `한 문장 더 말하기<span class="sub">${missionOk ? `미션 문장 ${flow.sentences.length} / ${FLOW.need}` : `이 문장은 미션과 달라서 안 셌어요 · 힌트: ${missionHints().slice(0, 3).join(', ')}`}</span>`; more.onclick = reset; more.classList.toggle('glow', !flow.done); }
  const showNb = !!(!r.ok && r.rule && r.rule.id !== 'OTHER'); $('#nbBtn').style.display = showNb ? '' : 'none'; $('#nbBtn').parentElement.style.gridTemplateColumns = showNb ? '' : '1fr';   // 맞는 문장이면 오답노트 버튼 없이 한 칸으로
  localStorage.setItem(`spoken_${state.student}_${state.unit.unit}_${Date.now()}`, '1'); S.set({ lastFix: { log_id: r.log_id, rule_id: r.rule?.id || null } });
  const chips = $('#askChips'); chips.style.display = 'flex';
  const sugg = (r.suggested_questions || []).filter(q => typeof q === 'string' && q);
  const chatCtx = { rule_id: r.rule?.id || null, rule_name: r.rule?.name || '', log_id: r.log_id, suggested: sugg };   // 전부 서버 /fix 응답 값
  chips.innerHTML = `<span class="hint" style="width:100%;margin:0">더 물어보기 <span style="font-weight:500">· 누르면 🙋 물어보기 챗이 열려요</span></span>` + sugg.map(q => `<button type="button" class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join('') + `<button type="button" class="chip" data-q="">🙋 직접 물어보기</button>`;
  $$('#askChips button[data-q]').forEach(b => b.addEventListener('click', () => openChat(chatCtx).then(() => { if (b.dataset.q) askChat(b.dataset.q); })));
  $('#nav').style.display = 'grid';
}
function renderMissionCnt() { const f = FLOW.get(state.unit.unit); $('#missionCnt').textContent = `미션 문장 ${Math.min(f.sentences.length, FLOW.need)} / ${FLOW.need}`; }
(async function init() {
  if (!state) return; renderTopbar(); renderFlow(2); showHealth(); injectChat('tutor'); renderMissionCnt();
  const u = state.unit; $('#mission').textContent = u.mission || `${u.title} 단어로 한 문장 말해봐요`;
  const hint = (u.hint_words && u.hint_words.length) ? u.hint_words : (S.get().words || []).slice(0, 4).map(w => w.word);
  $('#hintWords').innerHTML = hint.length ? `<span class="k">힌트</span>` + hint.map(h => `<span>${esc(h)}</span>`).join('') : ''; reset();
  const why = micSupport(); if (why) { showResult('#tNote', '🎙 ' + esc(why) + ' ⌨ 쓰기는 돼요.', 'todo'); $('#recBtn').disabled = true; }
})();
