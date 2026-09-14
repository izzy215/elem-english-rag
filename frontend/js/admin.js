/* 관리자 (PRD 3.7 · docs/plan-B/mockup.html 관리자 웹)
 * 골든 데이터 파일별 개수(/api/admin/golden) · RAG 정확도(/api/rag/eval + 모델별 비교 /api/admin/eval_history) · 학생 문장 로그 + 우리 규칙으로 못 짚은 문장(/api/admin/log 의 rows·gaps)
 * 서버에 아직 없는 API(404)면 그 패널만 "서버 재시작 필요" 로 두고 나머지는 그린다.
 */
const pct = v => v == null ? '–' : Math.round(v * 100) + '%';
const when = iso => iso ? iso.slice(5, 16).replace('T', ' ') : '';

// ---------- 골든 데이터 ----------
async function loadGolden(health) {
  let g = null;
  try { g = await api('/api/admin/golden'); }
  catch (e) {
    if (!health) { $('#dataStatus').textContent = '서버 연결 실패'; return; }
    $('#dataStatus').innerHTML = (health.using_sample ? '<span class="pill warn">임시 샘플</span>' : '<span class="pill ok">골든 데이터</span>') + esc((health.golden_files || []).join(', '));
    $('#indexStatus').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> 파일별 개수는 <code>/api/admin/golden</code> (backend/admin.py) 이 뜨면 나와요.' : '개수 확인 실패: ' + esc(e.message);
    return;
  }
  $('#dataStatus').innerHTML = (g.using_sample ? '<span class="pill warn">임시 샘플</span> 데이터팀 납품 전' : '<span class="pill ok">골든 데이터</span>') + ` <code>${esc(g.dir)}/</code>`;
  $('#dataTable').innerHTML = `<tr><th>파일</th><th>내용</th><th style="text-align:right">개수</th></tr>` + g.files.map(f => `
    <tr><td class="f">${esc(f.file)}${f.indexed ? ` <span class="pill idx" title="이 파일이 들어간 검색 색인">색인${f.index && f.index !== 'rules' ? ' · ' + esc(f.index) : ''}</span>` : (f.index ? ` <span class="pill warn" title="색인이 아직 없음 — python -m backend.textbook --rebuild">색인 없음</span>` : '')}</td><td>${esc(f.desc)}</td>
      <td class="n">${f.count == null ? '<span class="pill warn">없음</span>' : (f.indexed ? `<b>${f.count}</b>` : f.count)}</td></tr>`).join('');
  if (!g.index) { $('#indexStatus').innerHTML = '<span class="tag">색인 없음</span> RAG 담당: <code>python -m backend.indexing --rebuild</code>'; return; }
  const ix = g.indexes || {};   // 검색 색인 네 가지 (rules 는 RAG 담당 indexing.py · textbook·examples·faq 는 backend/textbook.py)
  const extra = [ix.textbook ? `교과서 <b>${ix.textbook.count}</b>(패턴 ${ix.textbook.patterns} · 단어 ${ix.textbook.words})` : '교과서 <span class="pill warn">없음</span>',
                 ix.examples ? `틀린 예문 <b>${ix.examples.count}</b>` : '틀린 예문 <span class="pill warn">없음</span>',
                 ix.faq ? `FAQ <b>${ix.faq.count}</b>(질문+변형, ${ix.faq.faqs}개)` : 'FAQ <span class="pill warn">없음</span>'].join(' · ');
  $('#indexStatus').innerHTML = `검색 색인: 규칙 <b>${g.index.count}</b>개 · ${extra} · 임베딩 ${esc(g.index.model || '')} · 규칙 색인 ${esc(when(g.index.generated_at))} 생성`
    + (g.index_stale ? ' · <span class="pill warn">rules.jsonl 과 개수가 달라요 — --rebuild 필요</span>' : '')
    + ((!ix.textbook || !ix.examples || !ix.faq) ? ' · <code>python -m backend.textbook --rebuild</code>' : '');
}

