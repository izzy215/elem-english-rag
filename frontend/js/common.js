/* 공통 (B안): API · 화면 간 상태 · 상단바 · 샘플 데이터 폴백 · 오답노트(로컬) · 오디오 · 물어보기 챗
 * 서버에 아직 없는 API(/fix /ask /notebook /drill /patterns)는 여기의 폴백이 대신한다.
 * 서버가 생기면 폴백은 자동으로 안 쓰인다 (먼저 서버를 부르고, 404/실패일 때만 폴백). */

// ---------- API ----------
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!r.ok) { let msg = r.statusText; try { msg = (await r.json()).detail || msg; } catch (_) {} const e = new Error(msg); e.status = r.status; throw e; }
  return r.json();
}
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const shuffle = a => a.sort(() => Math.random() - .5);
const today = () => new Date().toISOString().slice(0, 10);

// ---------- 화면 간 상태 (sessionStorage) ----------
const S = {
  get() { try { return JSON.parse(sessionStorage.getItem('echo') || '{}'); } catch (_) { return {}; } },
  set(patch) { const s = { ...S.get(), ...patch }; sessionStorage.setItem('echo', JSON.stringify(s)); return s; },
};
function go(page) { location.href = page; }
function requireState(...keys) { const s = S.get(); for (const k of keys) if (s[k] == null) { go('index.html'); return null; } return s; }

// ---------- 상단바 · 상태줄 ----------
function renderTopbar({ back = true, crumbs = true } = {}) {
  const s = S.get(); const parts = [];
  if (crumbs && s.level) parts.push(`Level ${s.level.level}`);
  if (crumbs && s.unit) parts.push(`${s.unit.unit} ${s.unit.title}`);
  $('#topbar').innerHTML = `${back ? '<button class="back" onclick="history.back()">‹ 뒤로</button>' : ''}<div class="crumb">${parts.map(p => `<span>${esc(p)}</span>`).join('')}</div><div class="student">학생 ${esc(s.student || 'A')}</div>`;
}
async function showHealth() {
  const el = $('#status'); if (!el) return null;
  try {
    const h = await api('/api/health');
    el.textContent = (h.using_sample ? '임시 샘플 데이터로 동작 중' : `골든 데이터 ${(h.golden_files || []).join(', ')}`) + ' · 서버에 없는 기능은 화면 임시 동작';
    if (!h.api_key) { el.textContent += ' · ⚠ GEMINI_API_KEY 없음'; el.classList.add('warn'); }
    return h;
  } catch (e) { el.textContent = '서버 연결 실패'; el.classList.add('warn'); return null; }
}
function showResult(sel, html, kind = '') { const el = $(sel); el.className = 'result on ' + kind; el.innerHTML = html; }
function hideResult(sel) { const el = $(sel); if (el) el.className = 'result'; }

// ---------- 샘플 데이터 폴백 (frontend/data/sample-B/, 서버 API 생기기 전까지) ----------
const SB = { loaded: false, rules: [], faq: [], errors: [], patterns: [], units: [] };
function parseCSV(t) {
  const lines = t.replace(/\r/g, '').split('\n').filter(l => l.trim()); const head = lines.shift().split(',');
  return lines.map(l => { const cells = []; let cur = '', q = false; for (const ch of l) { if (ch === '"') q = !q; else if (ch === ',' && !q) { cells.push(cur); cur = ''; } else cur += ch; } cells.push(cur); return Object.fromEntries(head.map((h, i) => [h, (cells[i] || '').trim()])); });
}
async function loadSampleB() {
  if (SB.loaded) return SB;
  const jl = async n => (await (await fetch(`data/sample-B/${n}`)).text()).split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
  const cs = async n => parseCSV(await (await fetch(`data/sample-B/${n}`)).text());
  [SB.rules, SB.faq, SB.errors, SB.patterns, SB.units] = await Promise.all([jl('rules.jsonl'), jl('faq.jsonl'), jl('errors.jsonl'), cs('patterns.csv'), cs('units.csv')]);
  SB.loaded = true; return SB;
}
const ruleOf = id => SB.rules.find(r => r.id === id);
const unitMeta = unit => SB.units.find(u => u.unit === unit);

