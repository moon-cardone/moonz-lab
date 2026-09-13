'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const core = html.match(/<script id="score-core">([\s\S]*?)<\/script>/);
assert.ok(core, '실제 HTML의 채점 함수를 찾을 수 있어야 합니다.');
const score = vm.runInNewContext(core[1] + '\nscoreAnswers;');
assert.equal(score(['b', 'c', 'a']).score, 3);
assert.equal(score(['a', 'b', 'c']).score, 0);
assert.equal(score(['b', 'b', 'a']).score, 2);
for (const blank of [null, undefined, '']) {
  const result = score(['b', blank, 'a']);
  assert.equal(result.complete, false);
  assert.equal(result.score, null, '미선택 답을 오답으로 채점하지 않습니다.');
  assert.equal(JSON.stringify(result.missing), '[1]');
}
assert.equal(score([null, null, null]).missing.length, 3);
assert.equal(score(new Array(3)).missing.length, 3);
assert.throws(() => score(['b', 'c']));
assert.throws(() => score(['b', 'd', 'a']));
assert.throws(() => score('bca'));
assert.equal((html.match(/<fieldset /g) || []).length, 3);
assert.equal((html.match(/type="radio"/g) || []).length, 9);
assert.ok(html.includes('aria-live="polite"'));
console.log('PASS: correct, wrong, partial, unanswered, invalid input, and accessible form structure.');
