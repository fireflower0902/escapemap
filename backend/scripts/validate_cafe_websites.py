#!/usr/bin/env python3
"""카페 웹사이트 상태 검증 - HTTP 요청 및 페이지 분석"""
import requests
from urllib.parse import urlparse
import json
from datetime import datetime

# 검증할 카페 목록
SAMPLE_CAFES = [
    {
        "name": "쿠쿠룸190000",
        "website": "http://place.map.kakao.com/2006661572",
        "type": "kakao_map"
    },
    {
        "name": "초상화",
        "website": "http://place.map.kakao.com/260184665",
        "type": "kakao_map"
    },
    {
        "name": "파라박스",
        "website": "https://parabox.kr/",
        "type": "website"
    },
    {
        "name": "개꿀이스케이프",
        "website": "https://doghoneyescape.com/",
        "type": "website"
    },
    {
        "name": "시그널헌터",
        "website": "https://www.signalhunter.co.kr/",
        "type": "website"
    },
    {
        "name": "플레이더월드",
        "website": "https://reservation.playthe.world/",
        "type": "website"
    },
    {
        "name": "리얼이스케이프챌린지",
        "website": "http://www.rec-escape.com/",
        "type": "website"
    },
]

# 폐업 신호 키워드
CLOSED_KEYWORDS = [
    "폐업", "영업 종료", "종료됨", "폐쇄", "운영 중지",
    "closed", "permanently closed", "not in business",
    "서비스 종료", "준비중", "coming soon", "오픈 예정"
]

def check_website_status(url):
    """웹사이트 HTTP 상태 확인"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=5, headers=headers, allow_redirects=True)

        result = {
            "status_code": response.status_code,
            "accessible": response.status_code in [200, 301, 302, 403, 404],  # 403, 404도 접근 가능한 것으로 봄
            "content_length": len(response.content),
            "url_final": response.url,
            "title": extract_title(response.text),
        }

        # 폐업 키워드 검색
        content_lower = response.text.lower()
        closed_found = any(kw in content_lower for kw in CLOSED_KEYWORDS)
        result["possibly_closed"] = closed_found

        # 예약 버튼 키워드
        booking_keywords = ["예약", "reservation", "booking", "예약하기", "reserve"]
        booking_found = any(kw in content_lower for kw in booking_keywords)
        result["has_booking"] = booking_found

        # 테마 키워드
        theme_keywords = ["테마", "theme", "room", "방", "escape"]
        theme_found = any(kw in content_lower for kw in theme_keywords)
        result["has_theme"] = theme_found

        return result

    except requests.exceptions.Timeout:
        return {"error": "Timeout - 응답 없음 (폐업 또는 서버 다운)"}
    except requests.exceptions.ConnectionError:
        return {"error": "Connection error - 도메인 없음 또는 서버 다운"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}

def extract_title(html):
    """HTML에서 타이틀 추출"""
    try:
        start = html.find("<title>") + 7
        end = html.find("</title>")
        if start > 6 and end > start:
            return html[start:end].strip()
    except:
        pass
    return "N/A"

def validate_cafes():
    """모든 카페 검증"""
    print("=" * 100)
    print("카페 웹사이트 상태 검증 보고서")
    print(f"검증 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)

    results = {
        "timestamp": datetime.now().isoformat(),
        "cafes": []
    }

    for cafe in SAMPLE_CAFES:
        print(f"\n[{cafe['name']}]")
        print(f"  URL: {cafe['website']}")
        print(f"  유형: {cafe['type']}")

        status = check_website_status(cafe['website'])

        # 결과 출력
        if "error" in status:
            print(f"  ❌ {status['error']}")
            diagnosis = "폐업 가능성 높음"
        elif not status.get("accessible"):
            print(f"  ❌ 접근 불가 (HTTP {status.get('status_code', 'N/A')})")
            diagnosis = "폐업 또는 서버 문제"
        else:
            print(f"  ✅ 접근 가능 (HTTP {status['status_code']})")
            print(f"     타이틀: {status.get('title', 'N/A')}")

            if status.get("possibly_closed"):
                print(f"  ⚠️  폐업 키워드 감지")
                diagnosis = "폐업"
            elif not status.get("has_booking"):
                print(f"  ⚠️  예약 기능 없음")
                diagnosis = "운영 중단 또는 폐업"
            elif not status.get("has_theme"):
                print(f"  ⚠️  테마 정보 없음")
                diagnosis = "크롤링 실패 또는 데이터 문제"
            else:
                print(f"  ✅ 예약 기능 있음, 테마 정보 있음")
                diagnosis = "운영 중"

        print(f"  진단: {diagnosis}")

        cafe_result = {
            "name": cafe['name'],
            "website": cafe['website'],
            "type": cafe['type'],
            **status,
            "diagnosis": diagnosis
        }
        results["cafes"].append(cafe_result)

    # JSON 저장
    with open("cafe_validation_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 100)
    print("검증 요약")
    print("=" * 100)

    operating = sum(1 for c in results["cafes"] if c["diagnosis"] == "운영 중")
    closed = sum(1 for c in results["cafes"] if "폐업" in c["diagnosis"])
    error = sum(1 for c in results["cafes"] if "error" in c)

    print(f"운영 중: {operating}개")
    print(f"폐업: {closed}개")
    print(f"접근 불가: {error}개")
    print(f"\n✅ 상세 보고서 저장: cafe_validation_report.json")

    return results

if __name__ == "__main__":
    validate_cafes()
