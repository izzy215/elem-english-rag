/* 시작 — 학생 선택 · Level · 오답노트 버튼 */
async function refreshHero() {
  const st = S.get().student; $('#heroName').textContent = st;
  const nb = await fetchNotebook(st);
  const spoken = nb.stats ? nb.stats.spoken : Object.keys(localStorage).filter(k => k.startsWith(`spoken_${st}_`)).length;   // 서버 /notebook 이 주면 서버 수치
  $('#heroStat').innerHTML = `<span>🗣 말한 문장 ${spoken}</span><span>📒 헷갈리는 규칙 ${nb.active.length}</span><span>🌳 극복 ${nb.overcome.length}</span>`;
  $('#noteBtn').textContent = `📒 내 오답노트${nb.active.length ? ` (${nb.active.length})` : ''}`;
}
function setStudent(v) { S.set({ student: v }); renderTopbar({ back: false }); refreshHero(); }
async function loadLevels() {
  const levels = await api('/api/levels');
  $('#levelCards').innerHTML = levels.map(l => `<button class="card level" ${l.units ? '' : 'disabled'} onclick='pickLevel(${JSON.stringify(l)})'><div class="num">${l.level}</div><div class="t">${esc(l.label)}</div><div class="d">${l.units ? `미션 ${l.units}개` : '준비 중'}</div></button>`).join('');
}
function pickLevel(level) { S.set({ level, unit: null, words: null, patterns: null, lastFix: null }); go('units.html'); }
(async function init() {
  if (!S.get().student) S.set({ student: 'A' });
  $('#studentSel').value = S.get().student; renderTopbar({ back: false });
  if (await showHealth()) await loadLevels();
  refreshHero();
})();
