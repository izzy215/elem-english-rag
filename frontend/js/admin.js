/* 관리자 (PRD 3.7 · docs/plan-B/mockup.html 관리자 웹)
 * 골든 데이터 파일별 개수(/api/admin/golden) · RAG 정확도(/api/rag/eval) · 학생 문장 로그 + 우리 규칙으로 못 짚은 문장(/api/admin/log 의 rows·gaps)
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
    <tr><td class="f">${esc(f.file)}${f.indexed ? ' <span class="pill idx">색인</span>' : ''}</td><td>${esc(f.desc)}</td>
      <td class="n">${f.count == null ? '<span class="pill warn">없음</span>' : (f.indexed ? `<b>${f.count}</b>` : f.count)}</td></tr>`).join('');
  if (!g.index) { $('#indexStatus').innerHTML = '<span class="tag">색인 없음</span> RAG 담당: <code>python -m backend.indexing --rebuild</code>'; return; }
  $('#indexStatus').innerHTML = `검색 색인: 규칙 <b>${g.index.count}</b>개 · 임베딩 ${esc(g.index.model || '')} · ${esc(when(g.index.generated_at))} 생성`
    + (g.index_stale ? ' · <span class="pill warn">rules.jsonl 과 개수가 달라요 — --rebuild 필요</span>' : '');
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
  const runs = r.runs || [];
  const best = Math.max(...runs.map(x => x.hit_at_3 || 0));
  $('#runs').innerHTML = runs.length ? `<div class="d">비교 실험 — 색인 방식 · 임베딩 모델별 hit@3 (RAG 담당이 runs 에 추가)</div>` + runs.map(x => `
    <div class="bar"><span>${esc(x.label)}</span>
      <div class="track"><i class="${x.hit_at_3 === best ? 'best' : ''}" style="width:${Math.round((x.hit_at_3 || 0) * 100)}%"></i></div>
      <span class="v">${pct(x.hit_at_3)}</span></div>`).join('') : '';
  const extra = [r.hit_at_5 != null ? `hit@5 ${pct(r.hit_at_5)} (/fix 가 받는 검색 후보 안 — tutor.py RAG_TOP_K=5 와 같이 바꿀 것)` : '', r.evaluated_at ? `${when(r.evaluated_at)} 측정` : '', r.index?.model ? esc(r.index.model) : ''].filter(Boolean).join(' · ');
  $('#evalHint').innerHTML = (r.hit_at_3 >= .8 ? '목표(80%) 달성' : '목표 80%까지 ' + Math.round((.8 - r.hit_at_3) * 100) + '%p 남음') + (extra ? ' · ' + extra : '');
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
  $('#logDesc').innerHTML = `문장 <b>${r.n}</b>개 · 맞음 ${r.ok_n} · 고침 ${r.n - r.ok_n} · 학생 ${r.students}명${llm ? ` · 처리 모델: ${llm}` : ''}`;
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

(async function init() {
  renderTopbar({ crumbs: false });      // 관리자 화면은 학습 위치(Level·Unit)와 무관
  const h = await showHealth();
  await Promise.all([loadGolden(h), loadEval(), loadLog(), loadGen()]);
})();
