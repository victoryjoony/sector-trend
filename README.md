# 미국 섹터·테마 트렌드

29개 미국 섹터·테마 ETF를 가격(S&P 500 대비 1·3·6개월), 거래(20일/120일 거래대금), 관심(위키백과 조회수) 세 층으로 매일 순위를 매기는 휴대폰용 페이지.

- 페이지: https://victoryjoony.github.io/sector-trend/
- 갱신: GitHub Actions가 화~토 07:00 KST에 `build.py`를 돌려 `docs/index.html`과 `data/history.json`을 커밋한다. PC가 꺼져 있어도 된다.
- 수동 실행: Actions 탭 → daily-update → Run workflow
- 테마 추가·변경: `themes.py`
- 로컬 실행: `pip install -r requirements.txt && python build.py`

주의: 공개 저장소의 예약 워크플로는 60일 동안 저장소 활동이 없으면 GitHub이 꺼 버린다. 매일 커밋이 생기므로 보통은 문제없지만, 갱신이 멈추면 Actions 탭에서 다시 켜면 된다.

예측이나 매매 권유가 아니라 지금 무엇이 주목받는지 보여주는 페이지다.
