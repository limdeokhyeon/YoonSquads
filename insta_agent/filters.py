"""자동 제외 키워드: 일반인 피해자·자살·성범죄처럼 올리면 위험한 기사는 후보로 만들지 않는다.

기본 목록을 쓰고, `.env`의 BLOCK_KEYWORDS 로 바꿀 수 있다(비워 두면 필터 끔, 쉼표로 구분).
제목과 검색 요약 둘 다 검사한다.
"""

from __future__ import annotations

DEFAULT_BLOCK = [
    # 자살·자해 (보도 권고기준상 구체적 방법·장소 보도 지양)
    "자살", "극단적 선택", "극단적선택", "투신", "스스로 목숨", "유서", "목숨을 끊",
    # 성범죄·피해자
    "성폭행", "성폭력", "성추행", "성범죄", "성착취", "불법촬영", "몰카", "딥페이크", "강간", "강제추행",
    # 아동·청소년 피해, 학대
    "아동학대", "학대", "미성년자 피해", "초등생 피해", "집단폭행",
    # 시신·변사
    "시신", "변사체", "사체", "토막",
]


def block_match(text: str, keywords: list[str]) -> str | None:
    """text 에 들어 있는 제외 키워드를 하나 돌려준다(없으면 None). 띄어쓰기 차이는 무시한다."""
    flat = text.replace(" ", "")
    for kw in keywords:
        if kw and kw.replace(" ", "") in flat:
            return kw
    return None
