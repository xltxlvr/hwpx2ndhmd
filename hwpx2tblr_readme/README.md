# hwpx2tblr

hwpx 문서에서 **표만** 추려 tabularray(`tblr` / `longtblr`) 코드로 바꾸는 독립 스크립트입니다. hwpx2ndhmd 가 파이프 표로 바꾸지 못하는 표(병합 칸, 테두리·바탕색이 중요한 표)를 위한 우회로이며, 통합은 시험을 거친 뒤의 과제입니다.

문서의 나머지(본문 문단, 그림, 쪽 레이아웃)는 보지 않습니다. 파이썬 3 표준 라이브러리만 씁니다(수식은 같은 폴더의 `hwpeq.py`, 없으면 수식 원문을 `\texttt`로 남깁니다).

```
python hwpx2tblr.py 문서.hwpx                 # 문서.tblr.tex (조각: \input 해서 쓴다)
python hwpx2tblr.py 문서.hwpx --standalone    # 바로 xelatex 로 컴파일되는 문서
python hwpx2tblr.py 문서.hwpx --list          # 표 목록(행·열·병합·환경·폭)
python hwpx2tblr.py 문서.hwpx --only 2,4-5    # 일부만
python hwpx2tblr.py 문서.hwpx --split         # 표마다 파일 하나 (문서_tblr/table-001.tex …)
```

## 옮기는 것

| hwpx | tabularray |
|---|---|
| 병합 칸 | 선언부 `cell{행}{열}={r=,c=}{}` (덮인 칸은 빈 칸 `&`) |
| 표의 가로 길이(`hp:sz width`)와 칸 너비 | 모든 열을 `X[정렬,co=비율]`로 하고 `width=<mm>`; 비율은 칸 너비(안쪽 여백 뺀 폭)를 합 100 으로 맞춘 것. 본문 너비보다 길면 본문 너비로 줄임 |
| 문단 정렬, 세로 정렬 | 열 정렬은 다수결, 예외는 `cell{행}{열}={halign=,valign=}` |
| 테두리(종류·굵기·색) | `hline{…}={…}{wd=,dashed,색}`, `vline{…}` — 같은 모양끼리 묶음 |
| 바탕색 | `bg=hwpRRGGBB` + `\providecolor` |
| 칸 안쪽 여백 | `colsep`, `rowsep` |
| 제목 행(`header="1"`), 긴 표 | `longtblr` + `rowhead=` (행이 30개 이상이거나 추정 높이가 본문 높이의 0.7배 이상) |
| 캡션 | `longtblr` 의 `caption={…}` (없으면 `entry=none,label=none`) |
| 표 안의 표 | 안쪽도 `tblr`(중괄호로 감쌈) |
| `∼`(U+223C), 곧은 따옴표 | 물결표 U+301C, 굽은 따옴표 (원문 구간은 ndhmd4tex 의 기호 치환을 받지 못함) |
| 수식 | `$…$` (`&` 가 든 `cases`·행렬은 `{$…$}`), 수식 안의 줄바꿈(`#`)은 줄마다 따로 수식 |
| 굵게·기울임·밑줄·취소선 | `\textbf` `\textit` `\underline` `\sout`(ulem) |
| 밑줄 친 빈칸(답 쓰는 줄) | `\underline{\hspace*{…em}}` |
| 칸 안의 문단·강제 줄바꿈 | `\\` (`\\`가 든 칸은 칸 전체를 `{…}`로 묶음) |

필요한 패키지는 출력 머리의 주석에 적힙니다: `tabularray`, `xcolor`, (`amsmath`, `amssymb`, `ulem`).

## 옵션

| 옵션 | 기본 | 설명 |
|---|---|---|
| `-o 파일` | `입력.tblr.tex` | 출력 |
| `--standalone` | | 완전한 문서로 냄(xelatex, fontspec) |
| `--font 이름` | `Noto Serif CJK KR` | `--standalone` 의 본문 글꼴 |
| `--list`, `--only N,M-K` | | 목록만 / 일부만 |
| `--split` | | 표 하나마다 파일 하나로 낸다(`-o`는 폴더, 기본 `입력이름_tblr/`, 파일 `table-001.tex`…). 각 파일에는 그 표가 쓴 색·패키지만 적으며, `--standalone`이면 각각 바로 컴파일된다 |
| `--env {auto,tblr,longtblr}` | `auto` | auto: 긴 표만 longtblr |
| `--long-table X`, `--long-table-rows N` | `0.7`, `30` | 긴 표 기준(0 이면 끔) |
| `--colspec {auto,width,linewidth,fixed,natural}` | `auto` | width: X 열 + 표의 원래 가로 길이 / linewidth: X 열 + `\linewidth` / fixed: 칸마다 `Q[wd=mm]` / natural: 글 길이대로 / auto: width 이되 본문 너비보다 길면 본문 너비 |
| `--textwidth MM` | 문서의 쪽 설정 | 본문 너비 |
| `--no-margins`, `--min-sep MM`, `--max-sep MM` | | 칸 안쪽 여백을 쓰지 않음 / 최소(기본 0.8) / 최대(기본 5) |
| `--no-borders`, `--no-fills`, `--no-format` | | 테두리 / 바탕색 / 글자 서식을 옮기지 않음 |
| `--justify` | | 양쪽 정렬을 `j` 로(기본 `l`) |
| `--header {auto,first,none}` | `auto` | longtblr 머리글 행 |
| `--no-wavedash` | | `∼`(U+223C)를 물결표(U+301C)로, 곧은 따옴표를 굽은 따옴표로 바꾸는 것을 끔 |

