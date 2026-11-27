# -*- coding: utf-8 -*-
"""한컴 수식 스크립트 -> LaTeX 변환기

규칙 출처: rhwp (https://github.com/edwardkim/rhwp, MIT License, Copyright (c) 2025-2026 Edward Kim)
  - 명령 이름 표: hwpeq_tables.py (rhwp symbols.rs 에서 생성)
  - 토큰 분리(붙여 쓴 키워드), OVER/ATOP 결합 범위, rm/it/bold 전역 전환, 구조 명령(SQRT, MATRIX, CASES, EQALIGN, PILE)의 해석 규칙
방침: 중첩 중괄호를 만들지 않는다 (필요한 곳에만 괄호를 쓴다).
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwpeq_tables import TABLES as T

__version__ = '0.0.10'

UNKNOWN = set()          # 해석하지 못한 명령 (호출한 쪽에서 보고용)
WARN = []                # (수식 원문, 메시지) — \left/\right 짝 보정 등 호출한 쪽에서 보고용
ORDER = ['GREEK_LOWER', 'GREEK_UPPER', 'SPECIAL_SYMBOLS', 'OPERATORS', 'BIG_OPERATORS', 'ARROWS', 'BRACKETS']
UPPER_FALLBACK = ['SPECIAL_SYMBOLS', 'OPERATORS', 'BIG_OPERATORS', 'BRACKETS']   # 화살표·그리스 문자는 대소문자 구분
STRUCT = {'OVER', 'ATOP', 'SQRT', 'ROOT', 'OF', 'LEFT', 'RIGHT', 'MATRIX', 'PMATRIX', 'BMATRIX', 'DMATRIX', 'VMATRIX',
          'CASES', 'EQALIGN', 'PILE', 'LPILE', 'RPILE', 'CHOOSE', 'BINOM', 'SUB', 'SUP', 'LIM'}
DECO = {'hat': r'\hat', 'check': r'\check', 'tilde': r'\tilde', 'acute': r'\acute', 'grave': r'\grave', 'dot': r'\dot',
        'ddot': r'\ddot', 'bar': r'\overline', 'vec': r'\vec', 'dyad': r'\overleftrightarrow', 'under': r'\underline',
        'underline': r'\underline', 'overline': r'\overline', 'widehat': r'\widehat', 'widetilde': r'\widetilde',
        'box': r'\boxed', 'arch': r'\overset{\frown}', 'not': r'\not', 'breve': r'\breve'}
FONTS = {'rm': 'rm', 'it': 'it', 'bold': 'bold'}
STD_FUNC = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh', 'coth', 'log',
            'ln', 'lg', 'exp', 'det', 'dim', 'ker', 'hom', 'arg', 'deg', 'gcd', 'max', 'min', 'sup', 'inf', 'lim',
            'limsup', 'liminf', 'Pr'}
GLUE = ['sinh', 'cosh', 'tanh', 'coth', 'sech', 'csch', 'sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'min', 'overrightarrow',
        'overleftarrow', 'widehat', 'widetilde', 'overline', 'underline', 'bar', 'vec', 'dyad', 'hat', 'tilde', 'dot', 'ddot',
        'acute', 'grave', 'check', 'breve', 'leq', 'geq', 'neq', 'triangle', 'angle', 'cap', 'cup', 'cdots', 'ldots', 'vdots', 'ddots']
SYMKEYS = sorted({k for t in ORDER for k in T[t] if not k[0].isalpha()}, key=lambda k: -len(k))   # '<=', '!=', '>>>' ...


def lookup(cmd):
    """rhwp lookup_symbol 과 같은 순서: 정확히 일치 -> 전부 대문자인 그리스 -> 대문자 재시도(그리스·화살표 제외)."""
    for t in ORDER:
        if cmd in T[t]:
            return T[t][cmd]
    if cmd.isalpha() and cmd.isupper():
        for n, v in T['GREEK_UPPER'].items():
            if n[0].isupper() and n.upper() == cmd:
                return v
    up = cmd.upper()
    if up != cmd:
        for t in UPPER_FALLBACK:
            if up in T[t]:
                return T[t][up]
    return None


def is_greek(s):
    return s in T['GREEK_LOWER'] or s in T['GREEK_UPPER'] or (s.isupper() and any(n.upper() == s for n in T['GREEK_UPPER']))


def is_keyword(s):
    lo = s.lower()
    return (lo in T['FUNCTIONS'] or s in T['FUNCTIONS'] or lookup(s) is not None or lo in DECO or lo in FONTS
            or s.upper() in STRUCT)


DELIM_UNI = {'∥': r'\Vert', '‖': r'\Vert', '∣': '|', '｜': '|', '⟨': r'\langle', '〈': r'\langle', '⟩': r'\rangle', '〉': r'\rangle',
             '⌊': r'\lfloor', '⌋': r'\rfloor', '⌈': r'\lceil', '⌉': r'\rceil', '（': '(', '）': ')', '［': '[', '］': ']'}


_TEXT_ESC = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '%': r'\%', '$': r'\$', '#': r'\#', '&': r'\&',
             '_': r'\_', '^': r'\^{}', '~': r'\textasciitilde{}'}


def text_escape(v):
    """\\text{…} 안에 들어가는 글(따옴표 글·기타 문자)의 LaTeX 특수문자를 이스케이프한다."""
    return ''.join(_TEXT_ESC.get(c, c) for c in v)


class Toks(list):
    """토큰 목록. .sp = 앞에 공백이 있었던 토큰의 위치 (첨자 인자의 범위를 정할 때 쓴다)
    .pos = 토큰마다 원문 글자 위치, .brk = 공백 없는 덩어리가 9글자씩 끊기는 곳의 토큰 위치 (OVER 의 분자 범위)"""
    sp = None; cur = 0

    def append(self, x):
        list.append(self, x)
        if not hasattr(self, 'pos'): self.pos = []
        self.pos.append(self.cur)


OPERATORS = ('inf', 'sup', 'liminf', 'limsup')     # 한글에는 전용 명령이 없어 rm "inf" 처럼 씀
CHUNK = 9        # 한글은 공백 없이 붙은 덩어리가 9글자를 넘으면 9글자 뒤에서 끊어 읽는다 (한글에서 확인함; OVER 의 분자)


def mark_chunks(toks):
    """공백 없는 덩어리를 9글자씩 끊는 위치를 .brk(토큰 위치 집합)에 모은다.
    끊김이 숫자·영문자 토큰 한가운데면 그 토큰을 둘로 쪼갠다(.sp 도 새 위치로 옮긴다)."""
    pos = getattr(toks, 'pos', [])
    if len(pos) != len(toks):
        toks.brk = set(); return toks
    # 덩어리(공백으로 끊긴 구간)의 시작 글자 위치
    run0 = []; cur = pos[0] if pos else 0
    for t in range(len(toks)):
        if t in toks.sp: cur = pos[t]
        run0.append(cur)
    new, npos, remap = [], [], {}
    for t, (k, v) in enumerate(toks):
        remap[t] = len(new)
        off = pos[t] - run0[t]
        if k in ('num', 'id') and off // CHUNK != (off + len(v) - 1) // CHUNK:
            while v:
                take = CHUNK - (off % CHUNK)
                new.append((k, v[:take])); npos.append(run0[t] + off)
                v = v[take:]; off += take
        else:
            new.append((k, v)); npos.append(pos[t])
    sp = {remap[t] for t in toks.sp if t in remap}
    new_run0 = []; cur = npos[0] if npos else 0
    for t in range(len(new)):
        if t in sp: cur = npos[t]
        new_run0.append(cur)
    brk = set()
    for t in range(1, len(new)):
        if t in sp: continue
        if (npos[t] - new_run0[t]) // CHUNK > (npos[t - 1] - new_run0[t - 1]) // CHUNK and new_run0[t] == new_run0[t - 1]: brk.add(t)
    toks[:] = []
    for x in new: list.append(toks, x)
    toks.pos = npos; toks.sp = sp; toks.brk = brk
    return toks


def tokenize(src):
    src = src.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
    toks, i, n = Toks(), 0, len(src)
    toks.sp = set(); mark = None
    while i < n:
        if mark is not None and len(toks) > mark: toks.sp.add(mark); mark = None
        c = src[i]; toks.cur = i
        if c.isspace():
            if mark is None: mark = len(toks)
            i += 1; continue
        if c == '"':
            j = src.find('"', i + 1); j = n if j < 0 else j
            toks.append(('txt', src[i + 1:j])); i = j + 1; continue
        if c in '`~#&{}^_()[]|,.:;!\'/+-=<>*@$%':
            for k in SYMKEYS + ['->', '<-']:
                if src.startswith(k, i):
                    toks.append(('cmd' if k not in ('->', '<-') else 'arrow', k)); i += len(k); break
            else:
                toks.append(('ch', c)); i += 1
            continue
        if c.isdigit():
            m = re.match(r'\d+(\.\d+)?', src[i:]); toks.append(('num', m.group())); i += m.end(); continue
        if c.isascii() and c.isalpha():
            w = re.match(r'[A-Za-z]+', src[i:]).group(); i += len(w); wend = i
            while w:
                toks.cur = wend - len(w)
                if is_keyword(w):
                    toks.append(('cmd', w)); break
                lw = w.lower(); done = False
                for kw in ('over', 'atop'):                       # over2, overa 처럼 붙은 피연산자
                    if lw.startswith(kw) and 0 < len(w) - len(kw) <= 2:
                        toks.append(('cmd', w[:len(kw)])); w = w[len(kw):]; done = True; break
                if done: continue
                for kw in ('bold', 'times', 'sim', 'rm', 'it'):   # 글꼴 전환·times/sim 이 붙은 경우
                    if (w.startswith(kw) or (kw in ('bold', 'rm', 'it') and lw.startswith(kw))) and len(w) > len(kw):
                        toks.append(('cmd', w[:len(kw)])); w = w[len(kw):]; done = True; break
                    if kw in ('times', 'sim') and w.startswith(kw.upper()) and len(w) > len(kw):
                        toks.append(('cmd', w[:len(kw)])); w = w[len(kw):]; done = True; break
                if done: continue
                for k in range(len(w) - 1, 1, -1):               # 붙은 키워드 접두 중 가장 긴 것
                    if w[:k].lower() in GLUE or is_greek(w[:k]):
                        toks.append(('cmd', w[:k])); w = w[k:]; done = True; break
                if done: continue
                toks.append(('id', w)); break
            continue
        j = i
        while j < n and not (src[j].isascii() or src[j].isspace()): j += 1   # 한글 등 비ASCII 덩어리
        if j == i: j = i + 1
        toks.append(('na', src[i:j])); i = j
    if mark is not None and len(toks) > mark: toks.sp.add(mark)
    return mark_chunks(toks)


class G(str):
    """HWP 의 {…} 그룹. 값은 괄호를 뺀 안쪽 LaTeX (괄호는 쓰는 쪽이 필요할 때만 씌운다)."""


class P:
    def __init__(s, toks):
        s.t = toks; s.i = 0; s.font = 'it'; s.sp = getattr(toks, 'sp', None) or set(); s.brk = getattr(toks, 'brk', None) or set()

    def peek(s):
        return s.t[s.i] if s.i < len(s.t) else (None, None)

    def next(s):
        x = s.peek(); s.i += 1; return x

    def is_cmd(s, name):
        k, v = s.peek(); return k == 'cmd' and v.upper() == name

    # ---- 그룹/인자
    def group(s):
        s.i += 1                                  # '{'
        r = s.seq(stop='}')
        if s.peek() == ('ch', '}'): s.i += 1
        return r

    def element(s):
        """OVER 의 분모, 장식·SQRT 의 인자처럼 '다음 한 요소'."""
        return s.script(s.atom())

    def run(s, chunk=False):
        """공백으로 끊기지 않은 한 덩어리 (OVER 의 분모, SQRT·장식의 인자).  {…} 로 시작하면 그 묶음만.  덩어리 안의 소괄호는 짝이 맞으면 포함."""
        braced = s.peek() == ('ch', '{')
        parts = [s.element()]; depth = 1 if parts[0] == '(' else 0
        while not braced:
            k2, v2 = s.peek()
            if k2 is None or s.i in s.sp: break
            if chunk and s.i in s.brk: break                   # 9글자 끊김 (OVER 의 분모)
            if (k2, v2) == ('ch', ')') and depth > 0: depth -= 1; parts.append(s.element()); continue
            if (k2, v2) in (('ch', '}'), ('ch', ']'), ('ch', ')'), ('ch', '`'), ('ch', '~'), ('ch', '&'), ('ch', '#')): break
            if k2 == 'cmd' and v2.upper() in ('RIGHT', 'OVER', 'ATOP', 'CHOOSE', 'OF'): break
            if (k2, v2) == ('ch', '('): depth += 1
            parts.append(s.element())
        return ''.join(str(x) for x in parts)

    def arg(s):
        a = s.atom()
        return str(a)

    # ---- 원자
    def wrap_font(s, text):
        if s.font == 'rm': return r'\mathrm{' + text + '}'
        if s.font == 'bold': return r'\mathbf{' + text + '}'
        return text

    def delim(s):
        k, v = s.next()
        if k == 'ch' and v in '([|.': return v
        if k == 'ch' and v == ')': return v
        if k == 'ch' and v == ']': return v
        if k == 'ch' and v == '{': return r'\{'
        if k == 'ch' and v == '}': return r'\}'
        if k == 'ch' and v == '<': return r'\langle'              # LEFT < u,v RIGHT >  (내적·기댓값 꺾쇠)
        if k == 'ch' and v == '>': return r'\rangle'
        if k == 'ch' and v == '/': return '/'
        if k == 'na' and v in DELIM_UNI: return DELIM_UNI[v]      # ∥ ‖ ⟨ ⟩ ⌊ ⌋ ⌈ ⌉ 같은 문자 그대로의 구분 기호
        if k == 'cmd':
            l = lookup(v)
            if l is not None: return r'\{' if l == '{' else r'\}' if l == '}' else l
        return '.'

    def closing(s, name):
        """MATRIX{...} 같은 구조의 몸체: 행(#)·칸(&) 구분을 보존한 채 {…} 안쪽을 읽는다."""
        if s.peek() != ('ch', '{'): return None
        s.i += 1
        amp = 'matrix' if name.endswith('MATRIX') else 'cases' if name == 'CASES' else 'eqalign' if name == 'EQALIGN' else None
        body = s.seq(stop='}', consume=True, amp=amp)
        # 원문 오타: LEFT ( … } RIGHT ) 처럼 구조의 닫는 } 가 RIGHT 보다 먼저 오는 경우 — 한글은 받아 주지만
        # 그대로 옮기면 \\right 가 \\end{cases} 밖으로 나가 짝이 깨진다. 몸체 안에서 열린 \\left 만큼 뒤따르는 RIGHT 를 몸체로 끌어들인다.
        opened = len(re.findall(r'\\left(?![A-Za-z])', body)) - len(re.findall(r'\\right(?![A-Za-z])', body))
        while opened > 0:
            k, v = s.peek()
            if k == 'cmd' and v.upper() == 'RIGHT':
                s.next(); d = s.delim(); body += '\\right' + d + (' ' if d[-1:].isalpha() else ''); opened -= 1
                WARN.append((name, '구조의 } 가 RIGHT 보다 앞에 있어 RIGHT 를 몸체 안으로 옮김'))
            else: break
        if opened > 0:                                      # 끝내 짝이 없으면 몸체 안에서 닫는다 (환경 경계를 넘지 않게)
            body += '\\right.' * opened
            WARN.append((name, '몸체 안의 짝 없는 \\left %d개 뒤에 \\right. 을 붙임' % opened))
        return body

    def atom(s):
        k, v = s.peek()
        if k is None: return ''
        if (k, v) == ('ch', '{'): return G(s.group())
        s.i += 1
        if k == 'num': return v
        if k == 'txt':                                    # "…" : 한글에서는 기본이 이탤릭, rm 이어야 로만체 (한글에서 확인함)
            if s.font == 'rm' and v.strip() in OPERATORS: return '\\' + v.strip() + ' '      # rm "inf" -> \inf (아래첨자가 밑에 붙도록)
            wrap = {'rm': r'\text{', 'bold': r'\textbf{'}.get(s.font, r'\textit{' if v.isascii() else r'\text{')   # 한글 글자는 기울이지 않음
            return wrap + text_escape(v) + '}'
        if k == 'na': return r'\text{' + text_escape(v) + '}'
        if k == 'arrow': return r'\to ' if v == '->' else r'\leftarrow '
        if k == 'id': return s.wrap_font(v)
        if k == 'ch':
            if v == '`': return r'\,'
            if v == '~': return r'\ '
            if v == '#': return r'\\'
            if v == '&': return r'\quad '        # 구조 밖의 & 는 열 구분이 아니라 탭 간격 (rhwp: SpaceKind::Tab)
            if v in '{}': return ''
            if v == '%': return r'\%'              # 수식 안의 % 는 ndhmd4tex 도 손대지 않으므로 직접 이스케이프 (LaTeX 주석 방지)
            if v == '$': return r'\$'
            return v
        # ---- 명령
        up = v.upper(); lo = v.lower()
        if lo in FONTS and v in (lo, up, v):
            s.font = FONTS[lo]; return ''           # 전역 전환 (rhwp: 중괄호로 끊기지 않음)
        if up in ('OVER', 'ATOP', 'CHOOSE'): return ''
        if up == 'OF': return s.wrap_font('of')              # root 에 붙지 못한 of 는 그냥 변수 (한글에서 확인함)
        if up in ('SQRT', 'ROOT'): return s.sqrt()
        if up in ('LEFT', 'RIGHT'):
            d = s.delim()
            return '\\' + up.lower() + d + (' ' if d[-1:].isalpha() else '')    # \left\langle u (명령 뒤 공백)
        if up in ('MATRIX', 'PMATRIX', 'BMATRIX', 'DMATRIX', 'VMATRIX'):
            env = {'MATRIX': 'matrix', 'PMATRIX': 'pmatrix', 'BMATRIX': 'bmatrix', 'DMATRIX': 'vmatrix', 'VMATRIX': 'Vmatrix'}[up]
            b = s.closing(up); return '' if b is None else '\\begin{%s}%s\\end{%s}' % (env, s.tidy_cells(b), env)
        if up == 'CASES':
            b = s.closing(up); return '' if b is None else r'\begin{cases}' + s.tidy_cells(b) + r'\end{cases}'
        if up in ('EQALIGN', 'PILE', 'LPILE', 'RPILE'):
            b = s.closing(up)
            if b is None: return ''
            rows = [r for r in re.split(r'\\\\', b) if re.sub(r'(\\,|\\ |\s)+', '', r)]   # 간격 맞춤용 빈 행은 버린다
            if not rows: return ''
            if len(rows) == 1: return s.tidy(rows[0].replace('&', ''))
            body = r'\\'.join(s.tidy(r) for r in rows)
            env = {'EQALIGN': 'aligned', 'PILE': 'matrix', 'LPILE': 'matrix', 'RPILE': 'matrix'}[up]
            return '\\begin{%s}%s\\end{%s}' % (env, body, env)
        if lo == 'inf': return r'\infty '
        if lo in DECO:
            return DECO[lo] + '{' + s.run(chunk=True).strip() + '}'
        if v == 'lim' or v == 'Lim' or up == 'LIM': return r'\lim '
        if v in T['FUNCTIONS'] or lo in T['FUNCTIONS']:
            f = v if v in T['FUNCTIONS'] else lo
            return ('\\' + f + ' ') if f in STD_FUNC else r'\operatorname{' + f + '}'
        if lo == 'inf': return r'\infty '                           # inf 는 함수가 아니라 ∞ (rhwp lookup_symbol)
        if v in ('prime', 'PRIME'): return "'"
        l = lookup(v)
        if l is not None:
            return l + (' ' if l[-1:].isalpha() and l.startswith('\\') else '')
        UNKNOWN.add(v); return r'\text{?' + v + '}'

    def sqrt(s):
        idx = None
        k, v = s.peek()
        if (k, v) == ('ch', '{') or (k, v) == ('ch', '('):         # {n} of {x}  /  (n) of x
            close = s.match(s.i)
            nk, nv = s.t[close + 1] if close + 1 < len(s.t) else (None, None)
            if nk == 'cmd' and nv.upper() == 'OF':
                if v == '{': idx = str(s.group())
                else:
                    s.i += 1; idx = s.seq(stop=')'); s.i += 1
                s.i += 1                                            # OF
        if idx is None and s.i + 1 < len(s.t) and s.t[s.i + 1][0] == 'cmd' and s.t[s.i + 1][1].upper() == 'OF':
            idx = str(s.atom()).strip(); s.i += 1                  # ROOT n OF x (단일 원자 지수)
        body = s.run(chunk=True).strip()
        return (r'\sqrt[' + idx + ']{' + body + '}') if idx is not None else r'\sqrt{' + body + '}'

    def match(s, i):
        o, c = s.t[i][1], '}' if s.t[i][1] == '{' else ')'
        d = 0
        for j in range(i, len(s.t)):
            if s.t[j] == ('ch', o): d += 1
            elif s.t[j] == ('ch', c):
                d -= 1
                if d == 0: return j
        return len(s.t)

    # ---- 첨자
    def operand(s, up):
        """첨자 인자. {…} 가 아니면 rhwp(한컴과 같은 규칙)처럼 공백·닫는 괄호·RIGHT·반대쪽 첨자 앞까지
        붙은 토큰을 모두 인자로 삼는다:  sum_i=1^n  ->  \\sum_{i=1}^n,   x^2+1 -> x^{2+1},   x^2 +1 -> x^2+1"""
        k, v = s.peek()
        if (k, v) == ('ch', '{'): return str(s.atom()).strip()
        items = []
        while True:
            k, v = s.peek()
            if k is None: break
            if (k, v) in (('ch', '}'), ('ch', ']'), ('ch', ')'), ('ch', '`'), ('ch', '~')): break
            if items and s.i in s.sp: break
            if k == 'cmd' and v.upper() in ('RIGHT', 'OVER', 'ATOP', 'CHOOSE', 'OF'): break
            is_up = (k, v) == ('ch', '^') or (k == 'cmd' and v.upper() == 'SUP')
            is_dn = (k, v) == ('ch', '_') or (k == 'cmd' and v.upper() == 'SUB')
            if is_up or is_dn:
                if is_up != up or not items: break                  # 반대쪽 첨자는 바깥 몫
                items.append(s.script(items.pop())); continue
            if (k, v) == ('ch', '('):
                s.i += 1; inner = s.seq(stop=')')
                if s.peek() == ('ch', ')'): s.i += 1
                items.append('(' + inner + ')'); continue
            items.append(str(s.atom()))
        return ''.join(items).strip()

    def script(s, base):
        while True:
            k, v = s.peek()
            if (k, v) in (('ch', '^'), ('ch', '_')) or (k == 'cmd' and v.upper() in ('SUB', 'SUP')):
                s.i += 1
                up = v == '^' or v.upper() == 'SUP'
                a = s.operand(up)
                if isinstance(base, G): base = '{' + base + '}'    # 그룹에 첨자가 붙을 때만 밑에 괄호
                a = a if re.fullmatch(r'[A-Za-z0-9]', a) or re.fullmatch(r'\\[A-Za-z]+ ?', a) else '{' + a + '}'
                base = str(base) + ('^' if up else '_') + a
            else:
                return base

    # ---- 열
    def seq(s, stop=None, consume=False, amp=None):
        """amp: 구조 몸체 안에서 & 를 어떻게 읽을지.
          matrix : & 하나가 칸 하나 (&& 는 빈 칸) — 그대로 둔다
          cases  : 한 행의 첫 & 묶음만 값|조건의 열 구분(&)이고, && 도 & 하나로 합친다. 같은 행의 나머지 & 는 탭 간격(\\quad)
          eqalign: 첫 & 묶음이 정렬 위치(&), && 이면 큰 간격을 더한다 (rhwp 와 같은 규칙)"""
        cur = [0]
        class L(list):
            starts = []
            def append(self, x): list.append(self, x); self.starts.append(cur[0])
        out = L(); out.starts = []; seen = False
        while True:
            cur[0] = s.i
            k, v = s.peek()
            if k is None: break
            if amp and (k, v) == ('ch', '&'):
                run = 0
                while s.peek() == ('ch', '&'): run += 1; s.i += 1
                if amp == 'matrix': out.append('&' * run)
                elif not seen: out.append('&' + (r'\quad ' if run >= 2 and amp == 'eqalign' else '')); seen = True
                else: out.append(r'\quad ' * (1 if run == 1 else 2))
                continue
            if amp and (k, v) == ('ch', '#'): seen = False
            if (k, v) == ('ch', '}'):
                if stop == '}':
                    if consume: s.i += 1
                    break
                s.i += 1; continue                                  # 짝 없는 '}' 는 무시
            if stop == ')' and (k, v) == ('ch', ')'): break
            if k == 'cmd' and v.upper() in ('OVER', 'ATOP', 'CHOOSE'):
                s.i += 1
                # 분자 = 앞쪽의, 공백으로 끊기지 않은 한 덩어리 (x+1 over 2 -> (x+1)/2,  x + 1 over 2 -> x + 1/2)
                j = len(out) - 1
                while j > 0 and out.starts[j] not in s.sp and out.starts[j] not in s.brk: j -= 1     # 공백 또는 9글자 끊김에서 끝
                j = max(j, 0)
                num = ''.join(str(x) for x in out[j:]); start0 = out.starts[j] if out else s.i
                del out[j:]; del out.starts[j:]
                den = s.run(chunk=True)                        # 분모도 공백 전까지 붙은 것, 단 9글자까지
                num, den = num.strip(), den.strip()
                cur[0] = start0
                if v.upper() == 'OVER': out.append(r'\frac{' + num + '}{' + den + '}')
                elif v.upper() == 'ATOP': out.append(r'{' + num + r'\atop ' + den + '}')
                else: out.append(r'\binom{' + num + '}{' + den + '}')
                continue
            out.append(s.element())
        return ''.join(str(x) for x in out)

    def tidy(s, x):
        x = re.sub(r'^(\\,|\\ |\s)+|(\\,|\\ |\s)+$', '', x)
        return x

    def tidy_cells(s, body):
        rows = [r for r in body.split('\\\\')]
        rows = [r for r in rows if r.strip() or True]
        cells = ['&'.join(s.tidy(c) for c in r.split('&')) for r in rows]
        return r'\\'.join(c for c in cells)


_LR = re.compile(r'\\(left|right|middle)(?![A-Za-z])(\s*(?:\\[A-Za-z]+|\\.|.))?', re.S)
_BAR = {'|', r'\|', r'\vert', r'\Vert'}


def _balanced(toks):
    st = 0
    for k, _ in toks:
        if k == 'left': st += 1
        elif k == 'right':
            st -= 1
            if st < 0: return False
    return st == 0


def balance_lr(r, src=''):
    """\\left 와 \\right 짝을 맞춘다 (짝이 안 맞으면 LaTeX 가 컴파일되지 않음).
    1) {x | …} 처럼 LEFT { x LEFT | … RIGHT } 로 쓴 경우: 안쪽 \\left| 는 짝 없는 구분선이므로 \\middle| 로 바꾼다.
    2) 그래도 남는 짝 없는 \\right 는 앞에 \\left. 을, 짝 없는 \\left 는 뒤에 \\right. 을 붙인다
       (HWP 는 한 수식을 여러 줄 수식으로 쪼개 쓰는 일이 많아, 열린 괄호가 다음 수식에서 닫히곤 한다)."""
    ms = list(_LR.finditer(r))
    if not ms: return r
    toks = [(m.group(1), (m.group(2) or '').strip()) for m in ms]
    msgs = []
    if not _balanced(toks):
        for i, (k, d) in enumerate(toks):                       # 구분선 역할의 \left| 후보를 하나씩 \middle 로 바꿔 본다
            if k == 'left' and d in _BAR and i > 0:
                t2 = toks[:i] + [('middle', d)] + toks[i + 1:]
                if _balanced([x for x in t2 if x[0] != 'middle']):
                    toks = t2; msgs.append('\\left%s 를 \\middle%s 로 바꿈' % (d, d)); break
    pieces, last, depth, need_l, ti = [], 0, 0, 0, 0
    for m, (k, d) in zip(ms, toks):
        pieces.append(r[last:m.start()]); last = m.end()
        pieces.append('\\%s%s' % (k, d))
        if k == 'left': depth += 1
        elif k == 'right':
            if depth == 0: need_l += 1
            else: depth -= 1
    pieces.append(r[last:])
    out = ''.join(pieces)
    if need_l: out = '\\left.' * need_l + out; msgs.append('짝 없는 \\right %d개 앞에 \\left. 을 붙임' % need_l)
    if depth: out = out + '\\right.' * depth; msgs.append('짝 없는 \\left %d개 뒤에 \\right. 을 붙임' % depth)
    if msgs: WARN.append((src, '; '.join(msgs)))
    return out


def convert(src):
    toks = tokenize(src)
    p = P(toks); r = p.seq()
    r = re.sub(r'(\\mathrm\{[^{}]*)\}([/.-])\\mathrm\{', r'\1\2', r)       # cm/s 처럼 기호로 이어진 경우
    r = re.sub(r'(\\mathrm\{[^{}]*)\}\\mathrm\{', r'\1', r)            # 이어진 \mathrm 합치기
    r = re.sub(r'(\\mathrm\{[^{}]*)\}\\mathrm\{', r'\1', r)
    r = re.sub(r'(\\mathbf\{[^{}]*)\}\\mathbf\{', r'\1', r)
    r = re.sub(r'(?:\\,|\\ ){2,}', r'\\,', r)                            # 간격 연속 -> 하나로
    r = re.sub(r'(\\[A-Za-z]+) +(?=[\\{}^_)\]&|,.]|$)', r'\1', r)        # 명령 뒤 불필요한 공백
    return balance_lr(r.strip(), src)


if __name__ == '__main__':
    for a in ["y=f(x)", "{DELTA y} over {DELTA x}", "lim _{DELTA x -> 0} {} {DELTA y} over {DELTA x}",
              "v(r) = left( { 1} over { 2} - r  right) r^2", "f prime (a)", "r``rmcm/s", "rmA it(a`,``f(a))",
              "DELTAx``->``0", "f(x)= {cases{x ^{2} +2x&`````(x GEQ 0)#eqalign{``#2x}&eqalign{`````#(x<0)}}",
              "a RARROW b rarrow c TIMES d", "root 3 of x", "sqrt {x+1}", "bmatrix{a&b#c&d}"]:
        print(a, '=>', convert(a))
    print('UNKNOWN:', UNKNOWN)
