# -*- coding: utf-8 -*-
"""mathsyntax.md (한컴 수식 -> LaTeX 대조표)를 만든다.  python gen/gen_mathsyntax.py > mathsyntax.md
'변환 결과'는 손으로 쓴 것이 아니라 hwpeq.py 를 실제로 돌려 얻는다 (기호표는 hwpeq_tables.py)."""
import os, sys, html, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import hwpeq
from hwpeq_tables import TABLES as T


def code(s):
    return '<code>' + html.escape(s, quote=False).replace('|', '&#124;').replace('`', '&#96;') + '</code>'


def conv(s):
    hwpeq.WARN.clear()
    return hwpeq.convert(s)


# (한컴 수식, 비고)
EXAMPLES = [
 ('첨자', [
  ('a_1 + b^2', ''),
  ('x_{i+1}^{n}', '아래·위 첨자 함께'),
  ('x^{n+1}', '중괄호로 묶은 인자'),
  ('x^2 +1', '공백에서 첨자 인자가 끝남'),
  ('x^2+1', '붙여 쓰면 `2+1` 전체가 위첨자 (한글에서 확인함)'),
  ('sum_i=1^n a_i', '`_`의 인자는 반대쪽 첨자 `^` 앞까지'),
  ('sum_{i=1}^n a_i', ''),
  ('2^{-k}', ''),
  ('e^(x+1) y', '소괄호 묶음은 한 덩어리'),
  ('a_n ^2', '첨자 사이의 공백은 무시'),
 ]),
 ('분수·나눗셈', [
  ('{a+b} over {c}', '`over`는 직전 원소와 직후 원소를 묶는다'),
  ('a over b', ''),
  ('x+1 over 2', '붙여 쓴 `x+1`이 통째로 분자 (한글에서 확인함)'),
  ('x + 1 over 2', '띄어 쓰면 직전 원소(`1`)만 분자 (한글에서 확인함)'),
  ('a+b over c+d', '분모도 공백 전까지 붙은 것 모두'),
  ('(a+b) over c', '9글자 이하면 괄호가 있어도 덩어리 전체 (한글에서 확인함)'),
  ('f(a)-f(b) over f(c)', '9글자 (한글에서 확인함)'),
  ('f(x+h)-f(x) over h', '붙은 덩어리가 10글자 이상이면 9글자 뒤에서 끊어 읽어, 분자가 `x)`뿐이 되고 괄호가 어긋남 (한글에서 확인함)'),
  ('{f(x+h)-f(x)} over h', '`{…}`로 묶으면 안전'),
  ('f(2x)-f(x) over h', '끊김은 글자 수만 보며 괄호와 무관 (한글에서 확인함)'),
  ('abcdefghijkl over z', '글자·숫자·연산자 구분 없이 9글자 (한글에서 확인함)'),
  ('a+b+c+d+e+f+g over z', '(한글에서 확인함)'),
  ('1234567890 over z', '(한글에서 확인함)'),
  ('1234567890123 over abcdefgbijklmnob', '분모도 9글자까지만 잡고 나머지는 분수 밖 (한글에서 확인함)'),
  ('{x+1} over 2', ''),
  ('{1 over 2} over 3', ''),
  ('a atop b', '`atop`: 분수선 없는 위아래 쌓기'),
  ('{n} choose {k}', '조합 모양'),
 ]),
 ('근호', [
  ('sqrt x', ''),
  ('sqrt {x+1}', ''),
  ('sqrt 2+3+x^n+1', '붙여 쓴 덩어리 전체가 근호 안 (`over`와 같은 규칙)'),
  ('sqrt 2+3 + x', '공백에서 끝남'),
  ('sqrt abcdefghijkl', '`sqrt`도 9글자까지만 (한글에서 확인함)'),
  ('root 1111111111 of 0', '지수가 9글자를 넘으면 `of`가 붙지 못해 그냥 변수 `of`가 됨 (한글에서 확인함)'),
  ('root 111111111 of 000000000000', '`root … of`도 지수·근호 안 모두 9글자까지 (한글에서 확인함)'),
  ('sqrt {3} of {x+1}', 'n제곱근 (`{n} of {x}`)'),
  ('root 3 of x', 'n제곱근 (`root n of x`)'),
 ]),
 ('그리스 문자·기호', [
  ('alpha beta gamma', '소문자는 대소문자를 구분한다'),
  ('Gamma Delta Omega', ''),
  ('INF', '`inf`도 ∞ (함수 inf 가 아님)'),
  ('{partial f} over {partial x}', '편미분 (분자·분모를 `{…}`로 묶어야 함)'),
  ('partial x+1', '`partial`은 인자를 받지 않는 기호 (한글에서 확인함)'),
  ('partial y+c over partial x', '묶지 않으면 분자는 `y+c`, 분모는 `partial` 하나뿐 (한글에서 확인함)'),
  ('nabla times F', ''),
  ('forall x in A', ''),
  ('exists y', ''),
  ('therefore', ''),
 ]),
 ('연산·관계', [
  ('a times b div c', ''),
  ('a PLUSMINUS b', '±  (`pm`은 한컴 키워드가 아니라서 변수 글자로 읽힙니다)'),
  ('a MINUSPLUS b', '∓'),
  ('a le b ge c ne d', '`LEQ`·`GEQ`·`NEQ` 도 같다'),
  ('a LEQ b', ''),
  ('a <= b', '기호 그대로 쓴 `<=`, `>=`, `!=` 도 변환'),
  ('a approx b', ''),
  ('a sim b', ''),
  ('a propto b', ''),
  ('A subset B', ''),
  ('A cup B cap C', ''),
  ('a cdot b', ''),
  ('1 cdots n', ''),
 ]),
 ('큰 연산자·극한', [
  ('sum_{k=1}^n k', ''),
  ('prod_{k=1}^n a_k', ''),
  ('int_0^1 f(x) dx', '적분 기호는 위·아래 첨자를 옆에 붙인다'),
  ('oint_C F cdot dr', ''),
  ('lim_{x->0} {sin x} over x', ''),
  ('lim_{n->inf} a_n', ''),
  ('BIGCUP_{i=1}^n A_i', '큰 ∪. 소문자 `bigcup`은 rhwp 표에서 작은 ∪ 로 정의되어 있어 그대로 따랐습니다'),
  ('BIGCAP_{i=1}^n A_i', ''),
 ]),
 ('함수', [
  ('sin x + cos x', ''),
  ('log_2 x', ''),
  ('ln x', ''),
  ('max(a,b)', ''),
  ('sinx', '붙여 쓴 함수 이름도 나눈다'),
 ]),
 ('장식', [
  ('hat x', ''),
  ('vec v', ''),
  ('bar x', ''),
  ('bar x+y', '붙여 쓴 덩어리 전체에 줄 (한글에서 확인함)'),
  ('bar x + y', '공백에서 끝남 (한글에서 확인함)'),
  ('bar abcdefghijkl', '`bar`도 9글자까지만 (한글에서 확인함)'),
  ('tilde x', ''),
  ('dot x', ''),
  ('ddot x', ''),
  ('underline x', ''),
  ('overline {AB}', ''),
  ("f prime (x)", ''),
 ]),
 ('괄호 (LEFT/RIGHT)', [
  ('LEFT ( a+b RIGHT )', '크기가 자동으로 맞는 괄호'),
  ('LEFT [ a RIGHT ]', ''),
  ('LEFT { a RIGHT }', ''),
  ('LEFT | x RIGHT |', '절댓값'),
  ('LEFT ∥ x RIGHT ∥', '문자 그대로 쓴 `∥`·`‖` → `\\Vert`'),
  ('LEFT < u,v RIGHT >', '`<`·`>`가 구분 기호이면 꺾쇠 (내적)'),
  ('LEFT LANGLE u,v RIGHT RANGLE', ''),
  ('LEFT lfloor x RIGHT rfloor', ''),
  ('LANGLE u,v RANGLE', 'LEFT/RIGHT 없이 쓰면 크기 자동 조절 없음'),
  ('LEFT { x LEFT | f(x)=k RIGHT }', '집합 {x | …}: 짝 없는 안쪽 `LEFT |`는 `\\middle|`'),
  ('LEFT ( x', '짝 없는 LEFT: 뒤에 `\\right.` 를 붙이고 경고'),
  ('x RIGHT )', '짝 없는 RIGHT: 앞에 `\\left.` 를 붙이고 경고'),
 ]),
 ('행렬·경우·정렬', [
  ('matrix{a & b # c & d}', '`&` 칸, `#` 줄'),
  ('pmatrix{a & b # c & d}', '소괄호 행렬'),
  ('bmatrix{a & b # c & d}', '대괄호 행렬'),
  ('dmatrix{a & b # c & d}', '`|…|` 행렬식 (한컴의 DMATRIX)'),
  ('matrix{a && b # c & d}', '행렬에서 `&&`는 빈 칸 하나 (그대로 둔다)'),
  ('cases{x^2 & (x>0) # 0 & (x<=0)}', ''),
  ('cases{x^2 && (x>0) # 0 & (x<=0)}', '`cases`의 `&&`는 `&` 하나로'),
  ('eqalign{a &= b+c # &= d}', ''),
  ('pile{a # b # c}', '가운데 정렬 쌓기'),
 ]),
 ('글꼴·공백·문자열', [
  ('rm AB it x', '`rm`·`it`·`bold`는 이후 전체에 적용되는 전환 (한글에서 확인함)'),
  ('bold v', ''),
  ('a`b', '`` ` `` : 가는 공백'),
  ('a~b', '`~` : 공백'),
  ('"hello" x', '따옴표 안은 글자 그대로. 기본은 이탤릭 (한글에서 확인함)'),
  ('rm "hello" x', '`rm`이면 로만체'),
  ('"inf"_{x in A} f(x)', '`inf`는 무한대 기호이므로 인피멈은 따옴표 글로 쓰는데, 이탤릭이 됨 (한글에서 확인함)'),
  ('rm "inf"_{x in A} f(x)', '`rm`은 전역이라 뒤의 `x`, `f`도 모두 로만체 (한글에서 확인함)'),
  ('rm "inf" rm "sup" f', '`rm "inf"`·`rm "sup"`·`rm "liminf"`·`rm "limsup"`이 연산자 `\\inf`·`\\sup`·`\\liminf`·`\\limsup` (한글에서 확인함)'),
  ('x 가 y', '한글 등은 `\\text{…}`'),
  ('95 %', 'LaTeX 특수문자 `%` `$`는 수식 안에서 `\\%` `\\$`로 이스케이프 (ndhmd4tex 는 수식 안을 그대로 둔다)'),
  ('"50% of $x_1$"', '따옴표 글 안의 `% $ # & _ ^ ~ { } \\`도 이스케이프'),
  ('a -> b', ''),
  ('a rarrow b', ''),
  ('a lrarrow b', ''),
 ]),
]


