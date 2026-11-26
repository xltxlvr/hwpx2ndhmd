# 변경 내역

최신 버전이 위에 옵니다.

## 0.0.4 (2026-11-26)

**추가**
- 미주를 ndhmd4tex 방식으로 출력: 본문 `[^en1]{end}`, 정의 `[^en1]: …`, front matter 에 `mappingrule`(`\endnote{%s}`)과 `endnotes` 패키지 설정. `--endnotes {ref,collect,drop}` (`collect` 는 예전의 문서 끝 모음 방식)
- 구역(`sectionN.xml`)이 여러 개인 문서를 `content.hpf` 순서대로 모두 변환 (이전에는 첫 구역만)
- `--keep-linebreaks`: 한글의 강제 줄바꿈을 마크다운 줄바꿈으로 남김
- `LICENSE`(MIT), `CHANGELOG.md`, `mathsyntax.md` 이스케이프 예시

**수정**
- 각주·미주 안의 문단 구분을 한 문단 안의 강제 줄바꿈으로 잇도록 변경 (이전: 4칸 들여쓴 별도 문단)
- 수식 안 `%`·`$`와, 따옴표 글·기타 문자(`\text{…}`) 안의 `% $ # & _ ^ ~ { } \` 를 이스케이프 (`%` 가 그대로 남아 컴파일 오류가 나던 문제)

## 0.0.1 (2026-11-25)

첫 프로토타입.
- 한글 hwpx → (ndh)md: 문단 스타일은 `:::{환경}`, 개요·헤딩 추정, 인용·글상자는 `:::{quote}`
- 한컴 수식 → LaTeX(`hwpeq.py`, rhwp 규칙 기반), 디스플레이 수식 추정, 앞머리 `amsmath,amssymb`
- 그림 추출(BMP → PNG)과 `![캡션](파일){width=…}`, 표는 변환 가능할 때만 변환하고 아니면 자리 표시
- 각주(pandoc 방식), 자동 문단 번호(`{1}.`), 미주를 문서 끝에 모음
- 스타일 이름 → 환경 이름 대응표, `--custompkg`, `--display-style`, 버전 표시(`-V`)
