/* No browser/dependencies: exercise the actual route/loadHome functions with
   deferred API responses. Run: node tests/navigation_unit.js */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'portal.js'), 'utf8');
const routing = source.slice(source.indexOf('  var routeVersion ='), source.indexOf('  function helperNote('));
assert.ok(routing.includes('function route(') && routing.includes('function loadHome('));
let count = 0;
function fixture() {
  const requests = [], calls = [], heading = {
    setAttribute: (name, value) => calls.push(['attr', name, value]),
    focus: options => calls.push(['focus', options.preventScroll])
  };
  const context = {
    Promise, location: { hash: '#/home' }, document: { title: '' },
    window: { scrollTo: (x, y) => calls.push(['scroll', x, y]) },
    main: { querySelector: () => heading, appendChild: () => {}, ...heading },
    S: { me: { user: { role: 'patient' }, patient_name: 'Avery Example' } },
    setNav: () => {}, chrome: () => {}, authFail: () => false,
    h: () => ({ addEventListener: () => {} }),
    PS: {
      api: () => new Promise((resolve, reject) => requests.push({ resolve, reject })),
      clear: () => calls.push(['clear']), errText: e => e.message
    }
  };
  vm.createContext(context);
  vm.runInContext(routing + `
    function renderHome() { return loadHome('Home', function () {}); }
    function renderVisits() { return loadHome('Visits', function () {}); }
    function renderRecords() { return loadHome('Records', function () {}); }
    function renderMessages() {}
    function renderSettings() {}
    function renderIntake() { return loadHome('Intake', function () {}); }
    function renderAssist() {}
    function renderThread() { return loadHome('Thread', function () {}); }
    function renderContent() { return loadHome('Content', function () {}); }
  `, context);
  return { context, requests, calls };
}
function check(name, run) { run(); count++; console.log('PASS ' + name); }
async function main() {
  const f = fixture(), c = f.context;
  const first = c.route(true);
  check('no focus or scroll before asynchronous view completes', () => assert.equal(f.calls.length, 0));
  f.requests.shift().resolve({}); await first;
  check('render completes before focus and own-window top reset', () => assert.deepEqual(f.calls.map(x => x[0]), ['clear', 'attr', 'focus', 'scroll']));
  check('heading focus prevents browser scrolling', () => assert.deepEqual(f.calls[2], ['focus', true]));
  check('both scroll axes reset', () => assert.deepEqual(f.calls[3], ['scroll', 0, 0]));
  f.calls.length = 0;
  const refresh = c.route(); f.requests.shift().resolve({}); await refresh;
  check('same-route retry/refresh does not move focus or scroll', () => assert.deepEqual(f.calls.map(x => x[0]), ['clear']));
  f.calls.length = 0;
  c.location.hash = '#/visits'; const visits = c.route(false);
  c.location.hash = '#/messages'; await c.route(false);
  f.calls.length = 0; f.requests.shift().resolve({}); await visits;
  check('late Home-data response cannot replace or refocus a newer view', () => assert.equal(f.calls.length, 0));
  c.location.hash = '#/home'; const back = c.route(false);
  f.requests.shift().resolve({}); await back;
  check('Back/Forward to an earlier route restores its top', () => assert.deepEqual(f.calls.at(-1), ['scroll', 0, 0]));
  for (const route of ['#/records', '#/intake', '#/messages/1', '#/content/1']) {
    f.calls.length = 0; c.location.hash = route;
    const pending = c.route(false);
    check(route + ' waits for rendering', () => assert.equal(f.calls.length, 0));
    f.requests.shift().resolve({}); await pending;
    check(route + ' resets after rendering', () => assert.deepEqual(f.calls.at(-1), ['scroll', 0, 0]));
  }
  f.calls.length = 0; c.location.hash = '#/visits'; const fail = c.route(false);
  f.requests.shift().reject(new Error('Offline')); await fail;
  check('error view receives navigation reset too', () => assert.deepEqual(f.calls.at(-1), ['scroll', 0, 0]));
  f.calls.length = 0; c.S.me = null; await c.route(false);
  check('signed-out route does not move focus or scroll', () => assert.equal(f.calls.length, 0));
  for (const view of ['Home', 'Visits', 'Records']) {
    check(view + ' returns its real loadHome promise', () => assert.ok(source.includes("return loadHome('" + view + "',")));
  }
  check('assistant answer still deliberately scrolls to its answer', () => assert.ok(source.includes("c.scrollIntoView({ block: 'start', behavior: 'smooth' })")));
  check('intake-step focus and scroll remain intact', () => assert.ok(source.includes("head.scrollIntoView({ block: 'start' })")));
  console.log('DONE navigation_unit: ' + count + '/' + count + ' passed');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
