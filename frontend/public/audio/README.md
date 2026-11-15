# 문제방 전용 배경음

직접 합성한 180초 추리 분위기 앰비언트. 외부 녹음·샘플·음원은 사용하지 않았다.

원본 생성: `python3 scripts/generate-problem-audio.py /tmp/problem-room.wav`
변환(macOS): `afconvert -f m4af -d aac@44100 /tmp/problem-room.wav public/audio/problem-room-180-v1.m4a`

기본 음소거. 사용자가 켰을 때만 내려받고, 문제 시작 시 재생한다. 중간에 켜면 남은 시간에 맞춰 해당 위치부터 재생한다. 정답·포기·3분 경과·화면 이동 때 중단한다.
