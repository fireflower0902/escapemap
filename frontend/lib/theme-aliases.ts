// 동일 지점·동일 테마명으로 검증한 과거 ID. 원래 기록은 DB에 보존합니다.
const aliases: Readonly<Record<string,string>> = {
  "1551717206__기억의_틈": "official_xcape_gn__기억의_틈",
  "1551717206__다나아종합병원": "official_xcape_gn__다나아종합병원",
  "1551717206__수취인초대": "official_xcape_gn__수취인초대",
  "1551717206__제3표류도": "official_xcape_gn__제3표류도",
  "1551717206__제5수감동": "official_xcape_gn__제5수감동",
  "361428621__경성도박장": "official_xcape_xr__경성도박장",
  "361428621__그믐달살인사건": "official_xcape_xr__그믐달살인사건",
  "361428621__베다바리": "official_xcape_xr__베다바리",
  "361428621__운필귀정": "official_xcape_xr__운필귀정",
  "361428621__청림맨션": "official_xcape_xr__청림맨션",
  "27354377__501동_사람들": "official_xcape_xc__501동_사람들",
  "27354377__숨바꼭질": "official_xcape_xc__숨바꼭질",
  "27354377__이도공간": "official_xcape_xc__이도공간",
  "27354377__짜불성설": "official_xcape_xc__짜불성설",
  "1599918263__501동사람들": "official_xcape_sw__501동사람들",
  "1599918263__기묘한날개짓": "official_xcape_sw__기묘한날개짓",
  "1599918263__숨바꼭질": "official_xcape_sw__숨바꼭질",
  "1599918263__인지상점": "official_xcape_sw__인지상점",
  "1599918263__제물의_밤": "official_xcape_sw__제물의_밤"
};

export function canonicalThemeIds(value: unknown): string[] {
 if (!Array.isArray(value)) return [];
 return [...new Set(value.filter((id): id is string => typeof id === "string").map(id => Object.hasOwn(aliases,id) ? aliases[id] : id))];
}
