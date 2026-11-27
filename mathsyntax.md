# 수학식 표현 대조표 (한컴 수식 → LaTeX)

hwpx2ndhmd 0.0.10 (`hwpeq.py`)이 한컴 수식 편집기의 스크립트를 LaTeX로 바꾸는 방식을 정리한 표입니다.
"변환 결과" 열은 손으로 쓴 것이 아니라 `gen/gen_mathsyntax.py`가 `hwpeq.py`를 실제로 돌려 만든 값입니다.

명령 이름의 뼈대(그리스 문자·기호·연산자·화살표·괄호·함수 표)는 [rhwp](https://github.com/edwardkim/rhwp)(MIT License, Copyright (c) 2025-2026 Edward Kim)의 `symbols.rs`에서 가져왔고, 첨자 인자의 범위나 `over`의 결합 범위 같은 규칙도 rhwp의 파서를 따랐습니다. 한컴 수식 문법은 Unix `eqn`(troff 전처리기)의 계통이라고 합니다. `over`의 결합 범위나 `sup`·`over`의 우선순위처럼 애매한 규칙은 `eqn` 매뉴얼을 참고할 수 있습니다. 한컴 화면과 일대일로 비교해 본 것은 아니며, 사용자가 한글에서 직접 확인한 규칙에는 "한글에서 확인함"이라고 적었습니다.

## 목차

1. [변환 규칙 요약](#변환-규칙-요약)
2. [예시 대조표](#예시-대조표)
3. [명령 이름 전체 표](#명령-이름-전체-표)

## 변환 규칙 요약

- **중괄호 억제.** 필요한 곳에만 중괄호를 씁니다. 한 글자 첨자는 `x^2`, 두 글자 이상은 `x^{n+1}`처럼 쓰고, `{…}` 그룹은 첨자의 밑이 될 때만 괄호로 감쌉니다.
- **첨자 인자.** `{…}`가 아니면 공백, 닫는 괄호(`)`·`]`·`}`), `RIGHT`, 반대쪽 첨자 앞까지 붙은 토큰 전부가 인자입니다. 그래서 `x^2+1`은 `x^{2+1}`, `sum_i=1^n`은 `\sum_{i=1}^n`이 됩니다. 한컴 화면에서 의도와 다르게 보이는 수식이었다면 변환 결과도 같게 나옵니다.
- **OVER·ATOP.** 분자는 앞쪽의, 공백으로 끊기지 않은 한 덩어리이고 분모는 뒤쪽의 같은 덩어리입니다(`x+1 over 2`는 `(x+1)/2`, `x + 1 over 2`는 `x+1/2`). `{…}`로 시작하면 그 묶음만이 인자입니다. 한글의 한계로, 공백 없이 붙은 덩어리가 10글자 이상이면 9글자 뒤에서 끊어 읽습니다. 분자는 10번째 글자부터만, 분모·`sqrt`·장식 명령(`bar`, `hat` 등)·`root … of`의 인자는 처음 9글자만 잡고 나머지는 밖에 남습니다(`f(x+h)-f(x) over h` → `f(x+h)-f(\frac{x)}{h}`). 글자 수만 세고 괄호·연산자와는 무관합니다. 긴 식은 `{…}`로 묶으십시오. 20글자 이상에서 9글자마다 끊는지는 확인하지 못했습니다. `root`에 붙지 못한 `of`는 그냥 변수가 됩니다(괄호를 낀 식은 `{…}`로 묶으십시오). `sqrt`, `root … of`와 장식 명령(`bar`, `hat`, `vec`, `underline` 등)의 인자도 같은 규칙입니다(`sqrt 2+3` → `\sqrt{2+3}`). 덩어리 범위를 분명히 하려면 `{…}`로 묶으십시오.
- **글꼴 전환.** `rm`, `it`, `bold`는 중괄호로 끊기지 않는 전역 전환입니다.
- **대소문자.** 그리스 문자와 화살표 이름은 대소문자를 구분합니다(`alpha`와 `Alpha`는 다름). 그 밖의 기호·연산자·함수는 대문자로 한 번 더 찾습니다(`times`와 `TIMES` 모두 가능).
- **붙여 쓴 키워드.** `sinx`, `overa`, `leqb`처럼 붙은 이름은 알려진 키워드 단위로 나눕니다.
- **`&`와 `#`.** 구조 안에서 `&`는 칸 구분, `#`은 줄 구분입니다. `matrix`류는 `&` 하나가 칸 하나이고 `&&`는 빈 칸입니다. `cases`는 한 줄의 첫 `&` 묶음(`&`, `&&` 모두)을 `&` 하나로 합치고 나머지는 간격으로 바꿉니다. `eqalign`은 첫 `&` 묶음이 정렬 위치이고 `&&`이면 간격을 더합니다. 구조 밖의 `&`는 LaTeX 오류를 막기 위해 간격 `\quad`로 바꿉니다.
- **LEFT/RIGHT 짝 보정.** 짝이 맞지 않는 `\left`·`\right`는 컴파일 오류가 되므로 고칩니다. (1) `LEFT { x LEFT | … RIGHT }`처럼 짝 없는 `LEFT |`는 `\middle|`로, (2) 구조(`cases` 등)의 닫는 `}`가 `RIGHT`보다 앞에 있으면 `RIGHT`를 구조 안으로 끌어들이고, (3) 그래도 남는 짝 없는 `\right`는 앞에 `\left.`를, 짝 없는 `\left`는 뒤에 `\right.`를 붙입니다. 보정한 수식은 변환 중 경고로 보고합니다.
- **모르는 명령.** 키워드로는 알지만 해석하지 못한 명령은 `\text{?이름}`으로 남기고, 변환이 끝난 뒤 목록을 보고합니다. 키워드 표에 없는 영문 단어는 변수 이름으로 읽혀 글자 그대로 나옵니다(예: `pm`).
- **`inf`.** 함수가 아니라 무한대(`\infty`)입니다.

## 예시 대조표

### 첨자

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>a_1 + b^2</code> | <code>a_1+b^2</code> |  |
| <code>x_{i+1}^{n}</code> | <code>x_{i+1}^n</code> | 아래·위 첨자 함께 |
| <code>x^{n+1}</code> | <code>x^{n+1}</code> | 중괄호로 묶은 인자 |
| <code>x^2 +1</code> | <code>x^2+1</code> | 공백에서 첨자 인자가 끝남 |
| <code>x^2+1</code> | <code>x^{2+1}</code> | 붙여 쓰면 `2+1` 전체가 위첨자 (한글에서 확인함) |
| <code>sum_i=1^n a_i</code> | <code>\sum_{i=1}^na_i</code> | `_`의 인자는 반대쪽 첨자 `^` 앞까지 |
| <code>sum_{i=1}^n a_i</code> | <code>\sum_{i=1}^na_i</code> |  |
| <code>2^{-k}</code> | <code>2^{-k}</code> |  |
| <code>e^(x+1) y</code> | <code>e^{(x+1)}y</code> | 소괄호 묶음은 한 덩어리 |
| <code>a_n ^2</code> | <code>a_n^2</code> | 첨자 사이의 공백은 무시 |

### 분수·나눗셈

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>{a+b} over {c}</code> | <code>\frac{a+b}{c}</code> | `over`는 직전 원소와 직후 원소를 묶는다 |
| <code>a over b</code> | <code>\frac{a}{b}</code> |  |
| <code>x+1 over 2</code> | <code>\frac{x+1}{2}</code> | 붙여 쓴 `x+1`이 통째로 분자 (한글에서 확인함) |
| <code>x + 1 over 2</code> | <code>x+\frac{1}{2}</code> | 띄어 쓰면 직전 원소(`1`)만 분자 (한글에서 확인함) |
| <code>a+b over c+d</code> | <code>\frac{a+b}{c+d}</code> | 분모도 공백 전까지 붙은 것 모두 |
| <code>(a+b) over c</code> | <code>\frac{(a+b)}{c}</code> | 9글자 이하면 괄호가 있어도 덩어리 전체 (한글에서 확인함) |
| <code>f(a)-f(b) over f(c)</code> | <code>\frac{f(a)-f(b)}{f(c)}</code> | 9글자 (한글에서 확인함) |
| <code>f(x+h)-f(x) over h</code> | <code>f(x+h)-f(\frac{x)}{h}</code> | 붙은 덩어리가 10글자 이상이면 9글자 뒤에서 끊어 읽어, 분자가 `x)`뿐이 되고 괄호가 어긋남 (한글에서 확인함) |
| <code>{f(x+h)-f(x)} over h</code> | <code>\frac{f(x+h)-f(x)}{h}</code> | `{…}`로 묶으면 안전 |
| <code>f(2x)-f(x) over h</code> | <code>f(2x)-f(x\frac{)}{h}</code> | 끊김은 글자 수만 보며 괄호와 무관 (한글에서 확인함) |
| <code>abcdefghijkl over z</code> | <code>abcdefghi\frac{jkl}{z}</code> | 글자·숫자·연산자 구분 없이 9글자 (한글에서 확인함) |
| <code>a+b+c+d+e+f+g over z</code> | <code>a+b+c+d+e\frac{+f+g}{z}</code> | (한글에서 확인함) |
| <code>1234567890 over z</code> | <code>123456789\frac{0}{z}</code> | (한글에서 확인함) |
| <code>1234567890123 over abcdefgbijklmnob</code> | <code>123456789\frac{0123}{abcdefgbi}jklmnob</code> | 분모도 9글자까지만 잡고 나머지는 분수 밖 (한글에서 확인함) |
| <code>{x+1} over 2</code> | <code>\frac{x+1}{2}</code> |  |
| <code>{1 over 2} over 3</code> | <code>\frac{\frac{1}{2}}{3}</code> |  |
| <code>a atop b</code> | <code>{a\atop b}</code> | `atop`: 분수선 없는 위아래 쌓기 |
| <code>{n} choose {k}</code> | <code>\binom{n}{k}</code> | 조합 모양 |

### 근호

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>sqrt x</code> | <code>\sqrt{x}</code> |  |
| <code>sqrt {x+1}</code> | <code>\sqrt{x+1}</code> |  |
| <code>sqrt 2+3+x^n+1</code> | <code>\sqrt{2+3+x^{n+1}}</code> | 붙여 쓴 덩어리 전체가 근호 안 (`over`와 같은 규칙) |
| <code>sqrt 2+3 + x</code> | <code>\sqrt{2+3}+x</code> | 공백에서 끝남 |
| <code>sqrt abcdefghijkl</code> | <code>\sqrt{abcdefghi}jkl</code> | `sqrt`도 9글자까지만 (한글에서 확인함) |
| <code>root 1111111111 of 0</code> | <code>\sqrt{111111111}1of0</code> | 지수가 9글자를 넘으면 `of`가 붙지 못해 그냥 변수 `of`가 됨 (한글에서 확인함) |
| <code>root 111111111 of 000000000000</code> | <code>\sqrt[111111111]{000000000}000</code> | `root … of`도 지수·근호 안 모두 9글자까지 (한글에서 확인함) |
| <code>sqrt {3} of {x+1}</code> | <code>\sqrt[3]{x+1}</code> | n제곱근 (`{n} of {x}`) |
| <code>root 3 of x</code> | <code>\sqrt[3]{x}</code> | n제곱근 (`root n of x`) |

### 그리스 문자·기호

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>alpha beta gamma</code> | <code>\alpha\beta\gamma</code> | 소문자는 대소문자를 구분한다 |
| <code>Gamma Delta Omega</code> | <code>\Gamma\Delta\Omega</code> |  |
| <code>INF</code> | <code>\infty</code> | `inf`도 ∞ (함수 inf 가 아님) |
| <code>{partial f} over {partial x}</code> | <code>\frac{\partial f}{\partial x}</code> | 편미분 (분자·분모를 `{…}`로 묶어야 함) |
| <code>partial x+1</code> | <code>\partial x+1</code> | `partial`은 인자를 받지 않는 기호 (한글에서 확인함) |
| <code>partial y+c over partial x</code> | <code>\partial\frac{y+c}{\partial}x</code> | 묶지 않으면 분자는 `y+c`, 분모는 `partial` 하나뿐 (한글에서 확인함) |
| <code>nabla times F</code> | <code>\nabla\times F</code> |  |
| <code>forall x in A</code> | <code>\forall x\in A</code> |  |
| <code>exists y</code> | <code>\exists y</code> |  |
| <code>therefore</code> | <code>\therefore</code> |  |

### 연산·관계

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>a times b div c</code> | <code>a\times b\div c</code> |  |
| <code>a PLUSMINUS b</code> | <code>a\pm b</code> | ±  (`pm`은 한컴 키워드가 아니라서 변수 글자로 읽힙니다) |
| <code>a MINUSPLUS b</code> | <code>a\mp b</code> | ∓ |
| <code>a le b ge c ne d</code> | <code>a\le b\ge c\ne d</code> | `LEQ`·`GEQ`·`NEQ` 도 같다 |
| <code>a LEQ b</code> | <code>a\le b</code> |  |
| <code>a &lt;= b</code> | <code>a\le b</code> | 기호 그대로 쓴 `<=`, `>=`, `!=` 도 변환 |
| <code>a approx b</code> | <code>a\approx b</code> |  |
| <code>a sim b</code> | <code>a\sim b</code> |  |
| <code>a propto b</code> | <code>a\propto b</code> |  |
| <code>A subset B</code> | <code>A\subset B</code> |  |
| <code>A cup B cap C</code> | <code>A\cup B\cap C</code> |  |
| <code>a cdot b</code> | <code>a\cdot b</code> |  |
| <code>1 cdots n</code> | <code>1\cdots n</code> |  |

### 큰 연산자·극한

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>sum_{k=1}^n k</code> | <code>\sum_{k=1}^nk</code> |  |
| <code>prod_{k=1}^n a_k</code> | <code>\prod_{k=1}^na_k</code> |  |
| <code>int_0^1 f(x) dx</code> | <code>\int_0^1f(x)dx</code> | 적분 기호는 위·아래 첨자를 옆에 붙인다 |
| <code>oint_C F cdot dr</code> | <code>\oint_CF\cdot dr</code> |  |
| <code>lim_{x-&gt;0} {sin x} over x</code> | <code>\lim_{x\to 0}\frac{\sin x}{x}</code> |  |
| <code>lim_{n-&gt;inf} a_n</code> | <code>\lim_{n\to\infty}a_n</code> |  |
| <code>BIGCUP_{i=1}^n A_i</code> | <code>\bigcup_{i=1}^nA_i</code> | 큰 ∪. 소문자 `bigcup`은 rhwp 표에서 작은 ∪ 로 정의되어 있어 그대로 따랐습니다 |
| <code>BIGCAP_{i=1}^n A_i</code> | <code>\bigcap_{i=1}^nA_i</code> |  |

### 함수

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>sin x + cos x</code> | <code>\sin x+\cos x</code> |  |
| <code>log_2 x</code> | <code>\log_2x</code> |  |
| <code>ln x</code> | <code>\ln x</code> |  |
| <code>max(a,b)</code> | <code>\max (a,b)</code> |  |
| <code>sinx</code> | <code>\sin x</code> | 붙여 쓴 함수 이름도 나눈다 |

### 장식

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>hat x</code> | <code>\hat{x}</code> |  |
| <code>vec v</code> | <code>\vec{v}</code> |  |
| <code>bar x</code> | <code>\overline{x}</code> |  |
| <code>bar x+y</code> | <code>\overline{x+y}</code> | 붙여 쓴 덩어리 전체에 줄 (한글에서 확인함) |
| <code>bar x + y</code> | <code>\overline{x}+y</code> | 공백에서 끝남 (한글에서 확인함) |
| <code>bar abcdefghijkl</code> | <code>\overline{abcdefghi}jkl</code> | `bar`도 9글자까지만 (한글에서 확인함) |
| <code>tilde x</code> | <code>\tilde{x}</code> |  |
| <code>dot x</code> | <code>\dot{x}</code> |  |
| <code>ddot x</code> | <code>\ddot{x}</code> |  |
| <code>underline x</code> | <code>\underline{x}</code> |  |
| <code>overline {AB}</code> | <code>\overline{AB}</code> |  |
| <code>f prime (x)</code> | <code>f'(x)</code> |  |

### 괄호 (LEFT/RIGHT)

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>LEFT ( a+b RIGHT )</code> | <code>\left(a+b\right)</code> | 크기가 자동으로 맞는 괄호 |
| <code>LEFT [ a RIGHT ]</code> | <code>\left[a\right]</code> |  |
| <code>LEFT { a RIGHT }</code> | <code>\left\{a\right\}</code> |  |
| <code>LEFT &#124; x RIGHT &#124;</code> | <code>\left&#124;x\right&#124;</code> | 절댓값 |
| <code>LEFT ∥ x RIGHT ∥</code> | <code>\left\Vert x\right\Vert</code> | 문자 그대로 쓴 `∥`·`‖` → `\Vert` |
| <code>LEFT &lt; u,v RIGHT &gt;</code> | <code>\left\langle u,v\right\rangle</code> | `<`·`>`가 구분 기호이면 꺾쇠 (내적) |
| <code>LEFT LANGLE u,v RIGHT RANGLE</code> | <code>\left\langle u,v\right\rangle</code> |  |
| <code>LEFT lfloor x RIGHT rfloor</code> | <code>\left\lfloor x\right\rfloor</code> |  |
| <code>LANGLE u,v RANGLE</code> | <code>\langle u,v\rangle</code> | LEFT/RIGHT 없이 쓰면 크기 자동 조절 없음 |
| <code>LEFT { x LEFT &#124; f(x)=k RIGHT }</code> | <code>\left\{x\middle&#124;f(x)=k\right\}</code> | 집합 {x &#124; …}: 짝 없는 안쪽 `LEFT &#124;`는 `\middle&#124;` |
| <code>LEFT ( x</code> | <code>\left(x\right.</code> | 짝 없는 LEFT: 뒤에 `\right.` 를 붙이고 경고 |
| <code>x RIGHT )</code> | <code>\left.x\right)</code> | 짝 없는 RIGHT: 앞에 `\left.` 를 붙이고 경고 |

### 행렬·경우·정렬

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>matrix{a &amp; b # c &amp; d}</code> | <code>\begin{matrix}a&amp;b\\c&amp;d\end{matrix}</code> | `&` 칸, `#` 줄 |
| <code>pmatrix{a &amp; b # c &amp; d}</code> | <code>\begin{pmatrix}a&amp;b\\c&amp;d\end{pmatrix}</code> | 소괄호 행렬 |
| <code>bmatrix{a &amp; b # c &amp; d}</code> | <code>\begin{bmatrix}a&amp;b\\c&amp;d\end{bmatrix}</code> | 대괄호 행렬 |
| <code>dmatrix{a &amp; b # c &amp; d}</code> | <code>\begin{vmatrix}a&amp;b\\c&amp;d\end{vmatrix}</code> | `&#124;…&#124;` 행렬식 (한컴의 DMATRIX) |
| <code>matrix{a &amp;&amp; b # c &amp; d}</code> | <code>\begin{matrix}a&amp;&amp;b\\c&amp;d\end{matrix}</code> | 행렬에서 `&&`는 빈 칸 하나 (그대로 둔다) |
| <code>cases{x^2 &amp; (x&gt;0) # 0 &amp; (x&lt;=0)}</code> | <code>\begin{cases}x^2&amp;(x&gt;0)\\0&amp;(x\le 0)\end{cases}</code> |  |
| <code>cases{x^2 &amp;&amp; (x&gt;0) # 0 &amp; (x&lt;=0)}</code> | <code>\begin{cases}x^2&amp;(x&gt;0)\\0&amp;(x\le 0)\end{cases}</code> | `cases`의 `&&`는 `&` 하나로 |
| <code>eqalign{a &amp;= b+c # &amp;= d}</code> | <code>\begin{aligned}a&amp;=b+c\\&amp;=d\end{aligned}</code> |  |
| <code>pile{a # b # c}</code> | <code>\begin{matrix}a\\b\\c\end{matrix}</code> | 가운데 정렬 쌓기 |

### 글꼴·공백·문자열

| 한컴 수식 | 변환 결과 (LaTeX) | 비고 |
| --- | --- | --- |
| <code>rm AB it x</code> | <code>\mathrm{AB}x</code> | `rm`·`it`·`bold`는 이후 전체에 적용되는 전환 (한글에서 확인함) |
| <code>bold v</code> | <code>\mathbf{v}</code> |  |
| <code>a&#96;b</code> | <code>a\,b</code> | `` ` `` : 가는 공백 |
| <code>a~b</code> | <code>a\ b</code> | `~` : 공백 |
| <code>"hello" x</code> | <code>\textit{hello}x</code> | 따옴표 안은 글자 그대로. 기본은 이탤릭 (한글에서 확인함) |
| <code>rm "hello" x</code> | <code>\text{hello}\mathrm{x}</code> | `rm`이면 로만체 |
| <code>"inf"_{x in A} f(x)</code> | <code>\textit{inf}_{x\in A}f(x)</code> | `inf`는 무한대 기호이므로 인피멈은 따옴표 글로 쓰는데, 이탤릭이 됨 (한글에서 확인함) |
| <code>rm "inf"_{x in A} f(x)</code> | <code>\inf_{\mathrm{x}\in\mathrm{A}}\mathrm{f}(\mathrm{x})</code> | `rm`은 전역이라 뒤의 `x`, `f`도 모두 로만체 (한글에서 확인함) |
| <code>rm "inf" rm "sup" f</code> | <code>\inf\sup\mathrm{f}</code> | `rm "inf"`·`rm "sup"`·`rm "liminf"`·`rm "limsup"`이 연산자 `\inf`·`\sup`·`\liminf`·`\limsup` (한글에서 확인함) |
| <code>x 가 y</code> | <code>x\text{가}y</code> | 한글 등은 `\text{…}` |
| <code>95 %</code> | <code>95\%</code> | LaTeX 특수문자 `%` `$`는 수식 안에서 `\%` `\$`로 이스케이프 (ndhmd4tex 는 수식 안을 그대로 둔다) |
| <code>"50% of $x_1$"</code> | <code>\textit{50\% of \$x\_1\$}</code> | 따옴표 글 안의 `% $ # & _ ^ ~ { } \`도 이스케이프 |
| <code>a -&gt; b</code> | <code>a\to b</code> |  |
| <code>a rarrow b</code> | <code>a\rightarrow b</code> |  |
| <code>a lrarrow b</code> | <code>a\leftrightarrow b</code> |  |

## 명령 이름 전체 표

한컴 이름이 여러 개인 항목(별칭)은 한 줄에 모았습니다. 이름의 대소문자 규칙은 위 규칙 요약을 보세요.

### 그리스 소문자 (30개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>\alpha</code> | <code>alpha</code> |
| <code>\beta</code> | <code>beta</code> |
| <code>\gamma</code> | <code>gamma</code> |
| <code>\delta</code> | <code>delta</code> |
| <code>\varepsilon</code> | <code>epsilon</code> |
| <code>\epsilon</code> | <code>varepsilon</code> |
| <code>\zeta</code> | <code>zeta</code> |
| <code>\eta</code> | <code>eta</code> |
| <code>\theta</code> | <code>theta</code> |
| <code>\vartheta</code> | <code>vartheta</code> |
| <code>\iota</code> | <code>iota</code> |
| <code>\kappa</code> | <code>kappa</code> |
| <code>\lambda</code> | <code>lambda</code> |
| <code>\mu</code> | <code>mu</code> |
| <code>\nu</code> | <code>nu</code> |
| <code>\xi</code> | <code>xi</code> |
| <code>o</code> | <code>omicron</code> |
| <code>\pi</code> | <code>pi</code> |
| <code>\varpi</code> | <code>varpi</code> |
| <code>\rho</code> | <code>rho</code> |
| <code>\varrho</code> | <code>varrho</code> |
| <code>\sigma</code> | <code>sigma</code> |
| <code>\varsigma</code> | <code>varsigma</code> |
| <code>\tau</code> | <code>tau</code> |
| <code>\upsilon</code> | <code>upsilon</code> |
| <code>\varphi</code> | <code>phi</code> |
| <code>\phi</code> | <code>varphi</code> |
| <code>\chi</code> | <code>chi</code> |
| <code>\psi</code> | <code>psi</code> |
| <code>\omega</code> | <code>omega</code> |

### 그리스 대문자 (라틴 문자와 같은 모양은 그 문자로 나옵니다) (25개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>A</code> | <code>Alpha</code> |
| <code>B</code> | <code>Beta</code> |
| <code>\Gamma</code> | <code>Gamma</code> |
| <code>\Delta</code> | <code>Delta</code> |
| <code>E</code> | <code>Epsilon</code> |
| <code>Z</code> | <code>Zeta</code> |
| <code>H</code> | <code>Eta</code> |
| <code>\Theta</code> | <code>Theta</code> |
| <code>I</code> | <code>Iota</code> |
| <code>K</code> | <code>Kappa</code> |
| <code>\Lambda</code> | <code>Lambda</code> |
| <code>M</code> | <code>Mu</code> |
| <code>N</code> | <code>Nu</code> |
| <code>\Xi</code> | <code>Xi</code> |
| <code>O</code> | <code>Omicron</code> |
| <code>\Pi</code> | <code>Pi</code> |
| <code>P</code> | <code>Rho</code> |
| <code>\Sigma</code> | <code>Sigma</code> |
| <code>T</code> | <code>Tau</code> |
| <code>\Upsilon</code> | <code>Upsilon</code>, <code>varupsilon</code> |
| <code>\Phi</code> | <code>Phi</code> |
| <code>X</code> | <code>Chi</code> |
| <code>\Psi</code> | <code>Psi</code> |
| <code>\Omega</code> | <code>Omega</code> |

### 특수 기호 (47개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>\infty</code> | <code>INF</code> |
| <code>\aleph</code> | <code>ALEPH</code> |
| <code>\hbar</code> | <code>HBAR</code> |
| <code>\imath</code> | <code>IMATH</code> |
| <code>\jmath</code> | <code>JMATH</code> |
| <code>\ell</code> | <code>ELL</code>, <code>LITER</code> |
| <code>\wp</code> | <code>WP</code> |
| <code>\Im</code> | <code>IMAG</code>, <code>image</code> |
| <code>\Re</code> | <code>REIMAGE</code> |
| <code>\r{A}</code> | <code>ANGSTROM</code> |
| <code>\mho</code> | <code>MHO</code> |
| <code>\Omega</code> | <code>OHM</code> |
| <code>\cdots</code> | <code>CDOTS</code> |
| <code>\ldots</code> | <code>LDOTS</code>, <code>DOTS</code> |
| <code>\vdots</code> | <code>VDOTS</code> |
| <code>\ddots</code> | <code>DDOTS</code> |
| <code>\u{2003}</code> | <code>QUAD</code> |
| <code>\u{2003}\u{2003}</code> | <code>QQUAD</code> |
| <code>\u{2009}</code> | <code>THINSPACE</code> |
| <code>\u{205F}</code> | <code>MEDSPACE</code> |
| <code>\u{2004}</code> | <code>THICKSPACE</code> |
| <code></code> | <code>NEGSPACE</code> |
| <code>\u{2002}</code> | <code>ENSPACE</code> |
| <code>\triangle</code> | <code>TRIANGLE</code>, <code>BASE</code> |
| <code>\triangledown</code> | <code>TRIANGLED</code> |
| <code>\angle</code> | <code>ANGLE</code> |
| <code>\measuredangle</code> | <code>MSANGLE</code>, <code>RTANGLE</code> |
| <code>\sphericalangle</code> | <code>SANGLE</code> |
| <code>\perp</code> | <code>BOT</code> |
| <code>\top</code> | <code>TOP</code> |
| <code>\mathcal{L}</code> | <code>LAPLACE</code> |
| <code>{}^\circ\mathrm{C}</code> | <code>CENTIGRADE</code> |
| <code>{}^\circ\mathrm{F}</code> | <code>FAHRENHEIT</code> |
| <code>{}^\circ</code> | <code>DEG</code> |
| <code>'</code> | <code>prime</code> |
| <code>/</code> | <code>LSLANT</code> |
| <code>\\</code> | <code>RSLANT</code> |
| <code>@</code> | <code>ATT</code> |
| <code>\text{\textperthousand}</code> | <code>HUND</code> |
| <code>\text{\textpertenthousand}</code> | <code>THOU</code> |
| <code>\sharp</code> | <code>WELL</code> |
| <code>\mathrm{?}</code> | <code>BENZENE</code> |

### 연산자·관계 기호 (127개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>\times</code> | <code>TIMES</code>, <code>times</code> |
| <code>\div</code> | <code>DIV</code>, <code>DIVDE</code>, <code>DIVIDE</code>, <code>div</code> |
| <code>\pm</code> | <code>PLUSMINUS</code> |
| <code>\mp</code> | <code>MINUSPLUS</code> |
| <code>\cdot</code> | <code>CDOT</code>, <code>BULLET</code>, <code>cdot</code> |
| <code>\circ</code> | <code>CIRC</code>, <code>circ</code> |
| <code>*</code> | <code>AST</code> |
| <code>\star</code> | <code>STAR</code>, <code>star</code> |
| <code>\boxplus</code> | <code>DSUM</code> |
| <code>\ne</code> | <code>NEQ</code>, <code>!=</code>, <code>ne</code>, <code>neq</code> |
| <code>\le</code> | <code>LE</code>, <code>LEQ</code>, <code>&lt;=</code>, <code>le</code>, <code>leq</code> |
| <code>\ge</code> | <code>GE</code>, <code>GEQ</code>, <code>&gt;=</code>, <code>ge</code>, <code>geq</code> |
| <code>\ll</code> | <code>&lt;&lt;</code>, <code>ll</code> |
| <code>\gg</code> | <code>&gt;&gt;</code>, <code>gg</code> |
| <code>\lll</code> | <code>LLL</code>, <code>&lt;&lt;&lt;</code> |
| <code>\ggg</code> | <code>GGG</code>, <code>&gt;&gt;&gt;</code> |
| <code>\approx</code> | <code>APPROX</code>, <code>approx</code> |
| <code>\sim</code> | <code>SIM</code>, <code>sim</code> |
| <code>\simeq</code> | <code>SIMEQ</code>, <code>simeq</code> |
| <code>\cong</code> | <code>CONG</code>, <code>cong</code> |
| <code>\equiv</code> | <code>EQUIV</code>, <code>==</code>, <code>equiv</code> |
| <code>\asymp</code> | <code>ASYMP</code> |
| <code>\doteq</code> | <code>DOTEQ</code> |
| <code>\propto</code> | <code>PROPTO</code>, <code>propto</code> |
| <code>\cup</code> | <code>UNION</code>, <code>SMALLUNION</code>, <code>CUP</code>, <code>cup</code> |
| <code>\cap</code> | <code>INTER</code>, <code>SMALLINTER</code>, <code>CAP</code>, <code>cap</code> |
| <code>\subset</code> | <code>SUBSET</code>, <code>subset</code> |
| <code>\supset</code> | <code>SUPERSET</code>, <code>supset</code> |
| <code>\subseteq</code> | <code>SUBSETEQ</code>, <code>subseteq</code> |
| <code>\supseteq</code> | <code>SUPSETEQ</code>, <code>supseteq</code> |
| <code>\sqsubset</code> | <code>SQSUBSET</code> |
| <code>\sqsupset</code> | <code>SQSUPSET</code> |
| <code>\sqsubseteq</code> | <code>SQSUBSETEQ</code> |
| <code>\sqsupseteq</code> | <code>SQSUPSETEQ</code> |
| <code>\in</code> | <code>IN</code>, <code>in</code> |
| <code>\notin</code> | <code>NOTIN</code>, <code>notin</code> |
| <code>\ni</code> | <code>OWNS</code>, <code>NI</code>, <code>ni</code> |
| <code>\prec</code> | <code>PREC</code> |
| <code>\succ</code> | <code>SUCC</code> |
| <code>\forall</code> | <code>FORALL</code>, <code>forall</code> |
| <code>\exists</code> | <code>EXIST</code>, <code>exists</code> |
| <code>\neg</code> | <code>LNOT</code>, <code>lnot</code>, <code>neg</code> |
| <code>\wedge</code> | <code>WEDGE</code>, <code>LAND</code>, <code>wedge</code>, <code>land</code> |
| <code>\vee</code> | <code>VEE</code>, <code>LOR</code>, <code>vee</code>, <code>lor</code> |
| <code>\veebar</code> | <code>XOR</code> |
| <code>\partial</code> | <code>PARTIAL</code>, <code>partial</code> |
| <code>\varnothing</code> | <code>EMPTYSET</code>, <code>emptyset</code> |
| <code>\therefore</code> | <code>THEREFORE</code>, <code>therefore</code> |
| <code>\because</code> | <code>BECAUSE</code>, <code>because</code> |
| <code>::</code> | <code>IDENTICAL</code> |
| <code>\vdash</code> | <code>VDASH</code>, <code>vdash</code> |
| <code>\dashv</code> | <code>HLEFT</code> |
| <code>\forcesextra</code> | <code>MODELS</code>, <code>models</code> |
| <code>\dagger</code> | <code>DAGGER</code>, <code>dagger</code> |
| <code>\ddagger</code> | <code>DDAGGER</code>, <code>ddagger</code> |
| <code>\bigcirc</code> | <code>BIGCIRC</code> |
| <code>\diamond</code> | <code>DIAMOND</code>, <code>ISO</code> |
| <code>\nexists</code> | <code>nexists</code> |
| <code>\nabla</code> | <code>nabla</code> |
| <code>\infty</code> | <code>infty</code> |
| <code>\aleph</code> | <code>aleph</code> |
| <code>\oplus</code> | <code>oplus</code> |
| <code>\otimes</code> | <code>otimes</code> |
| <code>\perp</code> | <code>perp</code> |

### 큰 연산자 (50개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>\int</code> | <code>INT</code>, <code>INTEGRAL</code>, <code>SMALLINT</code>, <code>int</code> |
| <code>\iint</code> | <code>DINT</code>, <code>iint</code> |
| <code>\iiint</code> | <code>TINT</code>, <code>iiint</code> |
| <code>\oint</code> | <code>OINT</code>, <code>SMALLOINT</code>, <code>oint</code> |
| <code>\oiint</code> | <code>ODINT</code> |
| <code>\oiiint</code> | <code>OTINT</code> |
| <code>\sum</code> | <code>SUM</code>, <code>sum</code> |
| <code>\Sigma</code> | <code>SMALLSUM</code> |
| <code>\prod</code> | <code>PROD</code>, <code>SMALLPROD</code>, <code>prod</code> |
| <code>\coprod</code> | <code>COPROD</code>, <code>SMCOPROD</code>, <code>AMALG</code>, <code>coprod</code> |
| <code>\bigcup</code> | <code>BIGCUP</code> |
| <code>\bigcap</code> | <code>BIGCAP</code> |
| <code>\sqcup</code> | <code>SQCUP</code> |
| <code>\bigsqcup</code> | <code>BIGSQCUP</code> |
| <code>\sqcap</code> | <code>SQCAP</code> |
| <code>\bigsqcap</code> | <code>BIGSQCAP</code> |
| <code>\uplus</code> | <code>UPLUS</code> |
| <code>\biguplus</code> | <code>BIGUPLUS</code> |
| <code>\bigwedge</code> | <code>BIGWEDGE</code>, <code>bigwedge</code> |
| <code>\bigvee</code> | <code>BIGVEE</code>, <code>bigvee</code> |
| <code>\oplus</code> | <code>OPLUS</code>, <code>bigoplus</code> |
| <code>\bigoplus</code> | <code>BIGOPLUS</code> |
| <code>\otimes</code> | <code>OTIMES</code>, <code>bigotimes</code> |
| <code>\bigotimes</code> | <code>BIGOTIMES</code> |
| <code>\odot</code> | <code>ODOT</code> |
| <code>\bigodot</code> | <code>BIGODOT</code> |
| <code>\ominus</code> | <code>OMINUS</code>, <code>BIGOMINUS</code> |
| <code>\oslash</code> | <code>ODIV</code>, <code>BIGODIV</code>, <code>OSLASH</code> |
| <code>\cup</code> | <code>bigcup</code> |
| <code>\cap</code> | <code>bigcap</code> |

### 화살표 (40개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>\leftarrow</code> | <code>larrow</code>, <code>leftarrow</code>, <code>gets</code> |
| <code>\rightarrow</code> | <code>rarrow</code>, <code>rightarrow</code>, <code>to</code> |
| <code>\uparrow</code> | <code>uparrow</code> |
| <code>\downarrow</code> | <code>downarrow</code> |
| <code>\leftrightarrow</code> | <code>lrarrow</code>, <code>leftrightarrow</code> |
| <code>\updownarrow</code> | <code>udarrow</code> |
| <code>\Leftarrow</code> | <code>LARROW</code>, <code>Leftarrow</code> |
| <code>\Rightarrow</code> | <code>RARROW</code>, <code>Rightarrow</code>, <code>implies</code> |
| <code>\Uparrow</code> | <code>UPARROW</code> |
| <code>\Downarrow</code> | <code>DOWNARROW</code> |
| <code>\Leftrightarrow</code> | <code>LRARROW</code>, <code>iff</code>, <code>Leftrightarrow</code> |
| <code>\Updownarrow</code> | <code>UDARROW</code> |
| <code>\nwarrow</code> | <code>nwarrow</code>, <code>NWARROW</code> |
| <code>\nearrow</code> | <code>nearrow</code>, <code>NEARROW</code> |
| <code>\swarrow</code> | <code>swarrow</code>, <code>SWARROW</code> |
| <code>\searrow</code> | <code>searrow</code>, <code>SEARROW</code> |
| <code>\mapsto</code> | <code>mapsto</code> |
| <code>\hookleftarrow</code> | <code>hookleft</code> |
| <code>\hookrightarrow</code> | <code>hookright</code> |
| <code>\longrightarrow</code> | <code>longrightarrow</code> |
| <code>\longleftarrow</code> | <code>longleftarrow</code> |
| <code>\Longrightarrow</code> | <code>Longrightarrow</code> |
| <code>\Longleftarrow</code> | <code>Longleftarrow</code> |
| <code>\longmapsto</code> | <code>longmapsto</code> |
| <code>&#124;</code> | <code>vert</code> |
| <code>\Vert</code> | <code>VERT</code> |

### 괄호 기호 (LEFT/RIGHT 뒤에 쓰는 이름) (20개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>{</code> | <code>LBRACE</code>, <code>lbrace</code> |
| <code>}</code> | <code>RBRACE</code>, <code>rbrace</code> |
| <code>\lceil</code> | <code>LCEIL</code>, <code>lceil</code> |
| <code>\rceil</code> | <code>RCEIL</code>, <code>rceil</code> |
| <code>\lfloor</code> | <code>LFLOOR</code>, <code>lfloor</code> |
| <code>\rfloor</code> | <code>RFLOOR</code>, <code>rfloor</code> |
| <code>\langle</code> | <code>langle</code>, <code>LANGLE</code> |
| <code>\rangle</code> | <code>rangle</code>, <code>RANGLE</code> |
| <code>&#124;</code> | <code>lvert</code>, <code>rvert</code> |
| <code>\Vert</code> | <code>lVert</code>, <code>rVert</code> |

### 함수 이름 (34개)

| LaTeX | 한컴 이름 |
| --- | --- |
| <code>sin</code> | <code>sin</code> |
| <code>cos</code> | <code>cos</code> |
| <code>tan</code> | <code>tan</code> |
| <code>cot</code> | <code>cot</code> |
| <code>sec</code> | <code>sec</code> |
| <code>csc</code> | <code>csc</code> |
| <code>arcsin</code> | <code>arcsin</code> |
| <code>arccos</code> | <code>arccos</code> |
| <code>arctan</code> | <code>arctan</code> |
| <code>sinh</code> | <code>sinh</code> |
| <code>cosh</code> | <code>cosh</code> |
| <code>tanh</code> | <code>tanh</code> |
| <code>coth</code> | <code>coth</code> |
| <code>log</code> | <code>log</code> |
| <code>ln</code> | <code>ln</code> |
| <code>lg</code> | <code>lg</code> |
| <code>exp</code> | <code>exp</code> |
| <code>det</code> | <code>det</code> |
| <code>dim</code> | <code>dim</code> |
| <code>ker</code> | <code>ker</code> |
| <code>hom</code> | <code>hom</code> |
| <code>arg</code> | <code>arg</code> |
| <code>deg</code> | <code>deg</code> |
| <code>gcd</code> | <code>gcd</code> |
| <code>lcm</code> | <code>lcm</code> |
| <code>max</code> | <code>max</code> |
| <code>min</code> | <code>min</code> |
| <code>mod</code> | <code>mod</code> |
| <code>sup</code> | <code>sup</code> |
| <code>inf</code> | <code>inf</code> |
| <code>lim</code> | <code>lim</code> |
| <code>lim sup</code> | <code>limsup</code> |
| <code>lim inf</code> | <code>liminf</code> |
| <code>Pr</code> | <code>Pr</code> |

