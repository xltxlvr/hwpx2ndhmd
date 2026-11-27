# hwpx2ndhmd

한글(HWP) 문서 `.hwpx`를 (ndh)md 로 바꾸는 도구입니다. [ndhmd4tex](https://github.com/xltxlvr/ndhmd4tex)로 PDF를 만드는 작업의 앞단으로 쓰려고 만들었습니다.

**버전 0.0.10** — 프로토타입입니다. 몇 가지 문서(수학 학습지, 시험지, 고전 수필 모음)로 다듬은 것이라, 다른 종류의 문서에서는 어색한 결과가 나올 수 있습니다.

## 하는 일

- 레이아웃(쪽 설정, 글꼴, 줄 간격 등)은 **무시**하고 **글과 수식은 보존**합니다.
- 수식은 한컴 수식 스크립트를 LaTeX 로 바꿉니다. 중괄호는 꼭 필요한 곳에만 씁니다. 한컴 수식이 거의 다 인라인으로 쓰여 있으므로, 디스플레이 수식은 구조를 보고 추정합니다.
- 그림은 파일로 꺼내(BMP 는 PNG 로 변환) ndhmd 그림 문법으로 낼 자리를 표시합니다.
- 표는 파이프 표 → grid 표 → tabularray 원문(`tblr`) 순으로 가장 단순한 형식으로 냅니다(`--table`).
- 문단 스타일은 `:::{환경}`으로, 번호 머리표와 개요 스타일은 헤딩으로 바꿉니다.
- 글자 서식 중 서체 계열(sans), 굵게, 기울임, 취소선, 밑줄, 강조점은 ndhmd4tex 의 인라인 마크업으로 옮깁니다. 실제로 쓰인 서체만 모은 보고서(`.fonts.md`)도 함께 씁니다.
- 각주와 미주를 모두 살립니다. 미주는 본문에 `[^en1]{end}` 표지를 남기고, 문서 끝에 모으는 일은 ndhmd4tex(`\endnote`)가 맡습니다.

hwpx 는 zip 안에 XML 이 들어 있는 형식입니다. 이 도구는 그 XML 을 직접 읽으며 한컴오피스는 필요 없습니다. 옛 `.hwp` 형식은 읽지 못합니다.

## 요구 사항

- Python 3 (0.0.10 은 Python 3.13 에서 시험했습니다)
- 표준 라이브러리만으로 동작합니다.
- [Pillow](https://python-pillow.org/)는 있으면 씁니다. 없어도 24비트 BMP 는 순수 파이썬으로 PNG 로 바꿉니다. 그 밖의 BMP 는 원본 그대로 저장하고 경고합니다(`--no-pillow`로 Pillow 를 쓰지 않게 할 수 있습니다).

## 빠른 시작

```
python hwpx2ndhmd.py 문서.hwpx -o 문서.md
python hwpx2ndhmd.py 문서.hwpx -o 문서.md --custompkg "esint,mystyle"
python hwpx2ndhmd.py --version
```

`-o`를 주면 같은 폴더에 다음이 만들어집니다.

| 파일 | 내용 |
|---|---|
| `문서.md` | 변환 결과 |
| `image1.png` … | 문서에서 꺼낸 그림 (`--image-dir`, `--image-prefix`로 위치와 이름을 바꿀 수 있음) |
| `문서.envs.tex` | 문단 스타일 이름 → 환경 이름 대응표와 `\newenvironment` 목록 (스타일에서 만든 환경이 있을 때만) |

`-o` 없이 실행하면 표준 출력으로 나옵니다.

## 변환 규칙

### 문단 스타일 → 환경

바탕글·본문 같은 기본 스타일이 아닌 문단 스타일은 `:::{환경}` … `:::`으로 감쌉니다. ndhmd4tex 는 환경 이름에 글자(letter)만 허용하므로, 한글 이름은 로마자(국어의 로마자 표기법, 글자 단위)로, 숫자는 로마 숫자로 바꿉니다.

| 스타일 이름 | 환경 이름 |
|---|---|
| 연습문제 | `yeonseubmunje` |
| 01-문제 | `IMunje` |

이름이 겹치면 `…II`, `…III`처럼 로마 숫자를 덧붙입니다. 이름을 그대로 쓰려면 `--env-names keep`, 직접 정하려면 `--style-map`(JSON)을 씁니다.

```json
{"연습문제": "exercise", "참고": null, "소제목": "heading:2"}
```

(`null`은 환경으로 만들지 않고 본문으로 둠, `heading:N`은 N 수준 헤딩)

이렇게 만든 환경은 LaTeX 에 정의가 없으니 그대로는 `Undefined environment` 오류가 납니다. 그래서 대응표 파일 `문서.envs.tex`에 정의되지 않은 환경만 빈 틀로 만드는 `\newenvironment` 목록을 함께 씁니다.

```latex
%   연습문제 -> yeonseubmunje            (12문단)

\ifcsname yeonseubmunje\endcsname\else\newenvironment{yeonseubmunje}{}{}\fi % 연습문제
```

`--env-in-preamble`을 주면 이 목록을 front matter 의 `preamble+:`에도 넣고, `--env-input`을 주면 목록 대신 `\input{출력파일.envs.tex}` 한 줄을 넣습니다(대응표 파일을 그대로 불러 쓰므로 환경 모양은 그 파일에서 고치면 됩니다). 중첩된 환경은 바깥·안쪽 모두 `:::`로 냅니다(`::::`는 쓰지 않음).

### 헤딩

- 개요 스타일(개요 1, 개요 2 …)이나 문단 모양의 개요 수준이 있으면 그 수준대로 `#` 헤딩을 냅니다. 스타일 이름이 제목·title·heading 꼴이어도 같습니다.
- 개요 스타일이 하나도 없는 문서는 `--headings auto`(기본)가 번호 머리표(`제1장`, `1.`, `1)`, `(1)`, `가.`, `I.`, `①`)·글자 크기·굵기·색·길이·문장 끝맺음을 점수로 매겨 헤딩을 추정합니다. 수준은 머리표 종류별로, 크기와 굵기 순서에 따라 정합니다.
- `--headings style`은 개요 스타일만, `--headings none`은 헤딩을 만들지 않습니다.

### 수식

- 한컴 수식 → LaTeX 변환표는 [`mathsyntax.md`](mathsyntax.md)에 있습니다.
- 수식이 하나라도 있으면 문서 맨 앞에 front matter 를 넣습니다(`--no-preamble`로 끌 수 있음).

  ```
  ---
  preamble+: |
    \usepackage{amsmath,amssymb}
  ---
  ```

  `--custompkg "esint,mystyle"`은 쉼표로 나눈 패키지마다 `\usepackage{…}` 줄을 같은 블록에 더합니다. 수식이 없어도 이 옵션을 주면 front matter 를 만듭니다.
- **디스플레이 수식.** 한 줄에 수식만 있고 구조(행렬, 분수, 큰 연산자 등)나 길이로 보아 따로 세울 만한 것은 디스플레이 수식으로 냅니다. 기본은 `\[` … `\]`(각각 한 줄)이고, `--display-style dollars`는 `$$` … `$$`, `--display none`은 모두 인라인입니다. 추정이 빡빡하거나 느슨하면 `--display-threshold`로 조절합니다.
- 맞붙은 인라인 수식은 하나로 합칩니다(`$a$$=b$`는 `$$`로 오인될 수 있어서).
- 짝이 맞지 않는 `\left`·`\right`는 고치고 경고합니다(자세한 규칙은 `mathsyntax.md`).

### 그림

그림 한 개는 `![캡션](image1.png){width=0.75\linewidth}` 꼴입니다.

- **파일.** 문서 안 그림을 꺼내 저장합니다. BMP 는 PNG 로 바꿉니다. hwpx 의 그림 잘라내기 정보도 반영합니다(`--no-crop`으로 무시).
- **폭.** 문서에서 보이는 크기를 본문 너비에 대한 비율로 옮깁니다(0.05 단위 반올림, 상한 `--image-max`, 기본 0.75). `--image-size fixed`면 모두 `--image-width`(기본 `0.75\linewidth`)로 냅니다.
- **캡션.** 그림의 캡션 요소 → 사용자가 쓴 대체 글(자동 문구 제외) → 바로 다음 문단이 `그림 1. …` 꼴이면 그 글, 순서로 찾고 없으면 비웁니다.

### 표

- 병합 칸과 그림, 중첩 표가 없는 단순한 표는 파이프 표(첫 줄이 머리)로 냅니다. 셀 안의 `|`는 `\|`로 이스케이프합니다.
- 긴 표는 표의 마지막 줄 바로 다음 줄에 `{env=long}`을 붙입니다(ndhmd4tex 의 longtable). 한글에 저장된 표 높이는 고정 행 높이·빈 칸이 섞여 있고 쪽을 넘는 표는 첫 쪽 부분만 저장되어 믿을 수 없으므로, **내용만으로 조판했을 때의 높이**를 추정합니다: 열 너비(한글의 칸 너비 비율, 본문 너비를 넘으면 줄임)에 글자 폭을 채워 줄 수를 세고 줄 간격 1.5를 곱합니다. 이 추정 높이가 본문 높이의 0.7배(`--long-table 0.7`) 이상이거나 행이 30개(`--long-table-rows 30`) 이상이면 붙입니다. 쪽의 어디에 놓였는지는 보지 않습니다. 칸 너비를 알 수 없어 높이를 추정하지 못하면 행 수만 봅니다. 각 옵션에 `0`을 주면 그 기준을 끕니다. 자리 표시만 하는 표에는 붙이지 않습니다.
- **병합 칸이 있는 표**(그림·중첩 표가 없는 것)는 pandoc **grid 표**로 냅니다. ndhmd4tex 가 병합 칸을 `\SetCell[r=,c=]`로 바꿉니다. 칸 안의 글은 낱말 사이 공백에서만 줄을 나누고(ndhmd4tex 가 줄을 공백 하나로 다시 잇기 때문), 칸 너비는 한글 2칸으로 세어 맞춥니다. 첫 행(과 그 행에 걸친 병합)은 머리글(`+===+`)로 둡니다. 열이 12개를 넘거나(`--grid-max-cols`) 칸이 빠지거나 겹쳐 격자를 못 만들면 다음 방식으로 물러납니다. 각주 안의 표는 grid 표를 쓸 수 없어 글만 남깁니다. `--no-grid-tables`로 끌 수 있습니다(`auto`에서는 병합 표가 tblr 로 갑니다).
- **`--table {auto,pipe,grid,tblr}`**: 표를 내는 방식입니다. 기본은 `auto`.
  - `auto`: 병합 칸이 없으면 파이프 표, 있으면 grid 표, 그래도 안 되면(그림·중첩 표가 든 표, 열이 많은 표, 격자가 안 맞는 표) tabularray 원문으로 냅니다. 그것마저 실패하면 `<!-- TABLE 3x4: 변환 불가 -->` 자리 표시와 칸 글(`:::{quote}`)을 남깁니다(`--no-cell-text`면 자리만).
  - `pipe`: 파이프 표만. 병합·그림이 있으면 자리 표시. / `grid`: 모든 표를 grid 표로(그림·중첩 표는 자리 표시).
  - `tblr`: **모든 표**를 tabularray(`tblr`/`longtblr`) 원문으로 냅니다. 테두리·바탕색·칸 너비(`X` 열과 `width=`)·정렬·머리글 행(longtblr)·표 안의 그림과 안쪽 표까지 옮기므로 서식이 중요한 표에 쓰십시오. 명시해야만 쓰이며, `auto`에서는 다른 방식이 안 될 때만 씁니다.
  - tblr 표는 ndhmd4tex 가 원문 그대로 통과시키는 `\begin{tblr}…\end{tblr}` 덩어리입니다. 그래서 ndhmd 마크업은 안 되고, 칸 안의 수식은 이미 LaTeX 로 변환되어 있으며, ndhmd4tex 의 기호 치환(`mappingrule`)도 적용되지 않습니다. 이를 hwpx2tblr 가 대신 합니다: `∼`(U+223C)는 물결표(U+301C)로, 곧은 따옴표는 굽은 따옴표로 바꿉니다(`--tblr-args=--no-wavedash`로 끔). 안쪽 표는 `subtblr`(front matter 에 `\NewTblrEnviron{subtblr}`)로 냅니다. ndhmd4tex 가 `\begin{tblr}`…`\end{tblr}`를 첫 `\end{tblr}`에서 끊기 때문입니다. tblr 표를 쓰면 front matter 의 `preamble+`에 `tabularray`, `xcolor`, 표에 쓴 색(`\providecolor`), 필요한 패키지가 들어갑니다.
  - 표 안의 그림은 파일로 꺼내 `\includegraphics[width=…,height=…,keepaspectratio]`로 냅니다(graphicx 자동 추가). 크기는 한글에 기록된 표시 크기에 표가 본문 너비에 맞춰 줄어든 비율을 곱한 값이고, 너비는 칸 너비를 넘지 않습니다. 파일을 꺼낼 수 없으면 `[그림]`. 표 안의 각주는 괄호 글로 풀어 씁니다. 각주 안에서는 tblr 을 쓸 수 없습니다.
  - `--tblr-args="…"`로 [hwpx2tblr](../hwpx2tblr/README.md)의 옵션을 넘길 수 있습니다(예: `--tblr-args="--colspec linewidth --no-fills"`). 옵션이 한 낱말뿐이면 `--tblr-args=--no-wavedash`처럼 `=`로 붙여야 합니다. 긴 표(`--long-table`, `--long-table-rows`)는 이 도구의 기준을 그대로 따릅니다.
  - 수식 속의 `|`는 `\vert`로 바꿔 파이프·grid 표의 칸 가름과 헷갈리지 않게 합니다. 칸 안의 수식은 줄을 나누지 않습니다.
- 글상자 같은 도형은 안의 글을 `:::{quote}`로 내고(문단이 둘 이상이면 `:::{quotation}`) `<!-- SHAPE:textbox -->` 표시를 붙입니다. 글이 없는 빈 도형은 `--show-empty-shapes`를 줄 때만 표시합니다.

### 여러 구역

구역(섹션)이 여러 개인 문서는 `content.hpf` 의 읽기 순서대로 모든 구역을 이어서 변환합니다. 쪽 너비(그림 폭 비율에 쓰임)는 첫 구역 기준입니다.

### 글자 서식

한글의 글자 모양 중 아래만 옮깁니다. 문단 스타일의 기본 서식과 **다른** 글자에만 붙이므로, 기본이 굵은 스타일의 굵은 글자에는 붙이지 않습니다. 헤딩, 표 안, 글상자 안의 글자에는 붙이지 않습니다.

| 한글 | 출력 | 비고 |
|---|---|---|
| 서체가 sans 계열 (돋움·고딕 등) | `_글_` | rm 문서에서만. 서체 변환은 rm ↔ sf 만 다룸 |
| sans 이면서 굵게 | `__글__` | |
| 굵게 | `**글**` | |
| 기울임 | `*글*` | |
| 굵은 기울임 | `***글***` | |
| 취소선 | `~~글~~` | |
| 강조점 | `^^글^^` | |
| 밑줄 | `==글==` | ndhmd4tex 기본 마크업이 아니어서, 쓰이면 front matter 에 `mappingrule: extra_inline`(`\uline`)과 ulem 설정을 자동으로 넣음 |

- 계열은 서체 이름으로 정합니다. 돋움·고딕·굴림·Sans·Arial 등이 들어간 이름은 sans, 나머지는 rm 입니다. 더 지정하려면 `--sans-fonts "맑은 고딕,나눔고딕"`.
- **문서 본문의 기본 계열**(글자 수가 더 많은 쪽)이 sans 인 문서는 sans 가 기본이므로 `_글_`을 내지 않습니다. 그 안의 rm 글자는 표시할 문법이 없어 그대로 둡니다.
- sans 글자의 기울임은 표시할 문법이 없어 버립니다. 이런 곳은 보고서에 개수를 적습니다.
- `--no-inline-marks`로 모두 끕니다.

#### 서체 보고서

`-o out.md`를 주면 `out.fonts.md`를 함께 씁니다(`--font-report FILE`로 변경). hwpx 의 글꼴 목록에는 쓰지 않는 것이 잔뜩 들어 있으므로, 본문 글자 수를 세어 **실제로 쓰인 서체만** 모읍니다. 서체별 글자 수·글자 종류(한글/영문/한자…)·크기·서식, 쓰인 문단 스타일의 기본 서체와 환경 이름, 수식 글꼴, LaTeX 글꼴 설정 예시가 들어 있습니다. 한글 서식을 LaTeX 로 재현할 때 참고하는 용도입니다.

### 물결표(∼)

옛 입력기와 한글은 물결표를 수학 기호 `∼`(U+223C)로 찍던 일이 있어서 오래된 문서에 많습니다. 수식이 아닌 글 속의 `∼`는 `\~`로 내고, 쓰였으면 front matter 에 `mappingrule`의 `wavedash: 301C`를 넣어 ndhmd4tex 가 물결표(U+301C)로 내게 합니다. 수식 안의 `∼`는 수식 규칙을 따릅니다.

### 각주와 미주

- **각주**는 pandoc 방식입니다. 본문에는 `[^번호]`, 정의는 그 문단 바로 뒤에 `[^번호]: 글`로 냅니다. ndhmd4tex 의 각주는 여러 줄을 받지만 **빈 줄은 각주의 끝**으로 읽으므로, 한글 각주 안의 문단은 줄로 나누어 이어지는 줄을 네 칸 들여쓰고, 문단 경계마다 줄 끝에 `\\`를 답니다(`[^3]: 첫 문단 \\` 다음 줄 `    둘째 문단`). 각주 안의 인용 환경은 `:::{quote}`로 내고(`quotation`은 `quote`로), 그 안의 문단도 빈 줄 없이 `\\`로 잇습니다. 각주 안의 그림은 떠다니는 figure 가 될 수 없어 별행 한 줄의 `\includegraphics[width=…]{파일}`로 냅니다(graphicx 필요, front matter 에 자동 추가). 각주 안의 표는 행마다 한 문단의 글(칸은 ` / `로 이음)로 바꿉니다(아래 "알려진 한계"). 미주(`[^en1]: …`)도 같습니다. 번호는 한글의 각주 번호를 그대로 씁니다. `--footnotes inline`은 `^[글]`, `--footnotes drop`은 버립니다.
- **`--notes-at-end`**: 각주 마크업이 말썽이면 쓰십시오. 본문에는 `(각주 3)`·`(미주 1)` 같은 평문 자리표시만 두고, `--endnote-break`(기본 `\\newpage`) 다음에 `(각주 3) 글` 꼴의 평문단으로 모두 모읍니다. 여러 문단 각주는 `(각주 3)` 문단 뒤에 이어지는 문단으로 냅니다. `--footnotes`·`--endnotes`는 무시하며 front matter 의 미주 설정도 넣지 않습니다.
- **미주**는 각주처럼 본문에 `[^en1]{end}` 를 두고, 정의 `[^en1]: …` 는 그 문단 바로 뒤에 냅니다(이름은 한글의 미주 번호 앞에 `en`을 붙인 것). 미주가 하나라도 있으면 front matter 에 아래 설정을 자동으로 넣습니다. 그러면 ndhmd4tex 가 `{end}` 를 `\endnote{…}` 로 바꾸고 문서 끝에 `\theendnotes` 로 모읍니다. 미주 번호 옆의 아주 작은 장식 그림(폭 약 0.8 cm 이하)은 뺍니다.

  ```yaml
  mappingrule: |
    notes:
      end: '\endnote{%s}'
  preamble+: |
    \usepackage{endnotes}
    \AtEndDocument{\theendnotes}
  ```

  `--endnotes collect`는 예전 방식(본문에 표지 없이 문서 끝 별면에 `{1})` 번호로 모음), `--endnotes drop`은 버립니다.

### 자동 문단 번호

한글의 문단 번호 기능으로 매겨진 번호(문제 번호 등)는 문단 텍스트에 없습니다. 번호 정의와 문단 순서로 세어서 `{1}.`, `{2}.` 꼴로 앞에 붙입니다. 중괄호는 마크다운 목록(`1.`)으로 읽히지 않게 하려는 것입니다. 번호는 번호 정의(numbering)마다 이어서 셉니다. `--no-para-numbers`로 끕니다.

### 마크다운으로 오인되지 않게 하는 처리

- 글로 쓴 번호가 줄 첫머리에 오면(`2011. 10. …`, `1) …`) `{2011}. 10. …`처럼 번호를 중괄호로 묶습니다. 줄 첫머리의 `* `, `- `, `+ `, `# `, `> `는 앞에 `\`를 붙입니다.
- 본문에서 `]` 바로 뒤에 `[`나 `(`가 오면 마크다운이 참조 링크나 링크로 읽으므로 사이에 `{}`를 끼웁니다(`채[^3]{}[눈썹을 찡그린 채]`). `{}`는 ndhmd4tex 에서 글자 그대로 `{}`로 나오는 것을 알고 선택한 방식입니다. 검색하기 쉬우니 최종 원고에서 손봐도 됩니다.

### 알려진 한계

변환기가 아니라 ndhmd4tex·LaTeX 쪽 제약이라서 변환기가 완전히 풀 수 없는 것들입니다.

- **각주·미주 안에는 표를 둘 수 없습니다.** 각주 안의 표는 행마다 한 문단의 글로 바꾸므로 표 모양은 사라집니다(칸은 ` / `로 이음). 필요하면 그 부분을 직접 고쳐 쓰십시오.
- **각주·미주 안의 문단은 빈 줄로 나눌 수 없습니다.** 문단 경계는 `\\`(줄바꿈)로 나타내므로 문단 사이 간격이나 들여쓰기는 사라집니다.
- **각주·미주 안의 인용문은 `quote`만 됩니다.** 글상자 같은 것이 각주 안에 있으면 `quote`로 냅니다. 문단이 여럿이어도 `quotation`을 쓰지 않습니다(ndhmd4tex 의 `footnote_envs` 에 `quotation`을 넣으면 고쳐 쓸 수 있습니다).
- **BMP 그림은 컴파일 엔진에 따라 넣을 수 없습니다.** 변환기는 BMP 를 PNG 로 바꿔 저장하지만, Pillow 가 없고 24비트 압축 없는 BMP 가 아니면 원본 BMP 를 그대로 저장하고 경고를 냅니다. 그런 그림이 있으면 Pillow 를 설치하고 다시 변환하세요.

## 쪽 설정 기록 (`--layout`)

쪽 설정은 **재현하지 않고 기록만** 합니다. `--layout`을 주면 `.layout.json`에 구역마다 용지 크기(mm와 원래 HWPUNIT, 용지 이름 추정, 방향), 여백 7종, 쪽 번호 시작값, 각주·미주 모양, 쪽 테두리와, 단 설정(`colPr`), 머리말·꼬리말(적용 쪽과 글), 쪽 번호 표시, 쪽 감추기, 강제 쪽 나눔을 적습니다. 위치는 최상위 문단 번호(모든 구역을 이어 1부터)입니다. `geometry_hint`는 `\geometry{…}` 한 줄 제안일 뿐 어디에도 적용되지 않으며, top·bottom 은 위쪽+머리말, 아래쪽+꼬리말(본문이 시작·끝나는 자리)입니다. 한글은 쪽 나눔 결과를 파일에 저장하지 않으므로 몇 쪽에 무엇이 놓이는지는 알 수 없습니다.

## 옵션

`python hwpx2ndhmd.py -h`로도 볼 수 있습니다.

| 옵션 | 기본 | 설명 |
|---|---|---|
| `-o, --output` | 표준 출력 | 출력 파일 |
| `-V, --version` | | 버전 표시 |
| `--headings {auto,style,none}` | `auto` | 헤딩 추정 방식 |
| `--heading-base N` | 1 | 가장 높은 헤딩 수준 |
| `--heading-threshold N` | | 자동 추정 점수 문턱 (최대 7) |
| `--heading-maxlen N` | | 헤딩으로 볼 최대 글자 수 |
| `--style-map FILE` | | 스타일 이름 → 환경 이름 JSON |
| `--env-names {romanize,keep}` | `romanize` | 환경 이름 만드는 방식 |
| `--env-table FILE` | `출력.envs.tex` | 환경 대응표 파일 |
| `--env-in-preamble` | | `\newenvironment` 목록을 front matter 에도 넣음 |
| `--env-input` | | front matter 의 `preamble+:`에 `\input{출력파일.envs.tex}` 를 넣음 (경로는 출력 파일 기준) |
| `--custompkg PKGS` | | `\usepackage{…}`를 더할 패키지(쉼표로 구분) |
| `--no-preamble` | | 수식용 front matter 를 넣지 않음 |
| `--display {auto,none}` | `auto` | 디스플레이 수식 추정 |
| `--display-style {brackets,dollars}` | `brackets` | `\[ \]` 또는 `$$` |
| `--display-threshold N` | | 디스플레이 추정 점수 문턱 (최대 6) |
| `--image-width W` | `0.75\linewidth` | `fixed`일 때 그림 폭 |
| `--image-size {auto,fixed}` | `auto` | 그림 폭 정하는 방식 |
| `--image-max X` | 0.75 | `auto`일 때 폭 상한 |
| `--image-dir DIR` | 출력과 같은 폴더 | 그림 저장 폴더(출력 파일 기준) |
| `--image-prefix S` | | 그림 파일 이름 앞에 붙일 글 |
| `--no-pillow` | | Pillow 를 쓰지 않음 |
| `--no-crop` | | 그림 잘라내기 정보를 무시 |
| `--no-table-conversion` | 끔 | 표를 변환하지 않고 칸 안의 글만 칸 순서대로 평문단으로 남김 (별칭 `--table-conversion-false`) |
| `--notes-at-end` | 끔 | 각주·미주를 문서 끝에 평문단으로 모음 (아래 "각주와 미주") |
| `--footnotes {ref,inline,drop}` | `ref` | 각주 출력 방식 |
| `--endnotes {ref,collect,drop}` | `ref` | `[^en1]{end}` 표지와 정의 / 문서 끝에 번호만 모음 / 버림 |
| `--endnote-break S` | `\newpage` | `collect` 일 때 미주 앞 줄 |
| `--long-table F` | `0.7` | 내용으로 조판한 추정 높이가 본문 높이의 F 배 이상이면 표 끝에 `{env=long}` (0이면 끔) |
| `--long-table-rows N` | `30` | 행이 N 개 이상이어도 `{env=long}` (0이면 끔) |
| `--no-inline-marks` | | 글자 서식 인라인 마크업을 내지 않음 |
| `--sans-fonts NAMES` | | sans 로 볼 서체 이름 조각을 쉼표로 더 지정 |
| `--font-report FILE` | `출력파일.fonts.md` | 실제 쓰인 서체 보고서를 쓸 파일 |
| `--layout [FILE]` | 꺼짐 (`출력파일.layout.json`) | 쪽 설정을 JSON 으로 기록. 본문 md 는 달라지지 않음 (아래 참고) |
| `--keep-linebreaks` | | 한글의 강제 줄바꿈(Shift+Enter)을 마크다운 줄바꿈(줄 끝 두 칸)으로 남김. 기본은 공백으로 이어 붙임 |
| `--no-para-numbers` | | 자동 문단 번호를 붙이지 않음 |
| `--table {auto,pipe,grid,tblr}` | `auto` | 표를 내는 방식 (위 "표" 참조) |
| `--tblr-args="…"` | | tblr 표를 만들 때 hwpx2tblr 에 넘길 옵션 |
| `--no-grid-tables` | | `auto`에서 병합 칸이 있는 표를 grid 표로 내지 않음 (tblr 로 넘어감) |
| `--grid-max-cols N` | `12` | grid 표로 내는 표의 열 수 상한 |
| `--no-cell-text` | | 변환 못 한 표의 셀 글을 내지 않음 |
| `--show-empty-shapes` | | 글 없는 도형도 자리 표시 |
| `--report` | | 변환 통계와 경고를 표준 오류로 보고 (`-o`를 주면 항상 보고) |

## 파일 구성

| 파일 | 설명 |
|---|---|
| `hwpx2ndhmd.py` | 본체 (명령줄 도구) |
| `hwpx2tblr.py` | 표 → tabularray 변환기 (`--table tblr`가 불러 씀. [hwpx2tblr](../hwpx2tblr)의 같은 파일이며 단독으로도 돈다) |
| `tests/` | 시험 (`python3 -m unittest discover -s tests`; ndhmd4tex.py 와 xelatex 가 있으면 조판까지 확인. 환경변수 `NDHMD4TEX`로 위치 지정) |
| `hwpeq.py` | 한컴 수식 → LaTeX 변환기 (단독으로 `import hwpeq; hwpeq.convert(…)`로도 쓸 수 있음) |
| `hwpeq_tables.py` | 명령 이름 표 (`gen/gen_tables.py`가 만든 것이라 직접 고치지 않음) |
| `gen/gen_tables.py` | rhwp 의 `symbols.rs`에서 `hwpeq_tables.py`를 만드는 생성기 (실행에만 `pylatexenc` 필요) |
| `gen/gen_mathsyntax.py` | `mathsyntax.md`를 만드는 생성기 |
| `mathsyntax.md` | 한컴 수식 → LaTeX 대조표 |
| `CHANGELOG.md` | 변경 내역 |
| `LICENSE` | 이 저장소의 MIT 라이선스 (Copyright (c) 2026 Nova de Hi) |
| `LICENSE.rhwp` | rhwp 의 MIT 라이선스 전문 |

## 아직 안 된 것, 확인하지 못한 것

- **ndhmd4tex 에서 확인하지 못한 것**: 디스플레이 수식을 `\[`·`\]`가 각각 한 줄로 쓴 모양, `collect` 일 때 미주 앞의 `\newpage` 줄, 표·도형 자리 표시 주석의 모양. pandoc 방식 각주, 표 안의 `\|`, `:::` 중첩, 환경 이름의 글자 제한은 ndhmd4tex 쪽 사정을 알고 맞춘 것입니다.
- **한컴 화면과의 비교**: 수식 변환 규칙(첨자 인자의 범위, `over`의 결합 범위 등)은 rhwp 소스를 근거로 했고 한컴 화면과 하나하나 대조하지는 않았습니다.
- **문단 번호 재시작**: 번호는 번호 정의마다 이어서 셉니다. 한글에서 번호가 다시 시작되는 표시가 있는 문서는 번호가 어긋날 수 있습니다.
- **글자 모양**: 서체 계열·굵게·기울임·취소선·밑줄·강조점만 옮깁니다. 색, 크기, 자간, 위·아래 첨자는 옮기지 않습니다. 표·글상자 안, 헤딩에는 표시를 붙이지 않습니다.
- **글머리표**: 글자로 입력한 `•`, `=>`, `※` 같은 줄은 목록으로 바꾸지 않습니다.
- **연속된 디스플레이 수식**은 하나의 `aligned`/`align`으로 합치지 않습니다.
- **grid 표의 모양**: 칸 안의 글이 아주 길어도 낱말이 긴 한 덩어리면 줄이 길어집니다. 병합 칸의 세로 정렬·테두리 굵기 같은 서식은 보지 않습니다. 그림이나 중첩 표가 든 표는 grid 로 낼 수 없어 `auto`에서는 tblr 로 갑니다.
- **머리말·꼬리말** 같은 컨트롤 개체는 변환하지 않습니다.
- 마크다운 특수문자(`~`, `*`, `_` 등)는 줄 첫머리와 `]` 뒤 말고는 이스케이프하지 않습니다.

## 감사와 라이선스

- 한컴 수식의 명령 이름 표, 토큰 분리와 첨자·`over` 규칙은 [rhwp](https://github.com/edwardkim/rhwp)(MIT License, Copyright (c) 2025-2026 Edward Kim)를 참고하거나 가져왔습니다. 라이선스 전문은 `LICENSE.rhwp`에 있습니다.
- 이 저장소는 MIT 라이선스입니다(`LICENSE`).
