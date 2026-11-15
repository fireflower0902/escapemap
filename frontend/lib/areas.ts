/** 검색 UI와 Next.js 검색 API가 공유하는 전국 지역 코드. */
export const AREAS = [
  { value: "all", label: "전국 전체" },
  { value: "seoul", label: "서울 전체" },
  { value: "gangnam", label: "강남/역삼" },
  { value: "hongdae", label: "홍대/합정" },
  { value: "sinchon", label: "신촌/이대" },
  { value: "konkuk", label: "건대/광진" },
  { value: "jamsil", label: "잠실/송파" },
  { value: "itaewon", label: "이태원/한남" },
  { value: "myeongdong", label: "명동/종로" },
  { value: "daehakro", label: "대학로" },
  { value: "sinlim", label: "신림" },
  { value: "seongsu", label: "성수/성동" },
  { value: "seoul_other", label: "서울 기타" },
  { value: "gyeonggi", label: "경기" },
  { value: "incheon", label: "인천" },
  { value: "busan", label: "부산" },
  { value: "daegu", label: "대구" },
  { value: "gwangju", label: "광주" },
  { value: "daejeon", label: "대전" },
  { value: "ulsan", label: "울산" },
  { value: "sejong", label: "세종" },
  { value: "gangwon", label: "강원" },
  { value: "chungbuk", label: "충북" },
  { value: "chungnam", label: "충남" },
  { value: "cheonan", label: "천안" },
  { value: "jeonbuk", label: "전북" },
  { value: "jeonnam", label: "전남" },
  { value: "gyeongbuk", label: "경북" },
  { value: "gyeongnam", label: "경남" },
  { value: "jeju", label: "제주" },
  { value: "etc", label: "기타/지역 미분류" },
] as const;

export const AREA_VALUES: readonly string[] = AREAS.map(a => a.value);
export const AREA_LABELS = Object.fromEntries(AREAS.map(a => [a.value, a.label]));
const SEOUL_AREAS = new Set([
  "gangnam", "hongdae", "sinchon", "konkuk", "jamsil", "itaewon",
  "myeongdong", "daehakro", "sinlim", "seongsu", "seoul_other",
]);
const SEOUL_DISTRICTS: Record<string, string> = {
  강남구: "gangnam", 서초구: "gangnam", 마포구: "hongdae", 서대문구: "sinchon",
  광진구: "konkuk", 송파구: "jamsil", 강동구: "jamsil", 용산구: "itaewon",
  중구: "myeongdong", 종로구: "myeongdong", 관악구: "sinlim", 성동구: "seongsu",
};
const PROVINCE_PREFIXES: [string, string[]][] = [
  ["busan", ["부산"]], ["daegu", ["대구"]], ["incheon", ["인천"]],
  ["gwangju", ["광주"]], ["daejeon", ["대전"]], ["ulsan", ["울산"]],
  ["sejong", ["세종"]], ["gyeonggi", ["경기"]], ["gangwon", ["강원"]],
  ["chungbuk", ["충북", "충청북도"]], ["chungnam", ["충남", "충청남도"]],
  ["jeonbuk", ["전북", "전라북도"]], ["jeonnam", ["전남", "전라남도"]],
  ["gyeongbuk", ["경북", "경상북도"]], ["gyeongnam", ["경남", "경상남도"]],
  ["jeju", ["제주"]],
];

export function resolveCafeArea(area?: string, rawAddress?: string): string {
  area = (area ?? "").trim().toLowerCase();
  const address = (rawAddress ?? "").trim();
  if (address.startsWith("서울")) {
    return area === "daehakro" && address.includes("종로구") ? area : SEOUL_DISTRICTS[address.split(/\s+/)[1]] ?? "seoul_other";
  }
  for (const [code, prefixes] of PROVINCE_PREFIXES) {
    if (prefixes.some(prefix => address.startsWith(prefix))) {
      return code === "chungnam" && area === "cheonan" && address.includes("천안시") ? area : code;
    }
  }
  return AREA_VALUES.includes(area) && area !== "all" && area !== "seoul" ? area : "etc";
}

export function areaMatches(requested: string, cafeArea: string): boolean {
  if (requested === "all") return true;
  if (requested === "seoul") return SEOUL_AREAS.has(cafeArea);
  if (requested === "chungnam") return cafeArea === "chungnam" || cafeArea === "cheonan";
  return requested === cafeArea;
}
