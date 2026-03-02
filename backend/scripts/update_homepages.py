"""
웹 검색으로 찾은 홈페이지 URL을 DB와 Excel에 업데이트하는 스크립트

실행:
  cd escape-aggregator/backend
  python scripts/update_homepages.py
"""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import update
from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe  # noqa: E402

# ── place_id → homepage_url 매핑 ──────────────────────────────────────────
# 웹 검색으로 찾은 URL들
HOMEPAGE_MAP = {
    # 강원
    "230738333":  "http://www.cc-escapezone.co.kr/",        # 이스케이프존 강대점
    # 경기
    "302959300":  "http://www.thedoorsescape.com/",          # 더도어즈이스케이프
    "300855776":  "https://www.todayescape.com/",            # 오늘 탈출 일산
    "1568417037": "https://le-room.co.kr/",                  # 라비린스 이스케이프
    "1620988252": "https://sherlock-holmes.co.kr/",          # 셜록홈즈 부천중동
    "1591055284": "http://xn--bb0b44mb8pfwi.kr/",            # 골든타임이스케이프 2호점
    "779900297":  "https://www.escapecafe.co.kr/",           # 방탈출탐정
    "1121229740": "https://xn--z92b74ha268d.com/",           # 상상의 문 수원2호점
    "1166453549": "https://sherlock-holmes.co.kr/",          # 셜록홈즈 수원인계
    "52252534":   "https://kidsintheroom.com/",              # 키즈인더룸 평촌
    "1888259527": "https://sherlock-holmes.co.kr/",          # 셜록홈즈 범계
    "2021007589": "https://sherlock-holmes.co.kr/",          # 셜록홈즈 용인동백
    "728789378":  "https://sherlock-holmes.co.kr/",          # 셜록홈즈 평택
    "1314964065": "http://ptesc.co.kr/",                     # ESC방탈출카페 평택
    # 경북
    "1266197087": "https://thepanic.modoo.at/",              # 더패닉방탈출카페 포항
    # 광주
    "1544141348": "https://www.roomsa.co.kr/",               # 룸즈에이 광주수완2호점
    "2102768222": "http://xn--vl2bn1fb7gouc9rc40rhobg6ihrh.com/",  # 러시아워 3호점
    "1393764461": "https://gateoftime.kr/",                  # 시간의문 광주점
    "923379950":  "https://www.hideescape.com/",             # 방탈출카페 숨박꼭질 2호점
    "942247508":  "http://xn--vl2bn1fb7gouc9rc40rhobg6ihrh.com/",  # 러시아워 로드맨션
    # 대구
    "363716272":  "http://orangetb.com/",                    # 오렌지티비 대구
    "929019886":  "https://gateoftime.kr/",                  # 시간의문 대구동성로
    # 대전
    "1696389756": "http://www.the-qescapedj.co.kr/",         # 더큐이스케이프 대전
    "1224388097": "https://playthe.world/",                  # 플레이더월드 대전은행
    "1908328454": "http://orangetb.com/",                    # 오렌지티비 대전
    # 부산
    "310013350":  "https://www.seoul-escape.com/",           # 서울이스케이프룸 부산서면
    "629764977":  "https://www.xphobia.net/",                # 비트포비아 레드던전 서면
    "1637143499": "https://keyescape.co.kr/",                # 키이스케이프 부산
    "1495650283": "https://busan.breakoutescapegame.com/en/", # 브레이크아웃 광안
    # 서울 강남
    "522639283":  "http://www.code-escape-garosu.com/",      # 코드이스케이프 가로수길
    "212176813":  "https://doghoneyescape.com/",             # 개꿀이스케이프
    "401872428":  "https://www.signalhunter.co.kr/",         # 시그널헌터 가로수길
    "1277196871": "",                                         # 에피소드방탈출 강남 (없음)
    "1000900386": "https://escapeshop.co.kr/",               # 이스케이프샾 강남
    "1871864524": "https://getawayesc.com/",                 # 겟어웨이방탈출
    "123477337":  "https://parabox.kr/",                     # 파라박스
    # 서울 광진
    "2016521022": "https://escapeshop.co.kr/",               # 이스케이프샾 건대
    "671151862":  "https://www.master-key.co.kr/",           # 마스터키 건대
    "746135486":  "https://playthe.world/",                  # 플레이더월드 건대
    "138006966":  "http://www.themazegd.co.kr/",             # 더메이즈 건대
    "1385414031": "https://play33.kr/",                      # 플레이33
    "1271584354": "http://xn--jj0b998aq3cptw.com/",          # 황금열쇠 건대
    "361428621":  "http://www.x-crime.com/",                 # 엑스크라임 건대2호
    # 서울 마포
    "727312827":  "http://www.mysteryroomescape.com/",       # 미스터리룸이스케이프 홍대2
    "315548029":  "http://www.puzzlefactory.co.kr/",         # 크라임씬 퍼즐팩토리 홍대3
    "1654390566": "https://xescape.com/",                    # 엑스이스케이프 상상마당
    "451924760":  "https://hongdae.breakoutescapegame.com/en/", # 브레이크아웃 홍대
    "759455993":  "https://teraspace.co.kr/",                # 테라스페이스 홍대
    "2070697879": "https://xn--2e0b040a4xj.com",            # 지구별방탈출 홍대어드벤처
    "327610610":  "http://www.ttescape.co.kr/",              # 티켓투이스케이프
    # 서울 서대문
    "690123759":  "https://www.ex-cape.com/",                # 룸익스케이프 인디고블루
    # 서울 서초
    "192767471":  "http://fantastrick.co.kr/",               # 판타스트릭 2호점
    "2058736611": "https://doorescape.co.kr/",               # 도어이스케이프 블루 신논현
    "691418241":  "https://doorescape.co.kr/",               # 도어이스케이프 강남가든
    # 서울 성동
    "259983085":  "https://www.dpsnnn.com/",                 # 단편선 성수
    "2022859547": "http://www.puzzlefactory.co.kr/",         # 크라임씬 퍼즐팩토리 성수
    # 서울 용산
    "888192913":  "https://www.xphobia.net/",                # 미션브레이크 CGV용산
    # 서울 종로
    "1944665207": "https://fuzzyline.co.kr/",                # 하이드앤시크 쌈지길
    # 울산
    "27575809":   "http://thetrap.co.kr/",                   # 트랩코리아 삼산점
    # 인천
    "1637776603": "https://playthe.world/",                  # 플레이더월드 부평
    "2138418097": "https://amazed.co.kr/",                   # 어메이즈드 3호점
    # 전북
    "431508316":  "http://chaosesc.co.kr/",                  # 카오스이스케이프
    "48992610":   "https://keyescape.co.kr/",                # 키이스케이프 전주
    # 제주
    "166623372":  "http://unlimited-escape.com/",            # 언리미티드 이스케이프
    # 충북
    "1574310774": "http://lupinescape.com/",                 # 루팡방탈출카페 1호점
    "2011481622": "http://lupinescape.com/",                 # 루팡방탈출카페 본점
}