// ---------- 오답노트 (서버 /notebook 생기기 전까지 로컬 저장) ----------
const NB = {
  key: st => `notebook_${st}`,
  get(st) { try { return JSON.parse(localStorage.getItem(NB.key(st)) || '{}'); } catch (_) { return {}; } },
  save(st, n) { localStorage.setItem(NB.key(st), JSON.stringify(n)); },
  addWrong(st, ruleId, text, fixed, logId) {
    const n = NB.get(st); const e = n[ruleId] || { count: 0, last: '', streak: 0, examples: [] };
    e.count++; e.last = today(); e.streak = 0; e.examples.unshift({ text, fixed, logId, ts: today() }); e.examples = e.examples.slice(0, 5); n[ruleId] = e; NB.save(st, n);
  },
  drillResult(st, ruleId, allCorrect) { const n = NB.get(st); const e = n[ruleId]; if (!e) return; e.streak = allCorrect ? Math.min(2, e.streak + 1) : 0; NB.save(st, n); },
  active(st) { const n = NB.get(st); return Object.entries(n).filter(([, e]) => e.streak < 2).map(([id, e]) => ({ rule_id: id, ...e })); },
  overcome(st) { const n = NB.get(st); return Object.entries(n).filter(([, e]) => e.streak >= 2).map(([id, e]) => ({ rule_id: id, ...e })); },
};
async function fetchNotebook(student) {           // 서버 우선, 없으면 로컬
  try { return await api(`/api/notebook?student=${student}`); }
  catch (_) { await loadSampleB(); return { active: NB.active(student).map(e => ({ ...e, name: ruleOf(e.rule_id)?.type || e.rule_id })), overcome: NB.overcome(student).map(e => ({ ...e, name: ruleOf(e.rule_id)?.type || e.rule_id })), local: true }; }
}