## tblrDoumi 에서 편집하기 (`.tblr`)

```
python3 hwpx2tblr.py 문서.hwpx --format tblr -o 표폴더
```

표마다 `table-001.tblr`, `table-002.tblr`… 가 생기며 tblrDoumi 에서 바로 열어 고칠 수 있습니다(`--only`로 일부만 가능). 바탕색이 있는 표는 `colors.tex`의 `\providecolor` 줄을 문서 머리부에 넣어야 컴파일됩니다(색 이름 `hwpRRGGBB`). tblrDoumi 의 표 화면에는 이 색 이름이 보이지 않아 칸 색이 검게 보일 수 있으나, 생성되는 코드에는 영향이 없습니다. 표 안의 그림은 `[그림]` 자리 표시로 남습니다.

## 옵션 메모

- `--colspec textwidth`: `--colspec linewidth`와 같되 `width=\textwidth`로 냅니다.
- `--header N`: longtblr 의 머리글 행(`rowhead`)을 위에서 N 행으로 정합니다 (`0`은 없음, 최대 5). 표의 행 수보다 많으면 행 수 − 1 로 줄입니다.
- 칸 안에서 줄을 바꾸는 곳은 `\\`로 냅니다 (칸 전체를 `{…}`로 묶으므로 `\newline`과 같습니다). 병합은 칸 안의 `\SetCell` 대신 선언부의 `cell{행}{열}={r=,c=}{}`로 냅니다.

## 주석·자료 행

표의 마지막 행이 표 폭 전체로 병합된 한 칸이고 거기에 `주:`, `자료:` 같은 글이 있는 표가 흔합니다. tabularray 의 X·Q 열에서는 이런 병합 칸의 폭이 정해지지 않아 긴 글이 줄바꿈되지 않고 잘리므로, 행의 모든 열을 덮는 병합 칸에는 (내용과 상관없이) 늘 `cell{행}{1}={c=열 수}{wd=…mm}`로 칸 폭(표 폭 − 2×colsep)을 줍니다. `talltblr`의 `remark`로 내보내는 방법도 있으나, `longtblr` 표와 섞어 쓰기 어색하여 쓰지 않습니다.

## 알려진 한계

- **그림**은 `[그림]` 자리 표시로 남깁니다.
- **한 행보다 큰 병합 칸이 쪽을 넘으면** tabularray 는 행 가운데서 쪽을 나눌 수 없어 빈 쪽이 생길 수 있습니다(경고를 냅니다).
- **겹선**은 굵은 한 줄로 근사합니다. 대각선, 칸 안 그림 배경, 그러데이션 바탕은 옮기지 않습니다.
- **행 높이**는 옮기지 않습니다(내용에 맞춤).
- **이상한 길이 값**(부호 없는 32비트로 적힌 음수 같은 것, 너무 큰 값)은 읽을 때 걸러 냅니다. 칸 안쪽 여백은 걸러 낸 뒤 중앙값을 쓰고 `--min-sep`~`--max-sep` 안으로 묶습니다. 쓸 만한 값이 없으면 `colsep`/`rowsep`을 내지 않습니다(경고를 냅니다).
- **각주·미주**는 칸 안에 `\textsuperscript{(글)}` 로 풀어 씁니다.
- 한글 글꼴은 직접 지정해야 합니다. xelatex 에서 한자만 이어진 긴 글은 줄이 나뉘지 않을 수 있습니다(xeCJK·luatexja 를 쓰면 풀립니다).

## 다른 도구에서 불러 쓰기

hwpx2ndhmd 가 `--table tblr`(과 `auto`의 마지막 수단)로 이 모듈을 불러 씁니다. 쓸 만한 입구는 다음과 같습니다.

- `build_parser()`: 옵션 기본값을 담은 파서. `parse_args(['x.hwpx'])`로 인자를 얻습니다.
- `Doc(경로 또는 ZipFile, roots=None)`: 이미 읽어 둔 구역(`roots`)을 넘기면 다시 읽지 않습니다. `doc.colors`(쓴 색), `doc.need`(필요한 패키지), `doc.warn`을 보고 머리글을 만드는 것은 부르는 쪽 몫입니다.
- `doc.pic_hook`: 표 안의 그림 요소를 받아 LaTeX 글을 돌려주는 함수(없으면 `[그림]`).
- `doc.sub_env = True`: 안쪽 표를 `subtblr`, `subsubtblr`… 로 냅니다(`doc.sub_names`에 모임; `\NewTblrEnviron{…}` 필요). 바깥 `\end{tblr}`를 첫 `\end{tblr}`로 찾는 도구(ndhmd4tex)를 위한 것입니다.
- `table_tex(doc, tbl 요소, 인자)`: 표 하나를 `\begin{tblr}…\end{tblr}` 문자열로.

## 시험

```
python3 -m unittest discover -s tests -v           # 즉석에서 만든 작은 hwpx 로 변환·컴파일
python3 tests/check_docs.py 문서1.hwpx 문서2.hwpx   # 실제 문서를 변환하고 xelatex 로 컴파일
```

수식 변환 규칙의 출처는 `LICENSE.rhwp`, 라이선스는 `LICENSE`(MIT)입니다.