// ---------- RAG 정확도 ----------
async function loadEval() {
  let r = null;
  try { r = await api('/api/rag/eval'); } catch (_) {}
  if (!r || r.hit_at_3 == null) {
    $('#evalHint').innerHTML = '<span class="tag">측정 전</span> RAG 담당이 <code>python -m tests.eval_rag --retrieval-only</code> 를 돌리면 여기에 숫자가 나와요. 목표 hit@3 ≥ 80%';
    return;
  }
  $('#hit3').textContent = pct(r.hit_at_3); $('#hit3').className = 'num' + (r.hit_at_3 >= .8 ? '' : ' na');
  $('#hit1').textContent = pct(r.hit_at_1); $('#hit1').className = 'num';
  $('#evalN').textContent = r.n; $('#evalN').className = 'num';
  if (r.total_n) $('#evalDesc').textContent = `시험지(eval.csv) ${r.total_n}문장 중 오류 문장 ${r.n}개 채점 (정상 문장 ${r.normal_n ?? r.total_n - r.n}개 제외) · 정답 규칙이 상위 3개 안에 들면 맞힘`;
  let hist = null;                                          // 모델(+재랭킹)별 최신 실행 — 서버 재시작 전(404)이면 null → 예전 runs 방식으로 폴백
  try { hist = await api('/api/admin/eval_history'); } catch (_) { hist = null; }
  renderRuns(hist, r.runs || []);
  const extra = [r.hit_at_5 != null ? `hit@5 ${pct(r.hit_at_5)} (/fix 가 받는 검색 후보 안 — tutor.py RAG_TOP_K=5 와 같이 바꿀 것)` : '', r.evaluated_at ? `${when(r.evaluated_at)} 측정` : '', r.index?.model ? esc(r.index.model) : ''].filter(Boolean).join(' · ');
  const stale = (r.stale && r.evaluation_hash) ? ' · <span class="pill warn">색인·시험지가 평가 뒤에 바뀜 — eval_rag 다시 돌려야 함</span>' : '';   // evaluation_hash 는 eval_rag 가 아직 안 써서(RAG 담당) 그 전엔 stale 이 항상 true → 값이 생긴 뒤에만 표시
  $('#evalHint').innerHTML = (r.hit_at_3 >= .8 ? '목표(80%) 달성' : '목표 80%까지 ' + Math.round((.8 - r.hit_at_3) * 100) + '%p 남음') + (extra ? ' · ' + extra : '') + stale;
  renderMiss(r.rows || []);
}
const day = iso => iso ? iso.slice(5, 10) : '–';   // "09-14" — 비교 표(renderRuns)·튜터 표(renderFix) 공용
function renderRuns(hist, runs) {   // 표: eval_history.latest (모델·재랭킹별 최신 실행) — 시험지(문장 수 + data_hash)별로 묶고, 같은 시험지 안에서 hit@3 최고 행 강조. 서버 재시작 전(404)이면 예전 runs 막대
  const latest = (hist && Array.isArray(hist.latest) && hist.latest.length) ? hist.latest : null;
  if (!latest) {
    if (hist && hist.sheet) { $('#runs').innerHTML = `<div class="d">임베딩 모델 · 재랭킹 비교 — 지금 시험지(${hist.sheet.n}문장)로 돌린 실행이 아직 없어요 · <code>python -m tests.eval_rag --retrieval-only</code></div>`; return; }
    if (!runs.length) { $('#runs').innerHTML = ''; return; }
    const best = Math.max(...runs.map(x => x.hit_at_3 || 0));
    $('#runs').innerHTML = `<div class="d">비교 실험 — 색인 방식 · 임베딩 모델별 hit@3 (RAG 담당이 runs 에 추가)</div>` + runs.map(x => `
      <div class="bar"><span class="lb">${esc(x.label)}</span><div class="track"><i class="${x.hit_at_3 === best ? 'best' : ''}" style="width:${Math.round((x.hit_at_3 || 0) * 100)}%"></i></div><span class="v">${pct(x.hit_at_3)}</span></div>`).join('');
    return;
  }
  const sheet = x => `${x.n ?? 0}|${String(x.data_hash || '').replace(/^sha256:/, '').slice(0, 6)}`;   // 시험지 = 문장 수 + 해시 앞 6자리 (다르면 직접 비교 불가)
  const rows = [...latest].sort((a, b) => (b.n || 0) - (a.n || 0) || sheet(a).localeCompare(sheet(b)) || (b.hit_at_3 || 0) - (a.hit_at_3 || 0));
  const bestOf = {}; rows.forEach(x => { const k = sheet(x); bestOf[k] = Math.max(bestOf[k] ?? -1, x.hit_at_3 || 0); });
  let prev = null;
  const hidden = hist.sheet && hist.sheet.hidden_labels ? ` · 지금 시험지(${hist.sheet.n}문장)와 짝이 안 맞는 실행 ${hist.sheet.hidden_labels}건은 숨김` : '';
  $('#runs').innerHTML = `<div class="d">임베딩 모델 · 재랭킹 비교 (같은 시험지 ${hist.sheet ? hist.sheet.n + '문장' : ''} 기준)</div>`;
  const has5 = rows.some(x => x.hit_at_5 != null);   // hit@5 = /fix 가 프롬프트에 넣는 후보 5개 안에 정답이 있나 (eval_rag 가 K=5 로 기록할 때만 열이 생김)
  $('#runs').innerHTML += `
    <table class="mini" id="evalRuns"><colgroup><col style="width:20%"><col style="width:${has5 ? 26 : 36}%"><col style="width:14%">${has5 ? '<col style="width:13%">' : ''}<col style="width:${has5 ? 13 : 15}%"><col style="width:${has5 ? 14 : 15}%"></colgroup>
    <tr><th title="문장 수 · 측정일 (두 줄)">시험지</th><th>임베딩 모델</th><th>재랭킹</th>${has5 ? '<th style="text-align:right" title="/fix 가 LLM 에 주는 후보 5개 안에 정답 규칙이 든 비율">hit@5</th>' : ''}<th style="text-align:right">hit@3</th><th style="text-align:right">hit@1</th></tr>` + rows.map(x => {
      const k = sheet(x), sep = prev !== null && k !== prev; prev = k;
      const best = (x.hit_at_3 || 0) === bestOf[k];
      const tip = `${x.file || ''}${x.evaluated_at ? ' · ' + when(x.evaluated_at) + ' 측정' : ''}${x.data_hash ? ' · ' + x.data_hash : ''}`;   // 실행 파일·측정 시각·해시는 행 툴팁으로만 (열로 두면 패널 밖으로 넘침)
      return `<tr class="${sep ? 'sep' : ''}${best ? ' best' : ''}" title="${esc(tip)}"><td>${x.total_n ?? x.n ?? '–'}문장<span class="sm">${esc(day(x.evaluated_at))} 측정</span></td><td class="m">${esc(x.model || '?')}${x.corpus && x.corpus !== 'rules' ? `<span class="sm">${esc(x.corpus_label || x.corpus)}</span>` : ''}</td><td class="m">${x.reranker ? esc(x.reranker) : '<span style="color:var(--muted)">검색만</span>'}</td>
        ${has5 ? `<td class="n">${x.hit_at_5 != null ? pct(x.hit_at_5) : '–'}</td>` : ''}<td class="n">${pct(x.hit_at_3)}</td><td class="n">${pct(x.hit_at_1)}</td></tr>`;
    }).join('') + `</table>
    <div class="d sub">실행 ${(hist.runs || []).length}회${hidden} · <code>python -m tests.eval_rag --retrieval-only</code> 로 실행하면 자동 추가 · 행에 마우스를 올리면 실행 파일 · 측정 시각 · 해시</div>`;
}
function renderMiss(rows) {   // 검색이 3위 안에 정답 규칙을 못 넣은 시험 문장 — 어느 규칙을 놓쳤고 대신 무엇을 골랐나 (RAG 담당·데이터팀이 볼 곳)
  const miss = rows.filter(x => !x.is_normal && !x.hit_at_3);
  if (!rows.length) { $('#missTable').innerHTML = ''; $('#missHint').textContent = ''; return; }
  if (!miss.length) { $('#missTable').innerHTML = ''; $('#missHint').textContent = '놓친 문장 없음 — 오류 문장 전부 3위 안에 정답 규칙이 들어 있어요'; return; }
  const name = c => `${esc(c.id)} ${esc(c.type || '')}`;
  $('#missTable').innerHTML = `<colgroup><col style="width:42%"><col style="width:18%"><col style="width:40%"></colgroup><tr><th>놓친 문장</th><th>정답 규칙</th><th>검색이 고른 1~3위</th></tr>` + miss.map(x => `
    <tr><td>${esc(x.text)}</td><td><b>${esc(x.expected_rule_id)}</b></td>
      <td class="c">${(x.candidates || []).slice(0, 3).map(c => `${name(c)} <span style="color:var(--muted)">${(c.score ?? 0).toFixed(2)}</span>`).join(' · ')}${x.error ? ` <span class="pill warn">${esc(x.error)}</span>` : ''}</td></tr>`).join('');
  $('#missHint').textContent = `놓친 문장 ${miss.length}개 — 이 규칙들의 설명문·예문을 보강하거나(데이터팀) 검색 방식을 손보는(RAG 담당) 근거`;
}

