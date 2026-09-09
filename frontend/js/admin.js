/* 관리자 (PRD 3.7 · docs/plan-B/mockup.html 관리자 웹)
 * 골든 데이터 파일별 개수(/api/admin/golden) · RAG 정확도(/api/rag/eval) · 학생 문장 로그(/api/admin/log)
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
  const extra = [r.hit_at_5 != null ? `hit@5 ${pct(r.hit_at_5)} (/fix 가 받는 후보 5개 안)` : '', r.evaluated_at ? `${when(r.evaluated_at)} 측정` : '', r.index?.model ? esc(r.index.model) : ''].filter(Boolean).join(' · ');
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
}

(async function init() {
  renderTopbar({ crumbs: false });      // 관리자 화면은 학습 위치(Level·Unit)와 무관
  const h = await showHealth();
  await Promise.all([loadGolden(h), loadEval(), loadLog()]);
})();
