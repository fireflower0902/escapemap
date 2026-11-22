const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('fs');const ts=require('typescript');
const mod={exports:{}};new Function('exports','module',ts.transpileModule(fs.readFileSync('lib/theme-aliases.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(mod.exports,mod);
const {canonicalThemeIds}=mod.exports;
const aliases=JSON.parse(fs.readFileSync('../backend/data/verified-cafe-aliases.json','utf8')).theme_aliases;
test('찜·방문 기록은 같은 지점의 검증된 현재 테마로 이동하고 중복을 합친다',()=>{
 for(const [old,current] of Object.entries(aliases))assert.deepEqual(canonicalThemeIds([old,current,old]),[current]);
 assert.equal(Object.keys(aliases).length,19);
});
test('다른 지점의 동명 테마·알 수 없는 ID는 보존한다',()=>{
 assert.deepEqual(canonicalThemeIds(['27354377__숨바꼭질','1599918263__숨바꼭질','unknown',null,3]),['official_xcape_xc__숨바꼭질','official_xcape_sw__숨바꼭질','unknown']);
 assert.deepEqual(canonicalThemeIds(['__proto__','constructor']),['__proto__','constructor']);
 assert.deepEqual(canonicalThemeIds(null),[]);
});
test('ID 전환은 반복해도 결과가 바뀌지 않는다',()=>{const once=canonicalThemeIds(Object.keys(aliases));assert.deepEqual(canonicalThemeIds(once),once);});