// ---------- 오디오: 듣기(TTS) · 녹음 · 파형 ----------
async function playTTS(itemId, btn, label = '🔊 듣기') {
  const p = $('#player'); if (!p) return;
  if (btn) { btn.classList.add('on'); btn.textContent = '🔊 …'; }
  try {
    const r = await fetch(`/api/tts/${itemId}`); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    p.src = `/api/tts/${itemId}`; await p.play(); p.onended = () => { if (btn) { btn.classList.remove('on'); btn.textContent = label; } };
  } catch (e) { if (btn) { btn.classList.remove('on'); btn.textContent = label; } throw e; }
}
// 이 브라우저에서 녹음이 되는지. 안 되면 이유 문자열, 되면 null (카카오톡 인앱 브라우저 등은 마이크 API 가 없음)
function micSupport() {
  if (!window.isSecureContext) return '주소가 https 가 아니라 마이크를 쓸 수 없어요.';
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return '이 브라우저는 마이크를 지원하지 않아요. 카카오톡 안에서 열었다면 오른쪽 위 ⋮ → "다른 브라우저로 열기"(Chrome·Safari)로 열어 주세요.';
  if (!window.MediaRecorder) return '이 브라우저는 녹음을 지원하지 않아요. Chrome 또는 Safari 최신 버전으로 열어 주세요.';
  return null;
}
let REC = null;   // 지금 녹음 중인 것 (한 번에 하나만). REC.stop() 으로 끝낼 수 있다
function stopRecording() { if (REC) REC.stop(); }
function recordOnce({ maxMs = 5000, onStart } = {}) {
  return new Promise((resolve, reject) => { (async () => {
    if (REC) throw new Error('이미 녹음 중이에요. 버튼을 다시 눌러 먼저 끝내 주세요.');
    const why = micSupport(); if (why) throw new Error(why);
    let stream;
    try {   // 인앱 브라우저는 권한 창이 안 뜨고 영원히 대기하는 경우가 있어 15초 제한
      stream = await Promise.race([navigator.mediaDevices.getUserMedia({ audio: true }), new Promise((_, rj) => setTimeout(() => rj(new Error('timeout')), 15000))]);
    } catch (e) { throw new Error(e.message === 'timeout' ? '마이크 권한 응답이 없어요. Chrome·Safari 에서 직접 열어 주세요.' : `마이크를 사용할 수 없어요. 브라우저 권한을 확인하세요. (${e.name || e.message})`); }
    // 브라우저가 내는 포맷을 그대로 서버에 알려준다 (Chrome=webm, iPhone Safari=mp4)
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find(t => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t)) || '';
    const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream), chunks = [];
    const type = (rec.mimeType || mime || 'audio/webm').split(';')[0];
    rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
    const release = () => { stream.getTracks().forEach(t => t.stop()); REC = null; };   // 마이크 끄기 (브라우저 마이크 표시등도 꺼짐)
    rec.onerror = e => { release(); reject(new Error('녹음 중 오류: ' + (e.error?.message || e.name || ''))); };
    rec.onstop = async () => {
      release();
      const blob = new Blob(chunks, { type }); if (!blob.size) return reject(new Error('녹음된 소리가 없어요. 다시 눌러 말해 주세요.'));
      const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(',')[1]); fr.readAsDataURL(blob); });
      resolve({ blob, b64, mime: type });
    };
    const stop = () => { if (rec.state === 'recording') rec.stop(); };
    rec.start(); REC = { stop }; onStart && onStart(stop);
    setTimeout(stop, maxMs);
  })().catch(reject); });
}
// 느린 API 대기 중 잠금: 로딩바 + 메시지 표시, 화면의 모든 버튼 disabled (원래 disabled였던 건 그대로 둠)
let BUSY = false;
function setBusy(on, msg = '') {
  BUSY = on; document.body.classList.toggle('busy', on);
  if (!$('#loadbar')) document.body.insertAdjacentHTML('beforeend', '<div class="loadbar" id="loadbar"></div><div class="loadmsg" id="loadmsg"></div>');
  $('#loadbar').classList.toggle('on', on); const m = $('#loadmsg'); m.textContent = msg; m.classList.toggle('on', on && !!msg);
  $$('button').forEach(b => {
    if (on) { if (!b.disabled) { b.dataset.busyLock = '1'; b.disabled = true; } }
    else if (b.dataset.busyLock) { delete b.dataset.busyLock; b.disabled = false; }
  });
}
const SPEAK_TIMEOUT_MS = 90000;   // Cloudflare 터널은 100초 넘으면 끊으므로 그 전에 화면이 먼저 포기
async function speak(b64, itemId = '', msg = '🎧 듣는 중… 잠깐만요', mime = 'audio/webm') {   // 팀원 완성 API. item_id 없으면 받아쓰기(heard)만 의미 있음
  if (BUSY) throw new Error('아직 앞 문장을 듣는 중이에요. 잠깐만 기다려 주세요.');
  setBusy(true, msg);
  const t0 = Date.now(), tick = setInterval(() => { const m = $('#loadmsg'); if (m) m.textContent = `${msg} (${Math.round((Date.now() - t0) / 1000)}초)`; }, 1000);
  const ac = new AbortController(), timer = setTimeout(() => ac.abort(), SPEAK_TIMEOUT_MS);
  try { return await api('/api/speak', { method: 'POST', signal: ac.signal, body: JSON.stringify({ student: S.get().student || 'A', item_id: itemId, audio_base64: b64, mime }) }); }
  catch (e) { throw e.name === 'AbortError' ? new Error('서버 응답이 90초 넘게 없어요. 잠시 후 다시 해 주세요.') : e; }
  finally { clearTimeout(timer); clearInterval(tick); setBusy(false); }
}
async function waveFromBlob(blob, bars = 26) {     // 실제 파형: 구간별 RMS
  try { const ctx = new (window.AudioContext || window.webkitAudioContext)(); const buf = await ctx.decodeAudioData(await blob.arrayBuffer()); const d = buf.getChannelData(0); const seg = Math.floor(d.length / bars); const out = []; for (let i = 0; i < bars; i++) { let s = 0; for (let j = i * seg; j < (i + 1) * seg; j++) s += d[j] * d[j]; out.push(Math.sqrt(s / seg)); } const m = Math.max(...out) || 1; return out.map(v => v / m); } catch (_) { return null; }
}
function drawWave(el, vals) { el.innerHTML = (vals || Array(26).fill(.15)).map(v => `<i style="height:${Math.max(4, Math.round(v * 38))}px"></i>`).join(''); }