def row(*cells):
    return '| ' + ' | '.join(cells) + ' |'


def main():
    out = []
    A = out.append
    A('# 수학식 표현 대조표 (한컴 수식 → LaTeX)')
    A('')
    A('hwpx2ndhmd 0.0.10 (`hwpeq.py`)이 한컴 수식 편집기의 스크립트를 LaTeX로 바꾸는 방식을 정리한 표입니다.')
    A('"변환 결과" 열은 손으로 쓴 것이 아니라 `gen/gen_mathsyntax.py`가 `hwpeq.py`를 실제로 돌려 만든 값입니다.')
    A('')
    A('명령 이름의 뼈대(그리스 문자·기호·연산자·화살표·괄호·함수 표)는 [rhwp](https://github.com/edwardkim/rhwp)(MIT License, Copyright (c) 2025-2026 Edward Kim)의 `symbols.rs`에서 가져왔고, 첨자 인자의 범위나 `over`의 결합 범위 같은 규칙도 rhwp의 파서를 따랐습니다. 한컴 수식 문법은 Unix `eqn`(troff 전처리기)의 계통이라고 합니다(한글 개발자의 증언에 따름). `over`의 결합 범위나 `sup`·`over`의 우선순위처럼 애매한 규칙은 `eqn` 매뉴얼을 참고할 수 있습니다. 한컴 화면과 일대일로 비교해 본 것은 아니며, 사용자가 한글에서 직접 확인한 규칙에는 "한글에서 확인함"이라고 적었습니다.')
    A('')
    A('## 목차')
    A('')
    A('1. [변환 규칙 요약](#변환-규칙-요약)')
    A('2. [예시 대조표](#예시-대조표)')
    A('3. [명령 이름 전체 표](#명령-이름-전체-표)')
    A('')
    A('## 변환 규칙 요약')
    A('')
    for t in [
        '**중괄호 억제.** 필요한 곳에만 중괄호를 씁니다. 한 글자 첨자는 `x^2`, 두 글자 이상은 `x^{n+1}`처럼 쓰고, `{…}` 그룹은 첨자의 밑이 될 때만 괄호로 감쌉니다.',
        '**첨자 인자.** `{…}`가 아니면 공백, 닫는 괄호(`)`·`]`·`}`), `RIGHT`, 반대쪽 첨자 앞까지 붙은 토큰 전부가 인자입니다. 그래서 `x^2+1`은 `x^{2+1}`, `sum_i=1^n`은 `\\sum_{i=1}^n`이 됩니다. 한컴 화면에서 의도와 다르게 보이는 수식이었다면 변환 결과도 같게 나옵니다.',
        '**OVER·ATOP.** 분자는 앞쪽의, 공백으로 끊기지 않은 한 덩어리이고 분모는 뒤쪽의 같은 덩어리입니다(`x+1 over 2`는 `(x+1)/2`, `x + 1 over 2`는 `x+1/2`). `{…}`로 시작하면 그 묶음만이 인자입니다. 한글의 한계로, 공백 없이 붙은 덩어리가 10글자 이상이면 9글자 뒤에서 끊어 읽습니다. 분자는 10번째 글자부터만, 분모·`sqrt`·장식 명령(`bar`, `hat` 등)·`root … of`의 인자는 처음 9글자만 잡고 나머지는 밖에 남습니다(`f(x+h)-f(x) over h` → `f(x+h)-f(\\frac{x)}{h}`). 글자 수만 세고 괄호·연산자와는 무관합니다. 긴 식은 `{…}`로 묶으십시오. 20글자 이상에서 9글자마다 끊는지는 확인하지 못했습니다. `root`에 붙지 못한 `of`는 그냥 변수가 됩니다(괄호를 낀 식은 `{…}`로 묶으십시오). `sqrt`, `root … of`와 장식 명령(`bar`, `hat`, `vec`, `underline` 등)의 인자도 같은 규칙입니다(`sqrt 2+3` → `\\sqrt{2+3}`). 덩어리 범위를 분명히 하려면 `{…}`로 묶으십시오.',
        '**글꼴 전환.** `rm`, `it`, `bold`는 중괄호로 끊기지 않는 전역 전환입니다.',
        '**대소문자.** 그리스 문자와 화살표 이름은 대소문자를 구분합니다(`alpha`와 `Alpha`는 다름). 그 밖의 기호·연산자·함수는 대문자로 한 번 더 찾습니다(`times`와 `TIMES` 모두 가능).',
        '**붙여 쓴 키워드.** `sinx`, `overa`, `leqb`처럼 붙은 이름은 알려진 키워드 단위로 나눕니다.',
        '**`&`와 `#`.** 구조 안에서 `&`는 칸 구분, `#`은 줄 구분입니다. `matrix`류는 `&` 하나가 칸 하나이고 `&&`는 빈 칸입니다. `cases`는 한 줄의 첫 `&` 묶음(`&`, `&&` 모두)을 `&` 하나로 합치고 나머지는 간격으로 바꿉니다. `eqalign`은 첫 `&` 묶음이 정렬 위치이고 `&&`이면 간격을 더합니다. 구조 밖의 `&`는 LaTeX 오류를 막기 위해 간격 `\\quad`로 바꿉니다.',
        '**LEFT/RIGHT 짝 보정.** 짝이 맞지 않는 `\\left`·`\\right`는 컴파일 오류가 되므로 고칩니다. (1) `LEFT { x LEFT | … RIGHT }`처럼 짝 없는 `LEFT |`는 `\\middle|`로, (2) 구조(`cases` 등)의 닫는 `}`가 `RIGHT`보다 앞에 있으면 `RIGHT`를 구조 안으로 끌어들이고, (3) 그래도 남는 짝 없는 `\\right`는 앞에 `\\left.`를, 짝 없는 `\\left`는 뒤에 `\\right.`를 붙입니다. 보정한 수식은 변환 중 경고로 보고합니다.',
        '**모르는 명령.** 키워드로는 알지만 해석하지 못한 명령은 `\\text{?이름}`으로 남기고, 변환이 끝난 뒤 목록을 보고합니다. 키워드 표에 없는 영문 단어는 변수 이름으로 읽혀 글자 그대로 나옵니다(예: `pm`).',
        '**`inf`.** 함수가 아니라 무한대(`\\infty`)입니다.',
    ]:
        A('- ' + t)
    A('')
    A('## 예시 대조표')
    A('')
    unknown = []
    for sec, rows in EXAMPLES:
        A('### ' + sec)
        A('')
        A(row('한컴 수식', '변환 결과 (LaTeX)', '비고'))
        A(row('---', '---', '---'))
        for src, note in rows:
            hwpeq.UNKNOWN.clear()
            r = conv(src)
            if hwpeq.UNKNOWN: unknown.append((src, sorted(hwpeq.UNKNOWN)))
            A(row(code(src), code(r), note.replace('|', '&#124;')))
        A('')
    if unknown:
        sys.stderr.write('알 수 없는 명령이 든 예시: %r\n' % unknown)
    A('## 명령 이름 전체 표')
    A('')
    A('한컴 이름이 여러 개인 항목(별칭)은 한 줄에 모았습니다. 이름의 대소문자 규칙은 위 규칙 요약을 보세요.')
    A('')
    titles = [('GREEK_LOWER', '그리스 소문자'), ('GREEK_UPPER', '그리스 대문자 (라틴 문자와 같은 모양은 그 문자로 나옵니다)'),
              ('SPECIAL_SYMBOLS', '특수 기호'), ('OPERATORS', '연산자·관계 기호'), ('BIG_OPERATORS', '큰 연산자'),
              ('ARROWS', '화살표'), ('BRACKETS', '괄호 기호 (LEFT/RIGHT 뒤에 쓰는 이름)'), ('FUNCTIONS', '함수 이름')]
    for key, title in titles:
        d = T[key]
        groups = collections.OrderedDict()
        for k, v in d.items(): groups.setdefault(v, []).append(k)
        A('### %s (%d개)' % (title, len(d)))
        A('')
        A(row('LaTeX', '한컴 이름'))
        A(row('---', '---'))
        for v, ks in groups.items():
            A(row(code(v), ', '.join(code(k) for k in ks)))
        A('')
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
