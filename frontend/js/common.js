/* 공통: API 호출 · 화면 간 상태(sessionStorage) · 상단바 · 헬퍼
 * 모든 화면 HTML 이 이 파일을 먼저 읽고, 그다음 자기 화면 js 를 읽는다.
 */

// ---------- API ----------
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    const e = new Error(msg); e.status = r.status; throw e;
  }
  return r.json();
}
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const shuffle = a => a.sort(() => Math.random() - .5);

// ---------- 화면 간 상태 ----------
// 학생 · Level · Unit · 단어/문장 · 문제 결과를 sessionStorage 에 두고 화면이 바뀌어도 이어 쓴다.
const S = {
  get() { try { return JSON.parse(sessionStorage.getItem('echo') || '{}'); } catch (_) { return {}; } },
  set(patch) { const s = { ...S.get(), ...patch }; sessionStorage.setItem('echo', JSON.stringify(s)); return s; },
  clear() { sessionStorage.removeItem('echo'); },
};
function go(page) { location.href = page; }

// 이 화면에 꼭 필요한 상태가 없으면 시작 화면으로 (주소를 직접 쳤을 때 대비)
function requireState(...keys) {
  const s = S.get();
  for (const k of keys) if (s[k] == null) { go('index.html'); return null; }
  return s;
}

// ---------- 상단바 ----------
function renderTopbar({ back = true, crumbs = true } = {}) {
  const s = S.get();
  const parts = [];
  if (crumbs && s.level) parts.push(`Level ${s.level.level}`);
  if (crumbs && s.unit) parts.push(`${s.unit.unit} ${s.unit.title}`);
  $('#topbar').innerHTML = `
    ${back ? '<button class="back" onclick="history.back()">‹ 뒤로</button>' : ''}
    <div class="crumb">${parts.map(p => `<span>${esc(p)}</span>`).join('')}</div>
    <div class="student">학생 ${esc(s.student || 'A')}</div>`;
}

// ---------- 하단 상태줄 ----------
async function showHealth() {
  const el = $('#status'); if (!el) return;
  try {
    const h = await api('/api/health');
    el.textContent = h.using_sample
      ? '임시 샘플 데이터(20단어)로 동작 중 · 골든 데이터 납품 후 자동 전환'
      : `골든 데이터 ${h.golden_files.join(', ')}`;
    if (!h.api_key) { el.textContent += ' · ⚠ GEMINI_API_KEY 없음'; el.classList.add('warn'); }
    return h;
  } catch (e) {
    el.textContent = '서버 연결 실패: python -m uvicorn backend.main:app --app-dir project --reload --port 8000';
    el.classList.add('warn');
    return null;
  }
}

// ---------- 결과 박스 (학습 · 문제 화면 공용) ----------
function showResult(sel, html, kind = '') { const el = $(sel); el.className = 'result on ' + kind; el.innerHTML = html; }
function hideResult(sel) { const el = $(sel); if (el) el.className = 'result'; }
