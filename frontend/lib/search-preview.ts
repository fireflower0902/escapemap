// 기존 검색 UI 확인용 예시. 실제 예약 현황이 아닙니다.
export const searchPreviewCafes = [
  {
    id: "preview-1", name: "이스케이프 스튜디오", branch_name: "강남점",
    address: "서울 강남구 · 미리보기용 예시 카페", website_url: null, crawled: true,
    themes: [
      {
        id: 90001, name: "어느 탐정의 마지막 사건", difficulty: 3,
        duration_min: 60, poster_url: null,
        slots: [
          { time: "11:00", status: "full", booking_url: null },
          { time: "12:30", status: "full", booking_url: null },
          { time: "14:00", status: "available", booking_url: null },
          { time: "15:30", status: "available", booking_url: null },
          { time: "17:00", status: "full", booking_url: null },
          { time: "18:30", status: "available", booking_url: null },
          { time: "20:00", status: "available", booking_url: null },
          { time: "21:30", status: "closed", booking_url: null },
        ],
      },
      {
        id: 90002, name: "한밤의 도서관", difficulty: 4,
        duration_min: 75, poster_url: null,
        slots: [
          { time: "11:30", status: "full", booking_url: null },
          { time: "13:00", status: "full", booking_url: null },
          { time: "14:30", status: "available", booking_url: null },
          { time: "16:00", status: "full", booking_url: null },
          { time: "17:30", status: "available", booking_url: null },
          { time: "19:00", status: "full", booking_url: null },
          { time: "20:30", status: "available", booking_url: null },
        ],
      },
    ],
  },
  {
    id: "preview-2", name: "미스터리 룸", branch_name: "역삼점",
    address: "서울 강남구 · 미리보기용 예시 카페", website_url: null, crawled: true,
    themes: [{
      id: 90003, name: "사라진 편지", difficulty: 2, duration_min: 60, poster_url: null,
      slots: [
        { time: "13:00", status: "available", booking_url: null },
        { time: "15:00", status: "full", booking_url: null },
        { time: "17:00", status: "available", booking_url: null },
        { time: "19:00", status: "available", booking_url: null },
      ],
    }],
  },
];