// ---------- 학생 문장 로그 ----------
async function loadLog() {
  const days = $('#logDays').value;
  let r = null;
  try { r = await api(`/api/admin/log?days=${days}`); }
  catch (e) {
    $('#logTable').innerHTML = '';
    $('#logHint').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> <code>/api/admin/log</code> (backend/admin.py) 이 뜨면 나와요.' : '로그 읽기 실패: ' + esc(e.message);
    return;
  }
  const llm = Object.entries(r.llm || {}).map(([k, v]) => `${esc(k)} ${v}`).join(' · ');
  const tm = r.timing ? ` · 평균 응답 <b>${(r.timing.total_ms / 1000).toFixed(1)}초</b> (검색 ${(r.timing.search_ms / 1000).toFixed(1)}초 · 모델 호출 ${r.timing.llm_calls}회, ${r.timing.n}문장 기준)` : '';
  const gr = r.grounded ? ` · 설명이 규칙 문서에서 나옴 <b>${r.grounded.yes}/${r.grounded.n}</b>` : '';   // 규칙으로 고친 문장 중 설명(why)이 검색된 규칙 문서 본문인 비율 — RAG 근거성 지표
  const tbl = r.textbook ? ` · 교과서 표현으로 고침 <b>${r.textbook.used_pattern}/${r.textbook.n}</b> · 학년 밖 단어 나온 문장 <b>${r.textbook.outside.length}</b>` : '';   // 서버가 used_pattern·outside_words 를 로그에 쓰기 시작하면 표시
  $('#logDesc').innerHTML = `문장 <b>${r.n}</b>개 · 맞음 ${r.ok_n} · 고침 ${r.n - r.ok_n} · 학생 ${r.students}명${llm ? ` · 처리 모델: ${llm}` : ''}${tm}${gr}${tbl}`;
  if (!r.rows.length) { $('#logTable').innerHTML = ''; $('#logHint').innerHTML = '<div class="empty">이 기간에 고친 문장이 없어요.</div>'; return; }
  $('#logTable').innerHTML = `<tr><th>규칙</th><th style="text-align:right">걸린 횟수</th><th style="text-align:right">학생 수</th><th>예시 문장 (최근)</th></tr>` + r.rows.map((x, i) => `
    <tr><td>${esc(x.name)} <span style="color:var(--muted);font-size:.75rem">${esc(x.rule_id)}</span></td>
      <td class="n">${i === 0 ? `<b>${x.count}</b>` : x.count}</td><td class="n">${x.students}</td><td>${esc(x.example)}</td></tr>`).join('');
  $('#logHint').textContent = 'data/student/sentence_log.jsonl 집계 · 맞은 문장(ok)은 개수에만 들어가요';
  renderGaps(r.gaps || []);
}
function renderGaps(gaps) {
  if (!gaps.length) { $('#gapTable').innerHTML = ''; $('#gapHint').innerHTML = '<div class="empty">이 기간에는 없어요.</div>'; return; }
  $('#gapTable').innerHTML = `<tr><th>때</th><th>학생 문장</th><th>어떻게 걸렸나</th><th>쓴 모델</th><th>고친 문장 / 이유</th></tr>` + gaps.map(g => `
    <tr><td class="n">${esc(when(g.ts))}</td><td>${esc(g.text)}</td><td><span class="pill ${g.kind === '규칙 밖' ? 'idx' : g.kind === '생성 점검' ? 'ok' : 'warn'}">${esc(g.kind)}</span></td>
      <td class="f">${esc(g.llm || '')}</td><td>${g.kind === '생성 점검' ? `${esc(g.reason)}${g.fixed ? ` · 만든 모델의 정답: ${esc(g.fixed)}` : ''}` : esc(g.fixed || g.reason)}</td></tr>`).join('');
  $('#gapHint').textContent = `${gaps.length}건 · "규칙 밖" = 튜터가 규칙 없이 고침, "진단 실패" = 튜터가 고치지 못함 (둘 다 학생 로그) · "생성 점검" = 아래 패널에서 만든 문장 중 우리 규칙에 없는 오류인데 튜터가 맞다고 한 것 (만든 모델의 판단이라 사람이 확인)`;
}