// ---------- 튜터 폴백: 규칙 감지 (서버 /fix 생기기 전까지 화면에서 대충) ----------
function detectRule(text) {
  const l = text.toLowerCase().replace(/[.!?]/g, ' ').trim(), W = l.split(/\s+/);
  const past = { go: 'went', see: 'saw', eat: 'ate', have: 'had', play: 'played', visit: 'visited', watch: 'watched', am: 'was', is: 'was', are: 'were' };
  if (/\b(yesterday|last (week|night|year)|ago)\b/.test(l)) { const w = W.find(x => past[x]); if (w) return { rule_id: w === 'am' || w === 'is' || w === 'are' ? 'R-07' : 'R-01', wrong: w, fix: past[w], fixed: text.replace(new RegExp(`\\b${w}\\b`, 'i'), past[w]) }; }
  const m1 = l.match(/\ba ([aeiou]\w*)/); if (m1) return { rule_id: 'R-04', wrong: 'a', fix: 'an', fixed: text.replace(/\ba (?=[aeiouAEIOU])/, 'an ') };
  const m2 = l.match(/\b(he|she|it|the \w+|my \w+) (eat|like|play|go|have|want|read)\b/); if (m2 && !/\b(am|is|are|was|were)\b/.test(l)) { const v = m2[2], fix = v === 'have' ? 'has' : v === 'go' ? 'goes' : v + 's'; return { rule_id: 'R-02', wrong: v, fix, fixed: text.replace(new RegExp(`\\b${v}\\b`, 'i'), fix) }; }
  const m3 = l.match(/\b(am|is|are) (\w+)\b/); if (m3 && /\bnow\b/.test(l) && !m3[2].endsWith('ing')) return { rule_id: 'R-05', wrong: m3[2], fix: m3[2] + 'ing', fixed: text.replace(new RegExp(`\\b${m3[2]}\\b`, 'i'), m3[2] + 'ing') };
  const m4 = l.match(/\b(he|she|it) (are|am)\b|\bi (is|are)\b|\b(they|we|you) (is|am)\b/); if (m4) { const wrong = (m4[2] || m4[3] || m4[5]); const subj = (m4[1] || (m4[3] ? 'i' : m4[4])); const fix = subj === 'i' ? 'am' : ['he', 'she', 'it'].includes(subj) ? 'is' : 'are'; return { rule_id: 'R-06', wrong, fix, fixed: text.replace(new RegExp(`\\b${wrong}\\b`, 'i'), fix) }; }
  const m5 = l.match(/\b(two|three|four|five|many|some) (\w+?)\b(?!s\b)/); if (m5 && !m5[2].endsWith('s')) return { rule_id: 'R-03', wrong: m5[2], fix: m5[2] + 's', fixed: text.replace(new RegExp(`\\b${m5[2]}\\b`, 'i'), m5[2] + 's') };
  const m6 = l.match(/\b(want|have|see|saw) (banana|dog|cat|apple|pizza|sandwich|book|pencil)\b/); if (m6) return { rule_id: 'R-08', wrong: m6[2], fix: 'a ' + m6[2], fixed: text.replace(new RegExp(`\\b${m6[2]}\\b`, 'i'), 'a ' + m6[2]) };
  return null;
}
async function fixSentence(text, ctx) {             // 서버 /fix 우선, 없으면 폴백
  try { return { ...(await api('/api/fix', { method: 'POST', body: JSON.stringify({ student: S.get().student, level: ctx.level, unit: ctx.unit, text, source: ctx.source }) })), mode: 'server' }; }
  catch (_) {
    await loadSampleB(); const d = detectRule(text); const logId = 'L-' + Date.now();
    if (!d) return { ok: true, rule: null, wrong: null, fix: null, fixed: text, why: '문법에 맞는 문장이에요. 다른 문장도 말해볼까요?', source: null, suggested_questions: ['다른 예문 보여줘', 'saw는 무슨 뜻이에요?'], log_id: logId, mode: 'fallback' };
    const r = ruleOf(d.rule_id) || { id: d.rule_id, type: d.rule_id, text: '' };
    return { ok: false, rule: { id: r.id, name: r.type, score: 0.9 }, runner_up: null, wrong: d.wrong, fix: d.fix, fixed: d.fixed, why: (r.text || '').split(/\s*(?:틀린\s*)?예\s*:/)[0], source: { chunk_id: r.id, text: r.text }, more_errors: false, suggested_questions: SB.faq.filter(f => f.rule_ids.includes(r.id)).slice(0, 2).map(f => f.question).concat(['다른 예문 보여줘']), log_id: logId, mode: 'fallback' };
  }
}