# 빈 문자열 제거 (홈페이지 없음 표시 제거)
HOMEPAGE_MAP = {k: v for k, v in HOMEPAGE_MAP.items() if v}


async def update_homepages():
    """DB의 website_url 필드를 업데이트"""
    updated = 0
    not_found = 0

    async with AsyncSessionLocal() as session:
        for place_id, url in HOMEPAGE_MAP.items():
            cafe = await session.get(Cafe, place_id)
            if cafe:
                # 카카오 플레이스 URL만 있는 경우 실제 홈페이지로 교체
                existing = cafe.website_url or ""
                if "place.map.kakao.com" in existing or not existing:
                    cafe.website_url = url
                    updated += 1
            else:
                not_found += 1
                print(f"  [경고] DB에서 ID {place_id} 미발견")

        await session.commit()

    print(f"\n  DB 업데이트 완료: {updated}개 갱신, {not_found}개 미발견")
    return updated


async def main():
    print("=" * 60)
    print("웹 검색 홈페이지 URL → DB 업데이트")
    print("=" * 60)

    # 테이블 확인
    from app.models import cafe, theme, schedule, user, alert  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    updated = await update_homepages()

    print(f"\n  총 {len(HOMEPAGE_MAP)}개 URL 중 {updated}개 DB 업데이트 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
