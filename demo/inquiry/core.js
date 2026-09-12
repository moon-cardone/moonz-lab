/* 공유 처리 로직. 브라우저와 Code.gs에 같은 파일을 사용합니다. */
var Inquiry = (function () {
  'use strict';
  const headers = ['문의ID', '접수일시', '고객명', '중복키', '유입경로', '중복여부', '원본문의ID', '담당자', '처리상태', '자동처리시각'];
  const owners = ['담당A', '담당B'];
  const statuses = ['신규', '연락중', '완료'];
  const keyOf = value => value.trim().toUpperCase();
  function validDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$/.test(value)) return false;
    const normalized = value.length === 10 ? value + ' 00:00:00' : value;
    const date = new Date(normalized.replace(' ', 'T') + 'Z');
    return !isNaN(date.getTime()) && date.toISOString().slice(0, 19).replace('T', ' ') === normalized;
  }
  function process(rows, now) {
    if (!Array.isArray(rows) || !validDate(now)) throw new Error('행 배열 또는 처리시각이 올바르지 않습니다.');
    const next = rows.map(row => Array.isArray(row) ? row.slice() : row);
    const ids = new Map(), originals = new Map();
    let assigned = 0;
    function fail(index, message) { throw new Error((index + 2) + '행: ' + message); }
    // 모든 입력을 먼저 검사합니다. 한 행의 오류도 쓰기 전에 발견합니다.
    next.forEach((row, index) => {
      if (!Array.isArray(row) || row.length !== 10 || row.some(v => typeof v !== 'string')) fail(index, 'A:J의 10개 값을 텍스트/날짜로 확인하세요.');
      if (row.every(v => v === '')) return;
      if (row.slice(0, 5).some(v => !v.trim())) fail(index, 'A:E 필수값이 비어 있습니다.');
      if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/.test(row[0])) fail(index, '문의ID는 영문·숫자·밑줄·하이픈 40자 이내여야 합니다.');
      if (ids.has(row[0])) fail(index, '문의ID가 다른 행과 같습니다. 고유 ID를 사용하세요.');
      ids.set(row[0], row);
      if (!validDate(row[1])) fail(index, '접수일시는 YYYY-MM-DD 또는 YYYY-MM-DD HH:mm:ss 형식이어야 합니다.');
      if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(row[3].trim())) fail(index, '중복키는 영문·숫자·밑줄·하이픈 64자 이내여야 합니다.');
      if ([row[2], row[4]].some(v => v.length > 80 || /[\u0000-\u001f\u007f]/.test(v))) fail(index, '고객명·유입경로는 제어문자 없는 80자 이내 텍스트여야 합니다.');
      if (!row[9]) {
        if (row.slice(5, 9).some(v => v !== '')) fail(index, 'F:I에 부분 결과가 있습니다. 원인을 확인하세요. 자동으로 덮어쓰지 않습니다.');
        return;
      }
      if (!validDate(row[9]) || !statuses.includes(row[8])) fail(index, '기존 처리시각 또는 처리상태가 올바르지 않습니다.');
      if (row[5] === '원본' && row[6] === '' && owners.includes(row[7])) {
        const key = keyOf(row[3]);
        if (originals.has(key)) fail(index, '같은 중복키에 원본이 두 개 있습니다. 기존 결과를 확인하세요.');
        originals.set(key, row[0]);
        assigned++;
      } else if (row[5] !== '중복' || !row[6] || row[7] !== '') {
        fail(index, '기존 자동 결과 F:J가 올바르지 않습니다.');
      }
    });
    next.forEach((row, index) => {
      if (row[9] && row[5] === '중복' && originals.get(keyOf(row[3])) !== row[6]) fail(index, '중복 행이 가리키는 원본을 찾을 수 없습니다.');
    });
    const changes = [];
    next.forEach((row, index) => {
      if (row.every(v => v === '') || row[9]) return;
      const key = keyOf(row[3]), original = originals.get(key);
      row[5] = original ? '중복' : '원본';
      row[6] = original || '';
      row[7] = original ? '' : owners[assigned++ % owners.length];
      row[8] = '신규';
      row[9] = now;
      if (!original) originals.set(key, row[0]);
      changes.push(index);
    });
    return { rows: next, changes };
  }
  function summary(rows, day) {
    const today = rows.filter(row => row[1].slice(0, 10) === day);
    const unique = today.filter(row => row[5] === '원본');
    return { total: today.length, unique: unique.length, duplicates: today.filter(row => row[5] === '중복').length,
      pending: unique.filter(row => row[8] !== '완료').length, done: unique.filter(row => row[8] === '완료').length };
  }
  function safeCell(value) {
    const text = String(value);
    return /^[\s]*[=+\-@]/.test(text) ? "'" + text : text;
  }
  return { headers, owners, statuses, process, summary, safeCell, validDate };
}());
if (typeof module !== 'undefined' && module.exports) module.exports = Inquiry;
