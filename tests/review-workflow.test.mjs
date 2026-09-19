import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

// Execute the actual inline script. No GitHub requests are sent by these tests.
const workflow = readFileSync(new URL('../.github/workflows/request-codex-review.yml', import.meta.url), 'utf8');
const match = workflow.match(/^          script: \|\n((?: {12}[^\n]*\n|\n)*)/m);
assert.ok(match, 'Expected the workflow inline script');
const source = match[1].replace(/^ {12}/gm, '');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFunction('github', 'context', 'core', source);
const sha = 'a'.repeat(40);
const marker = '<!-- problemforger-codex-review-request -->';
const context = { repo: { owner: 'fixture', repo: 'fixture' }, payload: { pull_request: { number: 22, head: { sha } } } };

function comment(login, type, body = `${marker}\n${sha}`) {
  return { user: { login, type }, body };
}

async function invoke(comments, { listError, createError } = {}) {
  const created = [];
  const listComments = () => {};
  const github = {
    paginate: async (method, args) => {
      assert.equal(method, listComments);
      assert.deepEqual(args, { owner: 'fixture', repo: 'fixture', issue_number: 22, per_page: 100 });
      if (listError) throw listError;
      return comments;
    },
    rest: { issues: {
      listComments,
      createComment: async (args) => {
        if (createError) throw createError;
        created.push(args);
      },
    } },
  };
  await run(github, context, { info() {} });
  return created;
}

for (const [name, comments, expected] of [
  ['first request', [], 1],
  ['human cannot spoof marker', [comment('contributor', 'User')], 1],
  ['another bot cannot spoof marker', [comment('other[bot]', 'Bot')], 1],
  ['trusted same-head request is deduplicated', [comment('github-actions[bot]', 'Bot')], 0],
  ['previous head does not suppress new head', [comment('github-actions[bot]', 'Bot', `${marker}\n${'b'.repeat(40)}`)], 1],
  ['SHA alone is not a marker', [comment('github-actions[bot]', 'Bot', sha)], 1],
  ['missing author or body is harmless', [{}, { user: { type: 'Bot', login: 'github-actions[bot]' } }], 1],
]) {
  test(name, async () => {
    const created = await invoke(comments);
    assert.equal(created.length, expected);
    if (expected) {
      assert.equal(created[0].body, `${marker}\n@codex review\n\nRequested automatically for head \`${sha}\`.`);
      assert.equal(created[0].issue_number, 22);
    }
  });
}

test('list failure is surfaced instead of posting a duplicate', async () => {
  const error = new Error('list failed');
  await assert.rejects(invoke([], { listError: error }), (actual) => actual === error);
});

test('comment failure is surfaced for a workflow retry', async () => {
  const error = new Error('create failed');
  await assert.rejects(invoke([], { createError: error }), (actual) => actual === error);
});
