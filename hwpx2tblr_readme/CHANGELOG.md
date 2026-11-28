# 변경 내역

## 0.0.11 (2026-11-28)

**바뀜**
- `--env auto`일 때 캡션이 있는 표만 짧아도 `longtblr`로 냄 (캡션은 `longtblr`에서만 붙음). 캡션 없는 짧은 표는 그대로 `tblr`

**고침**
- 머리글 행 수(`rowhead`)가 행 수 이상이 되어 한 행짜리 `longtblr`이 깨지던 것: 최대 행 수 − 1

## 0.0.10 (2026-11-28)

**고침**
- 표 폭 전체를 차지하는 병합 칸(주석·자료 행)의 글이 줄바꿈되지 않고 잘리던 문제: 그런 칸에 `cell{행}{1}={wd=칸 폭}`을 줌. 대상은 마지막 행이거나, 안에 `\par`가 있거나, 글이 60자 이상인 칸 (`talltblr`·`remark`는 쓰지 않음). `.tblr` 출력의 `cell_format`에도 들어감

## 0.0.9 (2026-11-27)

**추가**
- `--format tblr`: 표 하나마다 tblrDoumi 가 여는 `.tblr`(JSON) 파일 하나(`table-001.tblr`…, `-o`는 폴더). 칸 글·병합·선·바탕색·열 너비를 tblrDoumi 의 항목(lines, cell_format, generic_option, colspec, cells …)으로 나누어 담고 `latex_code`도 같은 순서로 조립. 바탕색 이름(`hwpRRGGBB`)을 정의한 `colors.tex`를 함께 씀
- `tests/check_tblr_json.py`: 폴더의 `.tblr`들의 `latex_code`를 모아 xelatex으로 컴파일해 보는 점검

## 0.0.8 (2026-11-27)

**추가**
- `--split`: 표 하나마다 파일 하나(`table-001.tex`…). 각 파일에 그 표가 쓴 색(`\providecolor`)과 필요한 패키지만 적고, `--standalone`이면 각각 컴파일되는 문서. `--only`와 함께 쓸 수 있음
- `tests/make_sample.py`, `samples/sample3.hwpx` (표 세 개짜리 예제)

## 0.0.7 (2026-11-27)

**추가**
- `pic_latex(doc, pic, 경로)`: 표 안의 그림을 `\includegraphics`로. 크기는 한글의 표시 크기 × 표의 축소 비율(`doc.pic_scale`), 너비는 `\linewidth` 이하, 높이도 주어 `keepaspectratio`. 단독 실행은 그림 파일이 없어 여전히 `[그림]`

## 0.0.6 (2026-11-27)

**추가** (hwpx2ndhmd 0.0.16 이 불러 쓰기 위한 것)
- `∼`(U+223C)를 물결표(U+301C)로, 곧은 따옴표를 굽은 따옴표로 (`--no-wavedash`로 끔). ndhmd4tex 는 원문 구간에 기호 치환을 하지 않음
- `build_parser()`, `Doc(…, roots=)`, `doc.pic_hook`(표 안의 그림), `doc.sub_env`(안쪽 표를 `subtblr`로)
- 칸 글의 `<!--`를 `<!-{}-`로 (마크다운 주석으로 읽히지 않게)

**수정**
- `--env longtblr`를 강제해도 안쪽 표는 `tblr`로

## 0.0.5 (2026-11-27)

- `\par` 가 든 칸은 칸 전체를 중괄호로 묶음

## 0.0.4 (2026-11-27)

**수정**
- 실제 문서(국회예산정책처 보고서, 표 282개)로 확인: 칸 여백이 `4294967295`(= -1)로 적힌 칸이 1514개 있었음. 이런 칸은 걸러 내는 데서 그치지 않고 표의 기본 여백(`inMargin`)으로 대신함 (둘 다 이상하면 `colsep`/`rowsep` 을 내지 않음)
- `[`·`*` 로 시작하는 칸 글 앞에 `{}`를 붙임: tabularray 가 `[`를 선택 인자로 읽어 `Missing number` 오류가 났음

## 0.0.3 (2026-11-27)

**수정**
- `colsep=11275676.63mm` 같은 비상식적인 값이 나오던 것을 고침: hwpx 의 길이 속성이 부호 없는 32비트 음수(4294967xxx)로 적힌 경우가 있어 평균을 망가뜨렸음. 길이 값을 읽을 때 음수·과대 값을 걸러 내고(`hu()`), 칸 안쪽 여백은 평균 대신 중앙값을 쓰며 `--min-sep`~`--max-sep`(기본 0.8~5 mm)으로 묶음. 쓸 만한 값이 없으면 `colsep`/`rowsep` 을 내지 않고 경고
- 칸 너비, 표 너비, 쪽 여백 읽기에도 같은 검사를 적용

## 0.0.2 (2026-11-27)

- 표의 가로 길이(`hp:sz width`)를 `width=<mm>` 로, 모든 열을 `X[정렬,co=칸 너비 비율]` 로 냄 (기본). 본문 너비보다 길면 본문 너비로 줄임
- `--colspec` 값: `auto`(기본) `width` `linewidth` `fixed` `natural` (`x` 는 `linewidth` 로 바뀜)

## 0.0.1 (2026-11-27)

- 첫 버전: hwpx 의 표를 tblr/longtblr 로 변환 (병합, 너비, 정렬, 테두리, 바탕색, 제목 행, 중첩 표, 수식, 글자 서식)
- 시험: 즉석 hwpx 단위 시험 15건, 실제 문서 8건 변환·xelatex 컴파일 확인
