const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const util = require('node:util');
const ts = require('typescript');

function moduleFrom(file, overrides = {}) {
  const source = fs.readFileSync(path.resolve(file), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', code)(name => name in overrides ? overrides[name] : require(name), module, module.exports);
  return module.exports;
}
const areas = moduleFrom('lib/areas.ts');
const catalog = [{ id: 'sync_sample_db', name: '검증용', urls: ['https://example.com'],
  cafe_ids: ['a', 'b', 'new'], cafes: [{ cafe_id: 'new', name: '새 카페', address: '전북특별자치도 전주시' }],
  selections: { BRANCH_MAP: { 1: ['a'], 2: ['b'] } } }];
const earlier = { script: 'sync_sample_db', checked_at: '2026-11-14T10:00:00+09:00', status: 'smoke_pass', scope: 'all configured branches / today', slots: 8 };
const recent = { script: 'sync_sample_db', checked_at: '2026-11-14T11:00:00+09:00', status: 'needs_review', scope: 'first configured branch / today', selected: { BRANCH_MAP: ['1'] }, slots: 0 };

function server({ unavailable = false, directory = [], readFailure = null, onGetDb = () => {} } = {}) {
  const snapshots = [{ id: 'a', data: () => ({ name: '부산 카페', area: 'etc', address: '부산 부산진구', is_active: true, supported_area: false }) },
    { id: 'b', data: () => ({ name: '서울 카페', area: 'konkuk', address: '서울 광진구', is_active: true }) }];
  const exec = () => {};
  exec[util.promisify.custom] = async () => ({ stdout: JSON.stringify(catalog) });
  const database = {
    collection(name) {
      const collection = {
        where() { return collection; },
        async get() { if (readFailure) throw readFailure; return { docs: name === 'cafes' ? snapshots : [
          { id: 'ta', data: () => ({ cafe_id: 'a', name: '부산 테마' }) },
          { id: 'tb', data: () => ({ cafe_id: 'b', name: '서울 테마' }) },
        ] }; },
        doc() { return { get: async () => ({ data: () => ({ cafes: { a: { crawled_at: '2026-11-14 09:30:00', themes: { ta: { slots: [{ time: '14:00', status: 'available' }] } } } } }) }) }; },
      };
      return collection;
    },
  };
  return moduleFrom('lib/crawler-dashboard-server.ts', {
    'node:child_process': { execFile: exec },
    'node:fs/promises': {
      readdir: async () => [{ name: 'checks.json', isDirectory: () => false, isFile: () => true }],
      readFile: async file => JSON.stringify(String(file).endsWith("cafe-directory.json") ? { cafes: directory } : [earlier, recent]),
    },
    '@/lib/firestore-server': { getDb: () => { onGetDb(); if (unavailable) throw new Error('offline'); return database; } },
    '@/lib/areas': areas,
    '@/lib/supabase-server': { usesSupabase: () => false },
  });
}

test('지점별 과거 검증을 다른 지점의 최신 실행으로 덮어쓰지 않는다', async () => {
  const data = await server().getDashboardData('2026-11-14', false);
  assert.equal(data.runs[0].latest.checked_at, recent.checked_at);
  assert.equal(data.cafes.find(c => c.id === 'a').check.checked_at, recent.checked_at);
  assert.equal(data.cafes.find(c => c.id === 'b').check.checked_at, earlier.checked_at);
  assert.equal(data.cafes.find(c => c.id === 'b').checkInScope, true);
});

test('저장 수치와 테스트 수치를 구분하고 과거 supported_area=false도 포함한다', async () => {
  const data = await server().getDashboardData('2026-11-14', false);
  const cafe = data.cafes.find(c => c.id === 'a');
  assert.equal(cafe.area, 'busan');
  assert.equal(cafe.themeCount, 1);
  assert.equal(cafe.slotCount, 1);
  assert.equal(cafe.available, 1);
  assert.equal(cafe.check.slots, 0);
  assert.equal(cafe.testSlotCount, 0);
  assert.equal(cafe.testThemeCount, 0);
  assert.equal(data.cafes.find(c => c.id === 'b').testSlotCount, null);
  assert.equal(cafe.crawledAt, '2026-11-14T09:30:00+09:00');
  const missing = data.cafes.find(c => c.id === 'new');
  assert.equal(missing.inDatabase, false);
  assert.equal(missing.area, 'jeonbuk');
});

test('DB 조회 실패를 0개로 위장하지 않고 미확인 값과 안내를 반환한다', async () => {
  const data = await server({ unavailable: true }).getDashboardData('2026-11-14', false);
  assert.equal(data.dataFetchedAt, null);
  assert.equal(data.cafes[0].inDatabase, null);
  assert.equal(data.cafes[0].slotCount, null);
  assert.equal(data.cafes[0].themeCount, null);
  assert.ok(data.warnings.some(w => w.includes('Firestore')));
});

function route() {
  return moduleFrom('lib/dev-crawlers-route.ts', {
    '@/lib/crawler-dashboard-server': { getDashboardData: async () => ({ runs: [{ id: 'sync_sample_db' }] }) },
    '@/lib/crawler-dashboard-jobs': { getCrawlerJob: () => null, startCrawlerJob: (script, allBranches) => ({ script, allBranches, status: 'running' }) },
  });
}
const { NextRequest } = require('next/server');
function request(body, origin = 'http://localhost:3000') {
  return new NextRequest('http://0.0.0.0:3000/api/dev/crawlers', { method: 'POST', headers: { host: 'localhost:3000', origin, 'content-type': 'application/json' }, body: JSON.stringify(body) });
}

test('0.0.0.0 개발 서버에서도 실제 Host와 같은 출처의 검증을 허용한다', async () => {
  const previous = process.env.NODE_ENV; process.env.NODE_ENV = 'development';
  try {
    const response = await route().POST(request({ script: 'sync_sample_db' }));
    assert.equal(response.status, 202);
    assert.equal((await response.json()).job.script, 'sync_sample_db');
  } finally { process.env.NODE_ENV = previous; }
});

test('다른 사이트 출처 및 등록되지 않은 실행 대상을 거부한다', async () => {
  const previous = process.env.NODE_ENV; process.env.NODE_ENV = 'development';
  try {
    assert.equal((await route().POST(request({ script: 'sync_sample_db' }, 'https://elsewhere.example'))).status, 403);
    assert.equal((await route().POST(request({ script: '../../invalid' }))).status, 400);
    assert.equal((await route().GET(new NextRequest('http://localhost:3000/api/dev/crawlers?date=2026-02-31'))).status, 400);
  } finally { process.env.NODE_ENV = previous; }
});

test('운영 빌드에서는 조회와 실행 API 모두 노출하지 않는다', async () => {
  const previous = process.env.NODE_ENV; process.env.NODE_ENV = 'production';
  try {
    assert.equal((await route().GET(new NextRequest('http://localhost:3000/api/dev/crawlers'))).status, 404);
    assert.equal((await route().POST(request({ script: 'sync_sample_db' }))).status, 404);
  } finally { process.env.NODE_ENV = previous; }
});


test('로그인 설정이 비어 있어도 현황판 렌더링에 필요한 모듈을 로드한다', () => {
  const previous = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  delete process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  try {
    const firebase = moduleFrom('lib/firebase.ts', {
      'firebase/app': { getApps: () => [], initializeApp: () => { throw new Error('초기화하면 안 됨'); } },
      'firebase/auth': { getAuth: () => { throw new Error('인증 초기화하면 안 됨'); }, GoogleAuthProvider: class {} },
    });
    assert.equal(firebase.auth, null);
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
    else process.env.NEXT_PUBLIC_FIREBASE_API_KEY = previous;
  }
});


test('실행 범위가 없는 실패 기록을 모든 지점 오류로 전파하지 않는다', async () => {
  const saved={...recent};
  Object.assign(recent,{scope:'실행 실패 / 범위 미확인',selected:undefined,status:'timeout'});
  try {
    const data=await server().getDashboardData('2026-11-14',false);
    assert.equal(data.cafes.find(c=>c.id==='b').check.checked_at,earlier.checked_at);
    assert.equal(data.cafes.find(c=>c.id==='b').check.status,'smoke_pass');
  } finally {for(const k of Object.keys(recent))delete recent[k];Object.assign(recent,saved);}
});

test('쓰기 전에 실패한 지점 단독 실행도 요청한 지점에만 표시한다', async () => {
  const saved={...recent};
  Object.assign(recent,{requested_cafe_ids:['a'],per_cafe:{},selected:undefined,status:'error'});
  try {
    const data=await server().getDashboardData('2026-11-14',false);
    assert.equal(data.cafes.find(c=>c.id==='a').check.status,'error');
    assert.equal(data.cafes.find(c=>c.id==='b').check.status,'smoke_pass');
  } finally {for(const k of Object.keys(recent))delete recent[k];Object.assign(recent,saved);}
});


test('DB 장애에도 카페 기본정보와 미연결 지점은 유지하고 예약 수치는 미확인으로 둔다', async () => {
  const directory = [
    { id: 'a', name: '룸익스케이프', branch_name: '화이트점', address: '서울 서대문구 명물길 66', area: 'hongdae', is_active: true },
    { id: 'unlinked', name: '부산 미연결 카페', address: '부산 부산진구 중앙대로 1', area: 'etc', is_active: false },
  ];
  const data = await server({ unavailable: true, directory }).getDashboardData('2026-11-15', true);
  const cafe = data.cafes.find(c => c.id === 'a');
  assert.equal(cafe.name, '룸익스케이프');
  assert.equal(cafe.address, '서울 서대문구 명물길 66');
  assert.equal(cafe.area, 'sinchon');
  assert.equal(cafe.slotCount, null);
  assert.equal(cafe.inDatabase, null);
  const unlinked = data.cafes.find(c => c.id === 'unlinked');
  assert.equal(unlinked.area, 'busan');
  assert.equal(unlinked.active, false);
  assert.equal(unlinked.coverage, 'unconfigured');
});


test('읽기 할당량 오류 직후 새로고침이 전체 DB 조회를 반복하지 않는다', async () => {
  let dbCalls = 0;
  const service = server({ readFailure: Object.assign(new Error('Quota exceeded.'), { code: 8 }), onGetDb: () => dbCalls++ });
  const first = await service.getDashboardData('2026-11-15', true);
  const second = await service.getDashboardData('2026-11-15', true);
  assert.equal(dbCalls, 1);
  assert.ok(first.warnings.some(w => w.includes('할당량')));
  assert.ok(second.warnings.some(w => w.includes('할당량')));
  assert.equal(second.dataFetchedAt, null);
});
