/* 4.1 시작 — 학생 선택 · Level 선택 → units.html */

function setStudent(v) { S.set({ student: v }); renderTopbar({ back: false }); }

async function loadLevels() {
  const levels = await api('/api/levels');
  $('#levelCards').innerHTML = levels.map(l => `
    <button class="card level" onclick='pickLevel(${JSON.stringify(l)})'>
      <div class="num">${l.level}</div>
      <div class="t">${esc(l.label)}</div>
      <div class="d">${l.units ? `Unit ${l.units}개` : '준비 중'}</div>
    </button>`).join('');
}

function pickLevel(level) {
  S.set({ level, unit: null, words: null, sentences: null, quizResult: null });
  go('units.html');
}

(async function init() {
  const s = S.get();
  if (!s.student) S.set({ student: 'A' });
  $('#studentSel').value = S.get().student;
  renderTopbar({ back: false });
  if (await showHealth()) await loadLevels();
})();
