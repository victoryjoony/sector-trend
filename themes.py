"""테마 정의. 각 테마 = 대표 ETF(돈의 흐름) + 위키 문서(관심도) + 뉴스 검색어.
대표 종목은 ETF 상위 보유 종목을 매일 yfinance에서 가져온다."""

BENCH = ("SPY", "S&P 500")

# (id, 이름, ETF, 위키 문서[en], 뉴스 검색어[ko])
THEMES = [
    ("tech", "기술", "XLK", ["Cloud_computing"], "미국 기술주"),
    ("fin", "금융", "XLF", ["Bank"], "미국 은행주"),
    ("energy", "에너지", "XLE", ["Oil_price"], "미국 에너지주 유가"),
    ("health", "헬스케어", "XLV", ["Pharmaceutical_industry"], "미국 헬스케어주"),
    ("ind", "산업재", "XLI", ["Infrastructure"], "미국 산업재"),
    ("disc", "경기소비재", "XLY", ["Retail"], "미국 소비재주"),
    ("stap", "필수소비재", "XLP", ["Retail"], "미국 필수소비재"),
    ("util", "유틸리티", "XLU", ["Electric_utility"], "미국 유틸리티주"),
    ("mat", "소재", "XLB", ["Steel"], "미국 소재주"),
    ("re", "부동산", "XLRE", ["Real_estate"], "미국 리츠"),
    ("comm", "커뮤니케이션", "XLC", ["Stock_market"], "미국 커뮤니케이션 서비스주"),
    ("semi", "반도체", "SMH", ["Semiconductor_industry", "Nvidia"], "미국 반도체주"),
    ("soft", "소프트웨어", "IGV", ["Software_as_a_service"], "미국 소프트웨어주"),
    ("ai", "AI·로봇", "BOTZ", ["Artificial_intelligence", "Humanoid_robot"], "AI 로봇주"),
    ("cyber", "사이버보안", "CIBR", ["Cybersecurity"], "사이버보안주"),
    ("quant", "양자컴퓨팅", "QTUM", ["Quantum_computing"], "양자컴퓨팅주"),
    ("def", "방산·우주", "ITA", ["Arms_industry", "Defense_industry"], "미국 방산주"),
    ("nuke", "원전·우라늄", "URA", ["Uranium", "Small_modular_reactor"], "원전 우라늄주"),
    ("grid", "전력망", "GRID", ["Electrical_grid", "Data_center"], "전력망 전력기기주"),
    ("solar", "태양광", "TAN", ["Solar_power"], "태양광주"),
    ("lith", "배터리·리튬", "LIT", ["Lithium-ion_battery"], "리튬 배터리주"),
    ("bio", "바이오", "XBI", ["Biotechnology"], "미국 바이오주"),
    ("rbank", "지역은행", "KRE", ["Mortgage_loan"], "미국 지역은행"),
    ("gold", "금광", "GDX", ["Gold_as_an_investment"], "금광주 금값"),
    ("copper", "구리", "COPX", ["Copper"], "구리 관련주"),
    ("btc", "비트코인", "IBIT", ["Bitcoin"], "비트코인 ETF"),
    ("home", "주택건설", "XHB", ["Mortgage_loan"], "미국 주택건설주"),
    ("air", "항공", "JETS", ["Airline"], "미국 항공주"),
    ("infra", "인프라", "PAVE", ["Infrastructure"], "미국 인프라주"),
]