// ---------- 생성 점검 (POST /api/admin/gen_gaps → 백그라운드, GET 으로 진행·결과) ----------
const RES = { ok: ['맞는 문장이라고 함', 'ok'], rule: ['규칙으로 고침', ''], OTHER: ['규칙 없이 고침(규칙 밖)', 'bad'], fail: ['고치지 못함(오류)', 'bad'], llm_err: ['모델 호출 실패', 'bad'] };
let genTimer = null;
async function loadGen() {
  let r = null;
  try { r = await api('/api/admin/gen_gaps'); }
  catch (e) { $('#genStatus').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> <code>/api/admin/gen_gaps</code> (backend/gapcheck.py)' : '읽기 실패: ' + esc(e.message); return; }
  const sel = $('#genBackend');
  if (!sel.options.length) sel.innerHTML = (r.backends || []).map(b => `<option value="${esc(b)}" ${b === r.default_backend ? 'selected' : ''}>${esc(b)}${b === r.default_backend ? ' (.env 기본)' : ''}</option>`).join('');
  const j = r.job || {};
  $('#genBtn').disabled = !!j.running;
  if (j.running) {
    $('#genStatus').innerHTML = `⏳ ${esc(j.backend)} 로 ${j.done}/${j.total} 진단 중… ${esc((j.log || []).slice(-1)[0] || '문장 만드는 중')}`;
    if (!genTimer) genTimer = setInterval(loadGen, 3000);
    return;
  }
  if (genTimer) { clearInterval(genTimer); genTimer = null; loadLog(); }
  const g = r.latest || {};
  if (j.error) { $('#genStatus').innerHTML = `<span class="pill warn">실패</span> ${esc(j.error)}`; }
  else if (!g.results) { $('#genStatus').innerHTML = '<div class="empty">아직 돌린 적이 없어요. 모델을 고르고 [실행]을 눌러 주세요.</div>'; $('#genTable').innerHTML = ''; return; }
  else {
    const t = g.tally || {};
    $('#genStatus').innerHTML = `최근 실행 ${esc(when(g.ran_at))} · <b>${esc(g.backend)}:${esc(g.model || '')}</b> · 문장 ${g.results.length}개 — 맞는 문장이라고 함 ${t.ok} · 규칙으로 고침 ${t.rule} · 규칙 없이 고침 ${t.OTHER} · 고치지 못함 ${t.fail} · 모델 호출 실패 ${t.llm_err}`
      + ` · <b>빠진 규칙 후보 ${(g.missed_outside || []).length}</b> (우리 규칙에 없는 오류로 만들었는데 튜터가 맞다고 한 문장)`;
  }
  $('#genTable').innerHTML = `<tr><th>#</th><th>튜터에 넣은 문장</th><th>어떤 오류로 만들었나 (만든 모델 말)</th><th>우리 규칙에 있는 오류?</th><th>튜터가 한 일</th><th>자세히</th></tr>` + (g.results || []).map((x, i) => `
    <tr><td class="n">${i + 1}</td><td>${esc(x.text)}${x.correct && x.correct !== x.text ? `<div style="color:var(--muted);font-size:.75rem">정답(모델): ${esc(x.correct)}</div>` : ''}</td>
      <td>${esc(x.intended)}</td><td>${x.inside ? '있음' : '<b>없음</b>'}</td>
      <td class="${RES[x.result]?.[1] || ''}">${RES[x.result]?.[0] || esc(x.result)}${!x.inside && x.result === 'ok' ? ' ⚠ 규칙이 없어 놓쳤을 수 있음' : x.inside && x.result === 'ok' ? ' ⚠ 규칙이 있는데 놓침' : ''}</td><td>${esc(x.detail)}</td></tr>`).join('');
}
async function runGen() {
  const n = parseInt($('#genN').value) || 20, backend = $('#genBackend').value || null;
  $('#genBtn').disabled = true; $('#genStatus').textContent = '시작하는 중…';
  try { await api('/api/admin/gen_gaps', { method: 'POST', body: JSON.stringify({ n, backend }) }); }
  catch (e) { $('#genStatus').innerHTML = '시작 실패: ' + esc(e.message); $('#genBtn').disabled = false; return; }
  loadGen();
}

// ---------- 검색 평가 실행 (GET/POST /api/admin/eval_run → tests/eval_embed.py 서브프로세스, 끝나면 비교 표 새로고침) ----------
let evTimer = null, evOpts = null;
function evFillModels() {
  const b = $('#evBackend').value, sel = $('#evModel');
  const d = evOpts?.default || {};
  if (b === 'gemini') { sel.innerHTML = '<option value="">gemini-embedding-001</option>'; sel.disabled = true; }
  else {
    sel.disabled = false;
    sel.innerHTML = (evOpts?.models || []).map(m => `<option value="${esc(m)}" ${b === d.backend && m === d.model ? 'selected' : ''}>${esc(m)}</option>`).join('');
  }
  $('#evTopn').disabled = !$('#evRerank').value;
}
async function loadEvalRun() {
  let r = null;
  try { r = await api('/api/admin/eval_run'); }
  catch (e) { $('#evStatus').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> <code>/api/admin/eval_run</code> (backend/evalrun.py)' : '읽기 실패: ' + esc(e.message); $('#evBtn').disabled = true; return; }
  if (!evOpts) {
    evOpts = r.options || {};
    const d = evOpts.default || {};
    $('#evBackend').innerHTML = (evOpts.backends || []).map(b => `<option value="${esc(b)}" ${b === d.backend ? 'selected' : ''}>${esc(b)}${b === d.backend ? ' (.env)' : ''}</option>`).join('');
    $('#evRerank').innerHTML = '<option value="">재랭킹 없음(검색만)</option>' + (evOpts.rerankers || []).map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
    $('#evCorpus').innerHTML = (evOpts.corpora || [{ id: 'rules', label: '규칙 설명문' }]).map(c => `<option value="${esc(c.id)}">${esc(c.label)}</option>`).join('');
    $('#evBackend').addEventListener('change', evFillModels); $('#evRerank').addEventListener('change', evFillModels);
    evFillModels();
  }
  const j = r.job || {};
  $('#evBtn').disabled = !!j.running;
  if (j.running) {
    const pct = j.total ? Math.round(j.done / j.total * 100) : 0;
    $('#evStatus').innerHTML = `⏳ <b>${esc(j.label)}</b> ${j.total ? `${j.done}/${j.total} (${pct}%)` : '준비 중(모델 로드·규칙 임베딩)'} … ${esc((j.log || []).slice(-1)[0] || '')}`;
    if (!evTimer) evTimer = setInterval(loadEvalRun, 2500);
    return;
  }
  if (evTimer) { clearInterval(evTimer); evTimer = null; loadEval(); }   // 끝남 → 비교 표·놓친 문장 새로고침
  if (j.error) $('#evStatus').innerHTML = `<span class="pill warn">실패</span> ${esc(j.label || '')} — ${esc(j.error)}`;
  else if (j.result_file) $('#evStatus').innerHTML = `완료 <b>${esc(j.label)}</b> · ${esc((j.log || []).filter(l => l.includes('hit@1')).slice(-1)[0] || '')} · <code>${esc(j.result_file)}</code>`;
  else $('#evStatus').textContent = evOpts?.note?.[$('#evBackend').value] || '';
}
async function runEval() {
  const backend = $('#evBackend').value, model = $('#evModel').value || null, rerank = $('#evRerank').value || null, topn = parseInt($('#evTopn').value) || 10, corpus = $('#evCorpus').value || 'rules';
  if (backend === 'gemini') {
    const n = (parseInt($('#evalN').textContent) || 0) + 100;
    if (!confirm(`Gemini 임베딩 약 ${n}회를 써요 (무료 한도 하루 1,000회). 계속할까요?`)) return;
  }
  $('#evBtn').disabled = true; $('#evStatus').textContent = '시작하는 중…';
  try { await api('/api/admin/eval_run', { method: 'POST', body: JSON.stringify({ backend, model, rerank, topn, corpus }) }); }
  catch (e) { $('#evStatus').innerHTML = '시작 실패: ' + esc(e.message); $('#evBtn').disabled = false; return; }
  loadEvalRun();
}

// ---------- 튜터 정확도 (/fix 끝까지) — GET /api/admin/fix_history 표 + GET/POST /api/admin/fix_run 실행 ----------
let fxTimer = null, fxInit = false;
function renderFix(h) {
  const runs = (h.runs || []).filter(r => r.same_sheet);
  const L = h.latest;
  $('#fxRuleAcc').textContent = L ? pct(L.rule_acc) : '–'; $('#fxRuleAcc').classList.toggle('na', !L);
  $('#fxKept').textContent = L && L.normal_kept != null ? pct(L.normal_kept) : '–'; $('#fxKept').classList.toggle('na', !L || L.normal_kept == null);
  $('#fxFail').textContent = L ? String(L.failures) : '–'; $('#fxFail').classList.toggle('na', !L);
  const tbOn = L && L.used_pattern != null;   // 서버가 used_pattern·outside_words 를 주기 시작한 실행만 값이 있음
  $('#fxTbUse').textContent = tbOn ? pct(L.used_pattern) : '측정 예정'; $('#fxTbUse').classList.toggle('na', !tbOn);
  $('#fxOut').textContent = tbOn ? pct(L.outside_words) : '측정 예정'; $('#fxOut').classList.toggle('na', !tbOn);
  $('#fxHint').textContent = L ? `최근 실행 ${when(L.ran_at)} · ${L.backend}:${L.model || ''} · ${L.no_rag ? '검색 없음' : 'RAG (임베딩 ' + (L.embedding || '?') + ')'} · 오류 ${L.n_err}문장 중 정답 규칙 ${L.hit} · 놓침 ${L.missed} · 다른 규칙 ${L.wrong_rule} · 정상 ${L.n_norm}문장 중 오교정 ${L.false_fix} · 평균 ${L.avg_ms ?? '?'}ms`
    : `지금 시험지(${h.sheet?.n ?? '?'}문장)로 돌린 실행이 아직 없어요. 모델을 고르고 [실행]을 눌러 주세요.${h.sheet?.hidden ? ` (다른 시험지 실행 ${h.sheet.hidden}건은 숨김)` : ''}`;
  if (!runs.length) { $('#fixRuns').innerHTML = ''; $('#fixMiss').innerHTML = ''; $('#fxMissHint').textContent = ''; return; }
  const best = Math.max(...runs.filter(r => r.n === (L && L.n)).map(r => r.rule_acc || 0));   // 최고 강조는 최근 실행과 문장 수가 같은 것끼리
  $('#fixRuns').innerHTML = `<colgroup><col style="width:20%"><col style="width:22%"><col style="width:12%"><col style="width:11%"><col style="width:11%"><col style="width:12%"><col style="width:12%"></colgroup>
    <tr><th>실행</th><th>모델</th><th>검색</th><th style="text-align:right" title="오류 문장 중 정답 규칙을 고른 비율">규칙 정답</th><th style="text-align:right" title="정상 문장을 고치지 않은 비율">정상 유지</th><th style="text-align:right" title="고친 문장이 교과서 패턴을 쓴 비율 / 학년 밖 단어가 든 비율 (서버가 주는 실행만)">교과서/밖</th><th style="text-align:right">응답</th></tr>` + runs.map(r => `
    <tr class="${r.n === (L && L.n) && (r.rule_acc || 0) === best ? 'best' : ''}" title="${esc(r.file)} · 놓침 ${r.missed} · 다른 규칙 ${r.wrong_rule} · 오교정 ${r.false_fix} · 실패 ${r.failures}">
      <td>${esc(day(r.ran_at))}<span class="sm">${r.n}문장${r.label ? ' · ' + esc(r.label) : ''}</span></td><td class="m">${esc(r.backend)}:${esc(r.model || '')}</td><td>${r.no_rag ? '없음' : 'RAG'}${r.no_textbook ? '<span class="sm">교과서 없음</span>' : ''}</td>
      <td class="n">${pct(r.rule_acc)}</td><td class="n">${r.normal_kept != null ? pct(r.normal_kept) : '–'}</td><td class="n">${r.used_pattern != null ? pct(r.used_pattern) + ' / ' + pct(r.outside_words) : '–'}</td><td class="n">${r.avg_ms != null ? (r.avg_ms / 1000).toFixed(1) + 's' : '–'}</td></tr>`).join('');
  const miss = h.misses || [];
  if (!miss.length) { $('#fixMiss').innerHTML = ''; $('#fxMissHint').textContent = '틀린 문장 없음'; return; }
  $('#fixMiss').innerHTML = `<colgroup><col style="width:40%"><col style="width:14%"><col style="width:22%"><col style="width:24%"></colgroup><tr><th>문장</th><th>정답</th><th>튜터 판정</th><th>고친 문장</th></tr>` + miss.map(x => `
    <tr><td>${esc(x.text)}</td><td><b>${esc(x.expected)}</b></td><td class="${x.judge && x.judge.startsWith('!') ? 'bad' : ''}">${esc(x.judge || '')}${x.rank ? ` <span style="color:var(--muted)">(검색 ${x.rank}위)</span>` : ''}</td><td>${esc(x.fixed || x.error || '')}</td></tr>`).join('');
  $('#fxMissHint').textContent = `최근 실행에서 틀린 ${miss.length}문장 — "✗ R-xx" = 다른 규칙을 고름, "✗ 놓침" = 오류인데 맞다고 함, "✗ 오교정" = 정상 문장을 고침, "!" = 실패`;
}
async function loadFix() {
  let r = null, h = null;
  try { [r, h] = await Promise.all([api('/api/admin/fix_run'), api('/api/admin/fix_history')]); }
  catch (e) { $('#fxStatus').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> <code>/api/admin/fix_run</code> (backend/evalrun.py)' : '읽기 실패: ' + esc(e.message); $('#fxBtn').disabled = true; return; }
  if (!fxInit) {
    fxInit = true;
    $('#fxBackend').innerHTML = (r.backends || []).map(b => `<option value="${esc(b)}" ${b === r.default_backend ? 'selected' : ''}>${esc(b)}${b === r.default_backend ? ' (.env)' : ''}</option>`).join('');
  }
  const j = r.job || {};
  $('#fxBtn').disabled = !!j.running;
  if (j.running) {
    const pct_ = j.total ? Math.round(j.done / j.total * 100) : 0;
    $('#fxStatus').innerHTML = `⏳ <b>${esc(j.label)}</b> ${j.total ? `${j.done}/${j.total} (${pct_}%)` : '준비 중'} … ${esc((j.log || []).slice(-1)[0] || '')}`;
    if (!fxTimer) fxTimer = setInterval(loadFix, 4000);
  } else {
    if (fxTimer) { clearInterval(fxTimer); fxTimer = null; }
    if (j.error) $('#fxStatus').innerHTML = `<span class="pill warn">실패</span> ${esc(j.label || '')} — ${esc(j.error)}`;
    else if (j.result_file) $('#fxStatus').innerHTML = `완료 <b>${esc(j.label)}</b> · <code>${esc(j.result_file)}</code>`;
    else $('#fxStatus').textContent = '';
  }
  renderFix(h);
}
async function runFix() {
  const backend = $('#fxBackend').value || null, no_rag = $('#fxRag').value === 'norag', sz = $('#fxSize').value, limit = parseInt($('#fxLimit').value) || 0, textbook = $('#fxTb').value !== '0';
  const size = sz === 'all' ? { limit } : { per_rule: parseInt(sz), normal: 20 * parseInt(sz), limit };   // 규칙당 n + 정상 20n, 그 위에 앞 N문장 자르기
  if (backend === 'gemini' && !confirm('Gemini 는 분당 15회 제한이라 360문장에 30분 넘게 걸려요. 계속할까요?')) return;
  $('#fxBtn').disabled = true; $('#fxStatus').textContent = '시작하는 중…';
  try { await api('/api/admin/fix_run', { method: 'POST', body: JSON.stringify({ backend, no_rag, textbook, ...size }) }); }
  catch (e) { $('#fxStatus').innerHTML = '시작 실패: ' + esc(e.message); $('#fxBtn').disabled = false; return; }
  loadFix();
}

// ---------- 교과서 검색 시험 (GET /api/admin/textbook?q=&level=) ----------
async function loadTextbook() {
  let r = null;
  try { r = await api('/api/admin/textbook'); }
  catch (e) { $('#tbStatus').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> <code>/api/admin/textbook</code> (backend/textbook.py)' : '읽기 실패: ' + esc(e.message); $('#tbBtn').disabled = true; return; }
  const m = r.index;
  $('#tbStatus').innerHTML = m ? `색인: 패턴 ${m.patterns} · 단어 ${m.words} · 임베딩 ${esc(m.model || '')} · ${esc(when(m.generated_at))} 생성` : '색인 없음 — <code>python -m backend.textbook --rebuild</code>';
  $('#tbBtn').disabled = !m;
  $('#tbQ').addEventListener('keydown', e => { if (e.key === 'Enter') runTextbook(); });
}
async function runTextbook() {
  const q = $('#tbQ').value.trim(), level = parseInt($('#tbLevel').value) || 3;
  if (!q) return;
  $('#tbBtn').disabled = true; $('#tbTable').innerHTML = '<tr><td>검색 중…</td></tr>';
  let r = null;
  try { r = await api(`/api/admin/textbook?q=${encodeURIComponent(q)}&level=${level}&k=5`); }
  catch (e) { $('#tbTable').innerHTML = `<tr><td class="bad">검색 실패: ${esc(e.message)}</td></tr>`; $('#tbBtn').disabled = false; return; }
  $('#tbBtn').disabled = false;
  const x = r.result || {};
  if (x.error) { $('#tbTable').innerHTML = `<tr><td class="bad">${esc(x.error)}</td></tr>`; hideResult('#tbJudge'); return; }
  if (r.gap != null) showResult('#tbJudge', `${r.hint ? '📖 교과서에 닮은 문장이 있어요 → 힌트로 넣음' : '닮은 문장이 뚜렷하지 않음 → 힌트 안 넣음 (지금 동작 그대로)'} · 1위 <b>${(r.top ?? 0).toFixed(3)}</b> (기준 ${r.top_threshold}) · 1위−5위 차이 <b>${r.gap.toFixed(3)}</b> (기준 ${r.gap_threshold})`, r.hint ? '' : 'todo'); else hideResult('#tbJudge');
  const rows = [...(x.patterns || []).map(p => ({ kind: '패턴', score: p.score, level: p.level, unit: p.unit, text: p.text, sub: `${p.meaning || ''}${p.tip ? ' · ' + p.tip : ''}${p.rule_id ? ' · ' + p.rule_id : ''}` })),
                ...(x.words || []).map(w => ({ kind: '단어', score: w.score, level: w.level, unit: w.unit, text: w.word, sub: `${w.meaning || ''} — ${w.example || ''}` }))];
  const best = { 패턴: Math.max(0, ...(x.patterns || []).map(p => p.score)), 단어: Math.max(0, ...(x.words || []).map(w => w.score)) };
  $('#tbTable').innerHTML = `<colgroup><col style="width:9%"><col style="width:10%"><col style="width:13%"><col style="width:30%"><col style="width:38%"></colgroup>
    <tr><th>종류</th><th style="text-align:right">점수</th><th>학년·유닛</th><th>자료</th><th>뜻 · 팁</th></tr>` + rows.map(o => `
    <tr class="${o.score === best[o.kind] ? 'top' : ''}"><td>${o.kind}</td><td class="n">${o.score.toFixed(3)}</td><td>${o.level}학년 ${esc(o.unit || '')}</td><td>${esc(o.text)}</td><td>${esc(o.sub)}</td></tr>`).join('')
    + `<tr><td colspan="5" style="color:var(--muted)">"${esc(q)}" · ${level}학년까지 · ${x.query_ms}ms · 이 학년까지 교과서 단어 ${r.known_words_n}개 (고친 문장의 단어가 여기 없으면 "학년 밖 단어"로 표시할 예정)</td></tr>`;
}

(async function init() {
  renderTopbar({ crumbs: false });      // 관리자 화면은 학습 위치(Level·Unit)와 무관
  const h = await showHealth();
  await Promise.all([loadGolden(h), loadEval(), loadLog(), loadGen(), loadEvalRun(), loadFix(), loadTextbook()]);
})();