// ---------- 물어보기 챗 (서버 /ask 우선, 없으면 FAQ 로컬 매칭) ----------
let CHAT = { ctx: {}, turns: 0 };
function injectChat(screen) {
  if ($('#chatFab')) return;
  document.body.insertAdjacentHTML('beforeend', `<button class="fab" id="chatFab" onclick="openChat()">🙋</button><div class="sheet-bg" id="chatBg" onclick="closeChat()"></div>
    <div class="sheet" id="chat"><div class="hd"><div class="t">🙋 물어보기 <button onclick="closeChat()">✕</button></div><div class="ctx" id="chatCtx"></div></div>
    <div class="msgs" id="chatMsgs"></div><div class="sugg" id="chatSugg"></div>
    <div class="inp"><input id="chatIn" placeholder="궁금한 걸 써 보세요" onkeydown="if(event.key==='Enter') sendChat()"><button class="mic" onclick="chatMic()">🎙</button><button onclick="sendChat()">보내기</button></div></div>`);
  CHAT.screen = screen;
}
async function openChat(extra = {}) {
  await loadSampleB(); const s = S.get(); CHAT.ctx = { screen: CHAT.screen, unit: s.unit?.unit, ...extra }; CHAT.turns = 0;
  const chips = []; if (s.unit) chips.push(`${s.unit.unit} ${s.unit.title}`); if (CHAT.ctx.rule_id) chips.push('방금: ' + (ruleOf(CHAT.ctx.rule_id)?.type || CHAT.ctx.rule_id)); if (CHAT.screen === 'notebook') chips.push('오답노트'); if (CHAT.screen === 'shadow') chips.push('따라 말하기');
  $('#chatCtx').innerHTML = chips.map(c => `<span>📍 ${esc(c)}</span>`).join('');
  $('#chatMsgs').innerHTML = `<div class="msg bot">안녕! 지금 배우는 것에 대해 뭐든 물어봐. 아래 질문을 눌러도 돼 🙂</div>`;
  const sug = CHAT.ctx.rule_id ? SB.faq.filter(f => f.rule_ids.includes(CHAT.ctx.rule_id)).map(f => f.question) : SB.faq.filter(f => f.unit === 'ALL' || f.unit === CHAT.ctx.unit).map(f => f.question);
  renderSugg(sug.slice(0, 3)); $('#chat').classList.add('on'); $('#chatBg').classList.add('on');
}
function renderSugg(list) { $('#chatSugg').innerHTML = list.map(q => `<button onclick="askChat(${JSON.stringify(q)})">${esc(q)}</button>`).join(''); }
function closeChat() { stopRecording(); $('#chat').classList.remove('on'); $('#chatBg').classList.remove('on'); }
function faqMatch(q) {                             // 폴백: 질문 ↔ question+variants 단어 겹침
  const norm = t => t.toLowerCase().replace(/[?？.!,]/g, '').split(/\s+/).filter(Boolean);
  const qs = norm(q); let best = null, bs = 0;
  for (const f of SB.faq) { const cands = [f.question, ...(f.variants || [])]; for (const c of cands) { const cs = norm(c); const hit = cs.filter(w => qs.some(x => x.includes(w) || w.includes(x))).length; const sc = hit / Math.max(cs.length, 1); if (sc > bs) { bs = sc; best = f; } } }
  return bs >= 0.5 ? best : null;
}
async function askChat(q) {
  const m = $('#chatMsgs'); m.insertAdjacentHTML('beforeend', `<div class="msg me">${esc(q)}</div>`); m.scrollTop = m.scrollHeight;
  let r;
  try { r = await api('/api/ask', { method: 'POST', body: JSON.stringify({ student: S.get().student, question: q, context: CHAT.ctx }) }); }
  catch (_) { const f = faqMatch(q); r = f ? { answer: f.answer, source: f.rule_ids.map(id => ({ chunk_id: id })).concat([{ chunk_id: f.id }]), offtopic: false, fallback: true } : { answer: '음, 그건 영어 공부랑은 조금 다른 것 같아. 선생님께 물어볼까? 🙂', offtopic: true, fallback: true }; }
  m.insertAdjacentHTML('beforeend', `<div class="msg bot ${r.offtopic ? 'warn' : ''}">${esc(r.answer)}${r.source && r.source.length ? `<div class="src">📚 근거 · ${r.source.map(s => esc(s.chunk_id)).join(' · ')}</div>` : (r.offtopic ? `<div class="src">검색 점수 낮음 → 조각 밖 답변 안 함</div>` : '')}${r.fallback ? `<div class="src" style="opacity:.7">서버 /ask 구현 전 · FAQ 샘플로 임시 답변</div>` : ''}</div>`);
  m.scrollTop = m.scrollHeight; CHAT.turns++;
  if (r.suggested && r.suggested.length) renderSugg(r.suggested); if (CHAT.turns >= 3) $('#chatSugg').innerHTML = `<button onclick="closeChat()">이제 돌아갈게요 ↩</button>`;
}
function sendChat() { const v = $('#chatIn').value.trim(); if (!v) return; $('#chatIn').value = ''; askChat(v); }
async function chatMic() {           // 한 번 누르면 녹음 시작, 다시 누르면 끝 (5초 지나면 자동으로 끝)
  if (BUSY) return;
  if (REC) { stopRecording(); return; }
  const btn = $('.inp .mic'), inp = $('#chatIn'), ph = inp.placeholder;
  btn.textContent = '⏹'; btn.classList.add('rec'); inp.placeholder = '말하는 중… 다시 누르면 끝';
  try { const { b64, mime } = await recordOnce({ maxMs: 5000 }); btn.textContent = '…'; btn.classList.remove('rec'); const r = await speak(b64, '', '🎧 듣는 중…', mime); if (r.heard) inp.value = r.heard; else inp.placeholder = '잘 안 들렸어요. 다시 말해볼까요?'; }
  catch (e) { inp.placeholder = e.message; }
  finally { btn.textContent = '🎙'; btn.classList.remove('rec'); if (inp.placeholder === '말하는 중… 다시 누르면 끝') inp.placeholder = ph; }
}
