/* 관리자 (admin.html) — 운영하는 사람이 보는 것: 서비스 상태 · 골든 데이터(/api/admin/golden) · 학생 문장 로그(/api/admin/log) · 학생별 현황(/api/notebook) · 데이터팀 안건(log 의 gaps)
 * 9/17 평가·실험 패널은 lab.html/lab.js 로 분리. 서버에 아직 없는 API(404)면 그 패널만 "서버 재시작 필요" 로 두고 나머지는 그린다. */
const pct = v => v == null ? '–' : Math.round(v * 100) + '%';
const when = iso => iso ? iso.slice(5, 16).replace('T', ' ') : '';

// ---------- 서비스 상태 (GET /api/admin/status + /api/admin/log 의 처리 모델·응답 시간) — 대시보드 타일 ----------
async function loadStatus(health) {
  const tile = (k, v, s = '', cls = '') => `<div class="it ${cls}"><div class="k">${k}</div><div class="v${v == null ? ' na' : ''}">${v == null ? '–' : v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
  if (!health) { $('#svcStat').innerHTML = tile('서버', '<span class="pill warn">연결 실패</span>'); return; }
  let st = null, log = null;
  await Promise.all([api('/api/admin/status').then(x => st = x).catch(() => {}), api('/api/admin/log?days=7').then(x => log = x).catch(() => {})]);
  if (!st) { $('#svcStat').innerHTML = tile('상태', '<span class="tag">서버 재시작 필요</span>', '<code>/api/admin/status</code> (backend/admin.py) 가 뜨면 나와요'); return; }
  const L = st.llm, E = st.embedding, S = st.stt, ix = st.indexes || {};
  const where = url => url ? esc(url.replace(/^https?:\/\//, '').replace(/\/v1$/, '')) : '';
  const short = m => esc((m || '').replace(/^intfloat\//, ''));
  const usage = log && log.llm ? Object.entries(log.llm).sort((a, b) => b[1] - a[1]) : [];
  const total = usage.reduce((a, [, n]) => a + n, 0);
  const idxName = { rules: '규칙 설명문', examples: '틀린 예문', textbook: '교과서', faq: 'FAQ', rulealias: '규칙 별칭' };
  const idxRows = Object.entries(idxName).map(([k, n]) => `<span>${n}</span><b>${ix[k] ? ix[k].count : '–'}</b><span class="p"></span><span class="m">${ix[k] ? esc(when(ix[k].generated_at)) + (ix[k].model && ix[k].model !== E.model ? ' · <span class="pill warn">임베딩 다름</span>' : '') : '<span class="pill warn">없음</span>'}</span>`).join('');
  const useRows = usage.map(([k, n]) => `<span>${esc(k)}</span><b>${n}</b><span class="p">${Math.round(n / total * 100)}%</span><span class="m">${esc((L.backends && L.backends[k]) || '')}</span>`).join('');
  $('#svcStat').innerHTML =
    tile('답변 모델', esc(L.model || L.backend), `${esc(L.backend)} · ${where(L.url) || esc(L.url)} · 제한 ${L.timeout_s}초`)
    + tile('대체 모델', L.fallback ? esc(L.fallback.split(' · ').pop()) : null, L.fallback ? '답변 모델이 실패하면 (LLM_FALLBACK=1)' : '없음 (LLM_FALLBACK=0)')
    + tile('임베딩 (검색)', short(E.model), E.provider === 'remote-http' ? `교실 서버 · ${where(E.url)}` : E.provider === 'sentence-transformers-local' ? '이 PC 에서 실행' : 'Google API')
    + tile('음성 인식', `Whisper ${esc(S.whisper_model)}`, `${S.whisper_url ? '교실 서버 · ' + where(S.whisper_url) : '이 PC'}${S.backend === 'gemini' ? ' · 한/영 자동 감지' : ''}`)
    + tile('데이터', st.data.using_sample ? '<span class="pill warn">임시 샘플</span>' : '<span class="pill ok">골든</span>', `<code>${esc(st.data.dir)}/</code>`)
    + tile('검색 색인 ' + (st.index_stale ? '<span class="pill warn">rules 와 개수 다름 — --rebuild</span>' : ''), `<div class="rows">${idxRows}</div>`, `임베딩 ${short((ix.rules || {}).model || E.model)} 로 만든 색인 5개`, 'wide')
    + tile('최근 7일 답한 모델', usage.length ? `<div class="rows">${useRows}</div>` : null, log && log.timing ? `평균 응답 <b>${(log.timing.total_ms / 1000).toFixed(1)}초</b> · 검색 ${(log.timing.search_ms / 1000).toFixed(1)}초 · 모델 호출 ${log.timing.llm_calls}회 · ${log.timing.n}문장` : '기록 없음', 'wide');
  $('#svcHint').innerHTML = '모델·임베딩·주소는 <code>.env</code> (바꾸면 서버 재시작), 색인은 <code>python -m backend.indexing --rebuild</code> / <code>backend.textbook --rebuild-*</code>. 평가·실험은 <a href="lab.html">실험실</a>.';
}

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


// ---------- 학생별 현황 (GET /api/notebook?student=) ----------
async function loadStudents() {
  const ids = ['A', 'B'];   // 시작 화면의 학생 선택과 같은 목록
  const rows = [];
  for (const st of ids) {
    try { const nb = await api(`/api/notebook?student=${encodeURIComponent(st)}`); rows.push({ st, nb }); }
    catch (e) { rows.push({ st, err: e.status === 404 ? '서버 재시작 필요' : (e.message || '읽기 실패') }); }
  }
  $('#stuTable').innerHTML = `<tr><th>학생</th><th style="text-align:right">말한 문장</th><th style="text-align:right">헷갈리는 규칙</th><th style="text-align:right">극복</th><th>가장 자주 걸린 규칙</th><th>유닛</th></tr>` + rows.map(({ st, nb, err }) => {
    if (err) return `<tr><td>학생 ${esc(st)}</td><td colspan="5" class="empty">${esc(err)}</td></tr>`;
    const top = (nb.active || []).slice(0, 3).map(a => `${esc(a.name)} <span style="color:var(--muted);font-size:.75rem">${a.count}회</span>`).join(' · ') || '<span style="color:var(--muted)">없음</span>';
    const units = Object.entries((nb.stats || {}).by_unit || {}).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([u, n]) => `${esc(u)} ${n}`).join(' · ');
    return `<tr><td>학생 ${esc(st)}</td><td class="n"><b>${(nb.stats || {}).spoken ?? 0}</b></td><td class="n">${(nb.active || []).length}</td><td class="n">${(nb.overcome || []).length}</td><td>${top}</td><td style="color:var(--muted);font-size:.8rem">${units}</td></tr>`;
  }).join('');
  $('#stuHint').textContent = '극복 = 오답노트 연습 문제를 연속 2번 다 맞힌 규칙 · 학생 GEN(생성 점검용)은 제외';
}

// ---------- 주간 리포트 (BigQuery) — /api/admin/report. source=bq 면 파일 집계와 행 수가 맞는지(check) 같이 보여 준다 ----------
async function loadReport() {
  const days = $('#rpDays').value;
  let r = null;
  try { r = await api(`/api/admin/report?days=${days}`); }
  catch (e) {
    ['#rpKpis', '#rpReport', '#rpRules', '#rpDaysTbl', '#rpStudents'].forEach(q => $(q).innerHTML = '');
    $('#rpHint').innerHTML = e.status === 404 ? '<span class="tag">서버 재시작 필요</span> <code>/api/admin/report</code> (backend/report.py) 가 뜨면 나와요.' : '리포트 읽기 실패: ' + esc(e.message || e);
    return;
  }
  const src = r.source === 'bq' ? `<b>BigQuery</b> ${esc(r.bq.project)} · ${esc(r.bq.table)} (${esc(r.bq.location)})` : '<b>서버 파일</b> 집계 (BigQuery 설정 전 — .env 에 BQ_PROJECT 넣고 tests/bq_upload.py 로 올리면 SQL 로 바뀜)';
  const chk = r.check && r.check.bq_n != null ? ` · 파일 ${r.check.file_n}행 vs BigQuery ${r.check.bq_n}행 ${r.check.match && r.check.rules_match ? '<span class="tag">일치</span>' : '<span class="tag" style="background:var(--danger-soft);color:var(--danger)">불일치 — bq_upload 다시</span>'}` : '';
  $('#rpDesc').innerHTML = `${src}${chk}`;
  const okN = r.days.reduce((a, d) => a + d.ok_n, 0);
  $('#rpKpis').innerHTML = `<div class="kpi"><div class="num">${r.n}</div><div class="lbl">말한 문장 (학생 전체)</div></div>
    <div class="kpi"><div class="num">${r.n ? Math.round(okN / r.n * 100) : '–'}<small>%</small></div><div class="lbl">바로 맞은 비율</div></div>
    <div class="kpi"><div class="num">${r.rules.length}</div><div class="lbl">걸린 규칙 종류</div></div>
    <div class="kpi"><div class="num">${r.students.length}</div><div class="lbl">학생</div></div>`;
  const rp = r.report;
  $('#rpReport').innerHTML = !rp ? '' : rp.sentences.length
    ? `<div class="rp-letter">${rp.sentences.map(s => `<p>${esc(s.text)}</p>`).join('')}<div class="by">— ${esc((rp.llm || {}).model || '모델')} 이 위 표만 보고 씀${rp.dropped.length ? ` · 표에 없는 숫자를 써서 버린 문장 ${rp.dropped.length}개 (${rp.dropped.map(d => d.bad_numbers.join(',')).join(' / ')})` : ''}</div></div>`
    : `<div class="rp-letter empty">${esc(rp.note || '리포트 문장 없음')}${rp.dropped && rp.dropped.length ? ` · 버린 문장 ${rp.dropped.length}개` : ''}</div>`;
  $('#rpRules').innerHTML = r.rules.length ? `<tr><th>규칙</th><th style="text-align:right">횟수</th><th style="text-align:right">학생</th></tr>` + r.rules.slice(0, 10).map((x, i) =>
    `<tr><td>${esc(x.name)} <span style="color:var(--muted);font-size:.75rem">${esc(x.rule_id)}</span></td><td class="n">${i === 0 ? `<b>${x.count}</b>` : x.count}</td><td class="n">${x.students}</td></tr>`).join('') : '';
  $('#rpDaysTbl').innerHTML = r.days.length ? `<tr><th>날짜</th><th style="text-align:right">문장</th><th style="text-align:right">바로 맞음</th></tr>` + r.days.map(d =>
    `<tr><td>${esc(d.day)}</td><td class="n">${d.n}</td><td class="n">${d.ok_n} <span style="color:var(--muted);font-size:.75rem">${Math.round(d.ok_rate * 100)}%</span></td></tr>`).join('') : '';
  $('#rpStudents').innerHTML = r.students.length ? `<tr><th style="width:90px">학생</th><th>상위 3 규칙</th></tr>` + r.students.map(s =>
    `<tr><td>학생 ${esc(s.student)}</td><td>${s.top.map(t => `${esc(t.name)} <span style="color:var(--muted);font-size:.75rem">${t.count}회</span>`).join(' · ')}</td></tr>`).join('') : '';
  $('#rpHint').textContent = r.n ? 'SQL 3개: 규칙별 횟수·학생 수 / 일별 문장 수·맞음 비율 / 학생별 상위 3 규칙 — 위 "학생 문장 로그" 표와 같은 정의' : '이 기간에 문장이 없어요.';
}

(async function init() {
  renderTopbar({ crumbs: false, backTo: 'index.html' });      // 관리자 화면은 학습 위치(Level·Unit)와 무관 · '뒤로'는 홈으로
  const h = await showHealth();
  await Promise.all([loadStatus(h), loadGolden(h), loadLog(), loadStudents(), loadReport()]);
})();
