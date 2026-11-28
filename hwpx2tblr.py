#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hwpx2tblr — hwpx 문서에서 표만 추려 tabularray(tblr / longtblr) 코드로 바꾼다.

표 안의 글·수식, 병합 칸, 정렬, 칸 너비, 테두리, 바탕색, 머리글 행을 옮긴다.
문서의 나머지(본문 문단, 그림, 레이아웃)는 보지 않는다. 표 안에 표가 있으면 안쪽 표도 tblr 로 낸다.
수식은 같은 폴더의 hwpeq.py 로 LaTeX 로 바꾼다(없으면 수식 원문을 \\texttt 로 남긴다).

사용:  python hwpx2tblr.py 문서.hwpx [-o 표.tex] [--standalone] [옵션]
"""
import sys, os, re, json, zipfile, argparse, collections, math, posixpath, unicodedata
import xml.etree.ElementTree as ET

__version__ = '0.0.10'

PN = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HN = 'http://www.hancom.co.kr/hwpml/2011/head'
p_ = lambda t: '{%s}%s' % (PN, t)
h_ = lambda t: '{%s}%s' % (HN, t)
lname = lambda e: e.tag.rsplit('}', 1)[-1]

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hwpeq
except Exception:                                   # 수식 변환기가 없어도 돈다
    hwpeq = None

HU_MM = 25.4 / 7200                                 # 1 HWPUNIT = 1/7200 inch


def hu(v, hi=2000000):
    """hwpx 의 길이 속성 -> 정수 HWPUNIT, 이상한 값이면 None.
    부호 없는 32비트로 적힌 음수(4294967xxx 같은 값)와 비상식적으로 큰 값을 걸러 낸다."""
    try: n = int(v)
    except (TypeError, ValueError): return None
    if n >= 2 ** 31: n -= 2 ** 32
    return n if 0 <= n <= hi else None


# ───────────────────────── 읽기: 패키지 ─────────────────────────
def section_paths(z):
    """본문 구역(Contents/sectionN.xml)을 content.hpf 의 읽기 순서대로 돌려준다."""
    names = set(z.namelist())
    rx = re.compile(r'(?:^|/)section(\d+)\.xml$')
    ordered = []
    try:
        pkg = ET.fromstring(z.read('Contents/content.hpf'))
        OPF = '{http://www.idpf.org/2007/opf/}'
        manifest = {}
        for it in pkg.iter(OPF + 'item'):
            href = it.get('href')
            if href:
                manifest[it.get('id')] = posixpath.normpath(href.lstrip('/') if href.startswith('/') else posixpath.join('Contents', href))
        for ir in pkg.iter(OPF + 'itemref'):
            pth = manifest.get(ir.get('idref'))
            if pth in names and rx.search(pth): ordered.append(pth)
    except (KeyError, ET.ParseError):
        pass
    found = sorted((int(m.group(1)), n) for n in names for m in [rx.search(n)] if m)
    ordered += [n for _, n in found if n not in ordered]
    return list(dict.fromkeys(ordered))


class Fill:                                          # 바탕색
    pass


class Doc:
    """header.xml 의 테두리·바탕·문단 정렬·글자 모양과 쪽 크기를 읽어 둔다."""

    def __init__(self, path, roots=None):
        self.z = zipfile.ZipFile(path) if isinstance(path, str) else path
        head = ET.fromstring(self.z.read('Contents/header.xml'))
        self.bf = {}
        for b in head.iter(h_('borderFill')):
            d = {}
            for side in ('left', 'right', 'top', 'bottom'):
                e = b.find(h_(side + 'Border'))
                if e is None: d[side] = None; continue
                m = re.match(r'([\d.]+)', e.get('width') or '0.1')
                d[side] = (e.get('type') or 'NONE', float(m.group(1)) if m else 0.1, (e.get('color') or '#000000').upper())
            d['bg'] = None
            for e in b.iter():
                if lname(e) == 'winBrush':
                    fc = e.get('faceColor')
                    if fc and fc.lower() != 'none' and re.fullmatch(r'#[0-9A-Fa-f]{6}', fc): d['bg'] = fc[1:].upper()
            self.bf[b.get('id')] = d
        self.align = {}
        for pp in head.iter(h_('paraPr')):
            a = pp.find(h_('align'))
            self.align[pp.get('id')] = a.get('horizontal') if a is not None else 'JUSTIFY'
        self.cp = {}
        for cp in head.iter(h_('charPr')):
            ul, so = cp.find(h_('underline')), cp.find(h_('strikeout'))
            ult = ul.get('type') if ul is not None else 'NONE'
            self.cp[cp.get('id')] = dict(
                B=cp.find(h_('bold')) is not None, I=cp.find(h_('italic')) is not None,
                U=ult == 'BOTTOM', X=(so is not None and so.get('shape') not in (None, 'NONE')) or ult == 'CENTER',
                h=int(cp.get('height') or 1000))
        self.roots = roots if roots else [ET.fromstring(self.z.read(n)) for n in section_paths(self.z)]
        if not self.roots: raise ValueError('HWPX 에서 sectionN.xml 본문을 찾지 못했습니다')
        self.textw = 45000                           # HWPUNIT
        self.body_h = 0
        sp = next((e for r in self.roots for e in r.iter(p_('secPr'))), None)
        if sp is not None and sp.find(p_('pagePr')) is not None:
            pg = sp.find(p_('pagePr')); mg = pg.find(p_('margin'))
            tw = (hu(pg.get('width'), 10 ** 7) or 0) - sum(hu(mg.get(k), 10 ** 7) or 0 for k in ('left', 'right', 'gutter'))
            if tw > 0: self.textw = tw
            self.body_h = (hu(pg.get('height'), 10 ** 7) or 0) - sum(hu(mg.get(k), 10 ** 7) or 0 for k in ('top', 'bottom', 'header', 'footer'))
        sz = collections.Counter()                   # 본문 글자 크기(표 바깥 문단의 최빈값)
        for r in self.roots:
            for p in r.findall(p_('p')):
                for run in p.findall(p_('run')):
                    n = len(''.join(x.text or '' for x in run.findall(p_('t'))).strip())
                    if n: sz[self.cp.get(run.get('charPrIDRef'), {}).get('h', 1000)] += n
        self.body_font = sz.most_common(1)[0][0] if sz else 1000
        self.colors = set()                          # 쓴 바탕·선 색 (\providecolor 로 정의)
        self.need = set()                            # 필요한 패키지
        self.pic_hook = None                         # 그림 -> LaTeX 글을 돌려주는 함수(없으면 [그림] 자리 표시). hwpx2ndhmd 가 쓴다
        self.sub_env = False                         # True 면 안쪽 표를 subtblr 로 낸다(\NewTblrEnviron 필요): 바깥 \end{tblr} 를 첫 \end{tblr} 로 찾는 도구용
        self.sub_names = set(); self.depth = 0
        self.pic_scale = 1.0                         # 그림 크기에 곱할 비율(표가 본문 너비에 맞춰 줄어든 정도)
        self.warn = []


def pic_latex(doc, pic, path):
    """표 칸 안의 그림 -> \\includegraphics. 크기는 한글이 기록한 표시 크기(hp:sz, 없으면 curSz·orgSz)에 표의 축소 비율을 곱한 값이고,
    너비는 칸 너비(\\linewidth)를 넘지 않으며, 높이도 함께 주어 가로세로 비율을 지킨다(keepaspectratio).
    크기를 모르면 칸 너비의 0.9."""
    def dim(tag, attr):
        e = pic.find(p_(tag))
        return (hu(e.get(attr), 10 ** 7) or 0) if e is not None else 0
    w = dim('sz', 'width') or dim('curSz', 'width') or dim('orgSz', 'width')
    h = dim('sz', 'height') or dim('curSz', 'height') or dim('orgSz', 'height')
    doc.need.add('graphicx')
    if not w: return r'\includegraphics[width=0.9\linewidth,keepaspectratio]{%s}' % path
    wm = w * HU_MM * doc.pic_scale
    opt = r'width=\dimexpr\ifdim %.1fmm>\linewidth\linewidth\else %.1fmm\fi\relax' % (wm, wm)
    if h: opt += ',height=%.1fmm' % (h * HU_MM * doc.pic_scale)
    return r'\includegraphics[%s,keepaspectratio]{%s}' % (opt, path)


# ───────────────────────── LaTeX 글 ─────────────────────────
ESC = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '#': r'\#', '$': r'\$', '%': r'\%', '&': r'\&', '_': r'\_',
       '~': r'\textasciitilde{}', '^': r'\textasciicircum{}', '\u00a0': '~', '\u200b': '', '\ufeff': '', '\t': ' ',
       '\x00': '', '\x0b': ' ', '\x0c': ' '}


WAVE = {'on': True}                                 # ∼(U+223C)를 물결표(U+301C)로: 본문 글꼴에 U+223C 가 없는 경우가 많고, ndhmd4tex 는 원문 구간에 글자 치환을 적용하지 않는다


def tex_escape(s):
    if WAVE['on']:
        s = s.replace('\u223c', '\u301c')
        s = re.sub(r'(^|[\s(\[{<])"', '\\1\u201c', s).replace('"', '\u201d')     # 곧은 따옴표는 LaTeX 가 모두 닫는 따옴표로 그린다
        s = re.sub(r"(^|[\s(\[{<])'", "\\1\u2018", s).replace("'", '\u2019')
    out = ''.join(ESC.get(c, c) for c in s)
    out = out.replace('<!--', '<!-{}-').replace('--', '-{}-').replace("''", "'{}'").replace('``', '`{}`')   # 합자가 되지 않게
    out = out.replace('?`', '?{}`').replace('!`', '!{}`')
    return out


def eq_tex(doc, script):
    doc.need.update(('amsmath', 'amssymb'))
    if hwpeq is not None:
        try:
            m = hwpeq.convert(script or '')
            if '\\\\' in m and '\\begin' not in m:                    # 수식 안의 줄바꿈(#)은 칸 안의 줄바꿈으로: 줄마다 따로 수식
                ps = [re.sub(r'^(?:\\,|\\ |\s)+', '', x).strip() for x in m.split('\\\\')]
                return r' \par '.join('$%s$' % x for x in ps if x)
            return ('{$%s$}' if '&' in m else '$%s$') % m                  # 수식 안의 &(cases·행렬)는 tabularray 가 칸 나눔으로 읽지 않게 중괄호로 감싼다
        except Exception:
            pass
    return r'\texttt{%s}' % tex_escape(script or '')


def wrap_flags(txt, f, doc):
    """서식 명령으로 감싼다. 줄바꿈(\\par) 사이마다 따로 감싸 \\underline 같은 상자 안에 \\par 가 들어가지 않게 한다."""
    if not (f['B'] or f['I'] or f['U'] or f['X']): return txt
    pieces = re.split(r'(\s*\\par\s*)', txt)
    out = []
    for k, pc in enumerate(pieces):
        if k % 2 or not pc.strip():
            if f['U'] and k % 2 == 0 and pc and not pc.strip() and len(pc) > 1:     # 밑줄 친 빈칸(답 쓰는 줄)은 그 폭의 밑줄로
                out.append(r'\underline{\hspace*{%.1fem}}' % (0.5 * len(pc)))
            else:
                out.append(pc)
            continue
        if f['B']: pc = r'\textbf{%s}' % pc
        if f['I']: pc = r'\textit{%s}' % pc
        if f['U']: pc = r'\underline{%s}' % pc
        if f['X']: pc = r'\sout{%s}' % pc; doc.need.add('ulem')
        out.append(pc)
    return ''.join(out)


def para_tex(doc, p, a):
    """문단 하나 -> (LaTeX 글, 정렬). 서식이 같은 이웃 글은 한 덩어리로 묶는다."""
    segs = []                                        # [flags, 글]  글은 이미 escape 됨
    def add(f, s, raw=False):
        if segs and segs[-1][0] == f and not raw and not segs[-1][2]: segs[-1][1] += s
        else: segs.append([f, s, raw])
    for run in p.findall(p_('run')):
        f = doc.cp.get(run.get('charPrIDRef'), dict(B=False, I=False, U=False, X=False)) if a.format else dict(B=False, I=False, U=False, X=False)
        f = {k: f[k] for k in 'BIUX'}
        for ch in run:
            tag = lname(ch)
            if tag == 't':
                buf = [ch.text or '']
                for c in ch:
                    ct = lname(c)
                    if ct == 'tab': buf.append(' ')
                    elif ct == 'lineBreak': buf.append('\n')
                    elif ct in ('fwSpace', 'nbSpace'): buf.append('\u00a0')
                    buf.append(c.tail or '')
                add(f, tex_escape(''.join(buf)).replace('\n', r' \par '))
            elif tag == 'equation':
                sc = ch.find(p_('script'))
                add(f, eq_tex(doc, sc.text if sc is not None else ''), raw=True)
            elif tag == 'pic':
                g = doc.pic_hook(ch) if doc.pic_hook else None
                if g: add(f, g, raw=True); doc.need.add('graphicx')
                else: add(f, r'\textit{[그림]}', raw=True); doc.warn.append('표 안의 그림은 자리 표시([그림])로 남깁니다')
            elif tag == 'tbl':
                doc.depth += 1
                try: inner = table_tex(doc, ch, a, nested=True)
                finally: doc.depth -= 1
                add(dict(B=False, I=False, U=False, X=False), '{' + inner + '}', raw=True)
            elif tag == 'ctrl':
                for c in ch:
                    if lname(c) in ('footNote', 'endNote'):
                        sub = c.find(p_('subList'))
                        t = ' '.join(' '.join(''.join(x.itertext()) for x in q.iter(p_('t'))) for q in (sub.iter(p_('p')) if sub is not None else []))
                        add(f, r'\textsuperscript{(%s)}' % tex_escape(' '.join(t.split())), raw=True)
    s = ''.join(x[1] if x[2] else wrap_flags(x[1], x[0], doc) for x in segs)             # 수식·표 같은 덩어리(raw)는 서식을 입히지 않는다
    s = s.strip()
    s = re.sub(r'(?:\s*\\par\s*)+$', '', s)               # 문단 끝의 강제 줄바꿈
    al = doc.align.get(p.get('paraPrIDRef'), 'JUSTIFY')
    return s, al


def cell_tex(doc, tc, a):
    """칸 하나 -> (LaTeX 글, 글자 수로 가중한 정렬 다수결, 글자 수)"""
    sub = tc.find(p_('subList'))
    paras, votes = [], collections.Counter()
    for p in (sub.findall(p_('p')) if sub is not None else []):
        s, al = para_tex(doc, p, a)
        n = len(''.join(''.join(x.itertext()) for x in p.iter(p_('t'))).strip())
        if s: votes[al] += max(n, 1)
        paras.append(s)
    while paras and not paras[-1]: paras.pop()
    while paras and not paras[0]: paras.pop(0)
    text = ''
    for s in paras:                                   # 빈 문단은 한 줄 띄움으로
        if not text: text = s; continue
        text += r' \par ' + s
    if r'\par' in text: text = '{%s}' % text                      # \par 가 든 칸은 칸 전체를 중괄호로 묶는다
    elif text.startswith(('[', '*')): text = '{}' + text           # 칸 첫머리의 [ 는 tabularray 가 선택 인자로 읽는다
    al = votes.most_common(1)[0][0] if votes else None
    return text, al


# ───────────────────────── 표 모델 ─────────────────────────
class Cell:
    pass


def halign_of(al, a):
    if al in ('CENTER',): return 'c'
    if al in ('RIGHT',): return 'r'
    if al == 'JUSTIFY' and a.justify: return 'j'
    return 'l'


VALIGN = {'TOP': 't', 'CENTER': 'm', 'BOTTOM': 'b'}


def read_table(doc, tbl, a):
    cells = []
    tbl_bf = tbl.get('borderFillIDRef')
    im = tbl.find(p_('inMargin'))
    for tr in tbl.findall(p_('tr')):
        for tc in tr.findall(p_('tc')):
            ad, sp, sz = tc.find(p_('cellAddr')), tc.find(p_('cellSpan')), tc.find(p_('cellSz'))
            if ad is None: continue
            c = Cell()
            c.r, c.c = int(ad.get('rowAddr')), int(ad.get('colAddr'))
            c.rs = max(1, int(sp.get('rowSpan'))) if sp is not None else 1
            c.cs = max(1, int(sp.get('colSpan'))) if sp is not None else 1
            c.w = (hu(sz.get('width')) or 0) if sz is not None else 0
            c.bf = doc.bf.get(tc.get('borderFillIDRef')) or doc.bf.get(tbl_bf)
            sl = tc.find(p_('subList'))
            c.valign = VALIGN.get(sl.get('vertAlign') if sl is not None else 'TOP', 't')
            c.header = tc.get('header') == '1'
            m = tc.find(p_('cellMargin'))
            if tc.get('hasMargin') != '1' or m is None: m = im
            if m is not None:
                lf, tp = hu(m.get('left'), 3000), hu(m.get('top'), 3000)
                if (lf is None or tp is None) and im is not None and m is not im:       # 칸 여백이 -1(4294967295) 같은 값이면 표의 기본 여백으로
                    lf, tp = hu(im.get('left'), 3000), hu(im.get('top'), 3000)
                    doc.warn.append('칸 안쪽 여백이 비상식적인 값(-1 등)인 칸은 표의 기본 여백(inMargin)을 씁니다')
                elif lf is None or tp is None:
                    doc.warn.append('비상식적인 칸 안쪽 여백 값(%s, %s)을 무시했습니다' % (m.get('left'), m.get('top')))
                c.margin = (lf, tp)
            else:
                c.margin = (None, None)
            c.el = tc
            cells.append(c)
    nr = max([c.r + c.rs for c in cells] + [int(tbl.get('rowCnt') or 0)])
    nc = max([c.c + c.cs for c in cells] + [int(tbl.get('colCnt') or 0)])
    # 격자 검사: 겹치는 칸은 버리고, 빈 자리는 빈 1x1 칸으로 메운다
    own = [[None] * nc for _ in range(nr)]
    keep = []
    for c in sorted(cells, key=lambda x: (x.r, x.c)):
        if any(own[y][x] is not None for y in range(c.r, c.r + c.rs) for x in range(c.c, c.c + c.cs)):
            doc.warn.append('겹치는 칸을 버렸습니다 (%d행 %d열)' % (c.r + 1, c.c + 1)); continue
        for y in range(c.r, c.r + c.rs):
            for x in range(c.c, c.c + c.cs): own[y][x] = c
        keep.append(c)
    for y in range(nr):
        for x in range(nc):
            if own[y][x] is None:
                c = Cell(); c.r, c.c, c.rs, c.cs, c.w = y, x, 1, 1, 0
                c.bf = None; c.valign = 't'; c.header = False; c.margin = (None, None); c.el = None
                own[y][x] = c; keep.append(c)
    return keep, own, nr, nc, im


# ───────────────────────── 테두리·색 ─────────────────────────
def line_style(side, doc, a):
    """(종류, 굵기 mm, 색) -> 선 명세 문자열 또는 None"""
    if not side or side[0] == 'NONE' or not a.borders: return None
    typ, w, col = side
    w = round(max(w, 0.05), 2)
    kind = ''
    if typ in ('DASH', 'LONG_DASH', 'DASH_DOT', 'DASH_DOT_DOT'): kind = 'dashed'
    elif typ in ('DOT', 'CIRCLE'): kind = 'dotted'
    elif typ.startswith(('DOUBLE', 'SLIM_THICK', 'THICK_SLIM')) or typ.endswith('THICK_SLIM'): w = round(max(w * 2.5, 0.4), 2)   # 겹선은 굵은 한 줄로 근사
    parts = ['wd=%gmm' % w]
    if kind: parts.append(kind)
    if col not in ('#000000', '#000'):
        name = 'hwp' + col[1:]
        doc.colors.add(col[1:]); parts.append(name)
    return ', '.join(parts)


def edge_styles(doc, own, nr, nc, a):
    """수평선 H[y][x] (y=0..nr, x=0..nc-1), 수직선 V[y][x] (y=0..nr-1, x=0..nc) 의 선 명세"""
    def pick(*cands):
        best = None
        for s in cands:
            if s is None: continue
            if best is None or float(re.search(r'wd=([\d.]+)', s).group(1)) > float(re.search(r'wd=([\d.]+)', best).group(1)): best = s
        return best
    H = [[None] * nc for _ in range(nr + 1)]
    V = [[None] * (nc + 1) for _ in range(nr)]
    for y in range(nr + 1):
        for x in range(nc):
            up = own[y - 1][x] if y > 0 else None
            dn = own[y][x] if y < nr else None
            cu = line_style(up.bf['bottom'], doc, a) if up is not None and up.bf and up.r + up.rs - 1 == y - 1 else None
            cd = line_style(dn.bf['top'], doc, a) if dn is not None and dn.bf and dn.r == y else None
            H[y][x] = pick(cu, cd)
    for y in range(nr):
        for x in range(nc + 1):
            lf = own[y][x - 1] if x > 0 else None
            rt = own[y][x] if x < nc else None
            cl = line_style(lf.bf['right'], doc, a) if lf is not None and lf.bf and lf.c + lf.cs - 1 == x - 1 else None
            cr = line_style(rt.bf['left'], doc, a) if rt is not None and rt.bf and rt.c == x else None
            V[y][x] = pick(cl, cr)
    return H, V


def runs(idx):
    """정수 목록 -> '1-3,5' 꼴 (1부터 셈)"""
    out, i = [], 0
    idx = sorted(idx)
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1: j += 1
        out.append('%d' % (idx[i] + 1) if i == j else '%d-%d' % (idx[i] + 1, idx[j] + 1))
        i = j + 1
    return ','.join(out)


def line_specs(kind, M, n_lines, n_pos):
    """선 행렬 -> ['hline{1,3}={1-4}{wd=0.12mm}', ...]. 같은 모양의 선은 한데 묶는다."""
    groups = collections.OrderedDict()
    for y in range(n_lines):
        by_style = collections.defaultdict(list)
        for x in range(n_pos):
            if M[y][x]: by_style[M[y][x]].append(x)
        for st, xs in by_style.items():
            groups.setdefault((st, runs(xs)), []).append(y)
    out = []
    for (st, rr), ys in groups.items():
        out.append('%s{%s}={%s}{%s}' % (kind, ','.join(str(y + 1) for y in ys), rr, st))
    return out


def line_specs_v(V, nr, nc):
    groups = collections.OrderedDict()
    for x in range(nc + 1):
        by_style = collections.defaultdict(list)
        for y in range(nr):
            if V[y][x]: by_style[V[y][x]].append(y)
        for st, ys in by_style.items():
            groups.setdefault((st, runs(ys)), []).append(x)
    return ['vline{%s}={%s}{%s}' % (','.join(str(x + 1) for x in xs), rr, st) for (st, rr), xs in groups.items()]


# ───────────────────────── 길이 추정 ─────────────────────────
def em_width(text):
    w = 0.0
    for c in text:
        if c.isspace(): w += 0.3
        elif unicodedata.east_asian_width(c) in 'WF': w += 1.0
        else: w += 0.55
    return w


def est_height(doc, cells, nr, widths):
    """내용만으로 조판했을 때의 표 높이 추정 (HWPUNIT). 여러 행에 걸친 칸은 모자란 높이를 마지막 행에 더한다."""
    em = doc.body_font or 1000
    line = 1.5 * em
    need = []
    for c in cells:
        if c.el is None: continue
        usable = max(sum(widths[c.c:c.c + c.cs]) - 1000, em * 2)
        n = 0
        for pp in c.el.iter(p_('p')):
            txt = ''.join(''.join(x.itertext()) for x in pp.iter(p_('t')))
            w = em_width(txt) + 6 * sum(1 for _ in pp.iter(p_('equation')))
            n += max(1, math.ceil(w * em / usable))
        need.append((c, n * line + 0.6 * em))
    H = [line + 0.6 * em] * nr
    for c, h in sorted(need, key=lambda x: x[0].rs):
        have = sum(H[c.r:c.r + c.rs])
        if have < h: H[c.r + c.rs - 1] += h - have
    return sum(H)


# ───────────────────────── 표 -> tblr ─────────────────────────
def table_tex(doc, tbl, a, nested=False, info=None):
    cells, own, nr, nc, im = read_table(doc, tbl, a)
    # --- 칸 너비 (HWPUNIT)
    W = [None] * nc
    for c in cells:
        if c.cs == 1 and c.w > 0: W[c.c] = max(W[c.c] or 0, c.w)
    for c in sorted(cells, key=lambda x: x.cs):
        if c.cs == 1 or c.w <= 0: continue
        known = sum(W[x] or 0 for x in range(c.c, c.c + c.cs))
        unk = [x for x in range(c.c, c.c + c.cs) if W[x] is None]
        if unk:
            share = max(c.w - known, 0) / len(unk)
            for x in unk: W[x] = max(share, 1000)
    avg = (sum(w for w in W if w) / max(1, sum(1 for w in W if w))) or 4000
    W = [w if w else avg for w in W]
    total = sum(W)
    # --- 칸 안 글
    body = {}
    _szel = tbl.find(p_('sz')); _tw = (hu(_szel.get('width')) or 0) if _szel is not None else 0
    _tot = (_tw if _tw > 0 else total) * HU_MM
    _textw = a.textwidth if a.textwidth else doc.textw * HU_MM
    saved_scale = doc.pic_scale
    doc.pic_scale = 1.0 if nested or not _tot else min(1.0, _textw / _tot)         # 표가 본문 너비에 맞춰 줄면 그림도 같은 비율로
    try:
        for c in cells:
            body[id(c)] = cell_tex(doc, c.el, a) if c.el is not None else ('', None)
    finally:
        doc.pic_scale = saved_scale
    # --- 열 정렬: 칸 수 다수결, 칸 단위 예외는 cell{}{} 로
    colvote = [collections.Counter() for _ in range(nc)]
    for c in cells:
        al = body[id(c)][1]
        if c.cs == 1 and al: colvote[c.c][halign_of(al, a)] += 1
    colal = [(v.most_common(1)[0][0] if v else 'l') for v in colvote]
    # --- 환경
    nrows_long = a.long_table_rows and nr >= a.long_table_rows
    hh = est_height(doc, cells, nr, W) if doc.body_h > 0 else 0
    is_long = bool(nrows_long or (a.long_table and doc.body_h > 0 and hh >= a.long_table * doc.body_h))
    env = {'tblr': 'tblr', 'longtblr': 'longtblr'}.get(a.env, 'longtblr' if is_long and not nested else 'tblr')
    if nested: env = 'tblr'
    ename = env
    if nested and doc.sub_env: ename = 'sub' * doc.depth + 'tblr'; doc.sub_names.add(ename)
    # --- 안쪽 여백
    cs_mm = rs_mm = None
    if a.margins:
        def med(v):
            v = sorted(v)
            return v[len(v) // 2] if v else None
        mx = med([c.margin[0] for c in cells if c.el is not None and c.margin[0] is not None])      # 중앙값: 튀는 값에 안 끌린다
        my = med([c.margin[1] for c in cells if c.el is not None and c.margin[1] is not None])
        if mx is not None: cs_mm = min(max(mx * HU_MM, a.min_sep), a.max_sep)
        if my is not None: rs_mm = min(max(my * HU_MM, a.min_sep), a.max_sep)
    sep = (cs_mm if cs_mm is not None else 6 * 25.4 / 72.27)          # tabularray 기본 colsep 6pt
    # --- colspec
    mode = a.colspec
    textw_mm = a.textwidth if a.textwidth else doc.textw * HU_MM
    szel = tbl.find(p_('sz'))
    tw = (hu(szel.get('width')) or 0) if szel is not None else 0          # 표 자체의 가로 길이 (hp:sz width, HWPUNIT)
    tot_mm = (tw if tw > 0 else total) * HU_MM
    if mode == 'auto': mode = 'width' if tot_mm <= textw_mm * 1.001 or nested else 'capped'
    spec_cols, extra = [], []
    if mode == 'fixed':
        scale = min(1.0, textw_mm / tot_mm) if tot_mm else 1.0
        for x in range(nc):
            wd = max(W[x] * HU_MM * scale - 2 * sep, 3.0)
            spec_cols.append('Q[%s,wd=%.1fmm]' % (colal[x], wd))
    elif mode in ('width', 'capped', 'linewidth'):
        inner = [max(W[x] - 2 * sep / HU_MM, 500.0) for x in range(nc)]          # 칸 안쪽(글이 놓이는 폭)의 비율
        tin = sum(inner)
        for x in range(nc): spec_cols.append('X[%s,co=%.2f]' % (colal[x], max(0.05, inner[x] / tin * 100)))
        if mode == 'linewidth': extra.append('width=\\linewidth')
        else: extra.append('width=%.1fmm' % (min(tot_mm, textw_mm) if mode == 'capped' else tot_mm))
    else:
        spec_cols = list(colal)
    keys = ['colspec={%s}' % ''.join(spec_cols)] + extra
    gen_keys = list(extra)                                        # tblrDoumi(.tblr)용: 일반 설정
    if cs_mm is not None: keys.append('colsep=%.2fmm' % cs_mm); gen_keys.append(keys[-1])
    if rs_mm is not None: keys.append('rowsep=%.2fmm' % rs_mm); gen_keys.append(keys[-1])
    # --- 머리글 행
    hdr = 0
    if a.header != 'none' and env == 'longtblr':
        for r in range(nr):
            row = [c for c in cells if c.r == r]
            if row and all(c.header for c in row): hdr += 1
            else: break
        if a.header == 'first' and hdr == 0: hdr = 1
    if hdr: keys.append('rowhead=%d' % hdr)
    # --- 칸 서식(세로 정렬, 가로 정렬 예외, 바탕색)
    vv = collections.Counter(c.valign for c in cells if c.el is not None)
    gv = vv.most_common(1)[0][0] if vv else 't'
    cell_keys = []                                                # tblrDoumi(.tblr)용: 칸 서식
    if gv != 't': keys.append('cells={valign=%s}' % gv); cell_keys.append(keys[-1])
    sets = collections.defaultdict(list)
    for c in cells:
        if c.el is None: continue
        d = []
        al = body[id(c)][1]
        if al and c.cs == 1 and halign_of(al, a) != colal[c.c]: d.append('halign=%s' % halign_of(al, a))
        if al and c.cs > 1 and halign_of(al, a) != 'l': d.append('halign=%s' % halign_of(al, a))
        if c.valign != gv: d.append('valign=%s' % c.valign)
        if a.fills and c.bf and c.bf['bg']:
            doc.colors.add(c.bf['bg']); d.append('bg=hwp%s' % c.bf['bg'])
        if d: sets[', '.join(d)].append(c)
    for st, cs in sets.items():
        byrow = collections.defaultdict(list)
        for c in cs: byrow[c.r].append(c.c)
        rg = collections.OrderedDict()
        for r, xs in sorted(byrow.items()): rg.setdefault(tuple(sorted(xs)), []).append(r)
        for xs, rs in rg.items():
            keys.append('cell{%s}{%s}={%s}' % (runs(rs), runs(xs), st)); cell_keys.append(keys[-1])
    # --- 표 폭 전체를 차지하는 병합 칸(주석·자료 행 등): 열이 X/Q 형이라 칸 폭이 정해지지 않으면 긴 글이 줄바꿈되지 않고 잘리므로 wd 를 준다
    if nc >= 2:
        if mode == 'linewidth': full = '\\dimexpr\\linewidth-%.2fmm\\relax' % (2 * sep)
        else:
            tw_mm = (min(tot_mm, textw_mm) if mode == 'capped' else tot_mm) if mode in ('width', 'capped') else (sum(W) * HU_MM * min(1.0, textw_mm / tot_mm if tot_mm else 1.0))
            full = '%.1fmm' % max(tw_mm - 2 * sep, 10.0) if mode in ('width', 'capped', 'fixed') else None
        if full:
            seen_c = set()
            for r in range(nr):
                c = own[r][0]
                if id(c) in seen_c or c.r != r or c.c != 0 or c.cs != nc or c.rs != 1: continue
                seen_c.add(id(c))
                t = body[id(c)][0]
                if r == nr - 1 or '\\par' in t or len(t) >= 60:
                    keys.append('cell{%d}{1}={wd=%s}' % (r + 1, full)); cell_keys.append(keys[-1])
    # --- 테두리
    H, V = edge_styles(doc, own, nr, nc, a)
    line_keys = line_specs('hline', H, nr + 1, nc) + line_specs_v(V, nr, nc)
    keys += line_keys
    # --- 행
    lines = []
    for r in range(nr):
        row = []
        for x in range(nc):
            c = own[r][x]
            if c.r != r or c.c != x: row.append(''); continue
            txt = body[id(c)][0]
            if c.rs > 1 or c.cs > 1:
                o = (['r=%d' % c.rs] if c.rs > 1 else []) + (['c=%d' % c.cs] if c.cs > 1 else [])
                txt = r'\SetCell[%s]{} %s' % (','.join(o), txt)
            row.append(txt)
        lines.append(' & '.join(row).rstrip() + r' \\')
    cap = ''
    ce = tbl.find(p_('caption'))
    if ce is not None and env == 'longtblr' and not nested:
        ct = ' '.join(' '.join(''.join(x.itertext()) for x in q.iter(p_('t'))) for q in ce.iter(p_('p')))
        ct = ' '.join(ct.split())
        if ct: cap = '[caption={%s}]' % tex_escape(ct)
    if hh and doc.body_h and hh > doc.body_h * 0.95 and nr <= 3 and not nested:
        doc.warn.append('행이 적은데 한 쪽을 넘는 표가 있습니다(%d행 %d열): tblr/longtblr 은 행 가운데서 쪽을 나눌 수 없어 빈 쪽이 생길 수 있습니다' % (nr, nc))
    if env == 'longtblr' and not cap: cap = '[entry=none,label=none]'       # 캡션이 없으면 'Table N:' 머리줄을 없앤다
    if info is not None:
        info.update(rows=nr, cols=nc, env=env, merged=sum(1 for c in cells if c.rs > 1 or c.cs > 1), hdr=hdr, mode=mode,
                    width_mm=round(tot_mm, 1))
    if info is not None:
        scale = min(1.0, textw_mm / tot_mm) if tot_mm else 1.0
        info['struct'] = dict(
            env=env, rows=nr, cols=nc, colspec=''.join(spec_cols), general=gen_keys, cell_format=cell_keys, lines=line_keys, rowhead=hdr,
            outer=[x.strip() for x in re.split(r',(?=\w+=)', cap[1:-1])] if cap else [],
            cells=[[dict(text=(body[id(own[r][x])][0] if own[r][x].r == r and own[r][x].c == x else ''),
                         row_span=(own[r][x].rs if own[r][x].r == r and own[r][x].c == x else 1),
                         col_span=(own[r][x].cs if own[r][x].r == r and own[r][x].c == x else 1)) for x in range(nc)] for r in range(nr)],
            widths_mm=[W[x] * HU_MM * scale * (tot_mm / (total * HU_MM) if total else 1) for x in range(nc)])
    out = '\\begin{%s}%s{\n  %s\n}\n%s\n\\end{%s}' % (ename, cap, ',\n  '.join(keys), '\n'.join(lines), ename)
    return out


# ───────────────────────── tblrDoumi(.tblr, JSON) ─────────────────────────
TBLR_FORMAT_VERSION = '3.9'


def _mm2pt(t):
    """tblrDoumi 의 테두리 미리보기는 pt 단위 굵기를 읽는다"""
    return re.sub(r'wd=([\d.]+)mm', lambda m: 'wd=%.2fpt' % (float(m.group(1)) * 72.27 / 25.4), t)


def tblr_json(st):
    """table_tex 가 info['struct'] 로 돌려준 구조 -> tblrDoumi 의 .tblr (JSON) 내용.
    tblrDoumi 의 저장·불러오기(TblrGenerator.save_table / load_table, 형식 3.9)와 latex_code 조립 순서를 그대로 따른다:
    colspec, 선(lines), 행 서식, 칸 서식, 일반 설정, (long 환경의) 추가 설정, 병합 cell{r}{c}={r=,c=}{} 순."""
    lines_ = [_mm2pt(x) for x in st['lines']]
    inner_extra = 'rowhead = %d' % st['rowhead'] if st['rowhead'] and st['env'] != 'tblr' else ''
    outer = '\n'.join(st['outer']) if st['env'] != 'tblr' else ''
    code = ['\\begin{%s}%s{' % (st['env'], ('[\n  %s\n]' % ',\n  '.join(st['outer'])) if outer else '')]
    code.append('  colspec = {%s},' % st['colspec'])
    for x in lines_ + st['cell_format'] + st['general'] + ([inner_extra] if inner_extra else []): code.append('  %s,' % x)
    for r, row in enumerate(st['cells']):
        for c, cell in enumerate(row):
            if cell['row_span'] > 1 or cell['col_span'] > 1:
                code.append('  cell{%d}{%d} = {r=%d, c=%d}{},' % (r + 1, c + 1, cell['row_span'], cell['col_span']))
    code.append('}')
    covered = set()
    for r, row in enumerate(st['cells']):
        for c, cell in enumerate(row):
            for dr in range(cell['row_span']):
                for dc in range(cell['col_span']):
                    if dr or dc: covered.add((r + dr, c + dc))
    for r, row in enumerate(st['cells']):
        code.append('  ' + ' & '.join('' if (r, c) in covered else cell['text'] for c, cell in enumerate(row)) + ' \\\\')
    code.append('\\end{%s}' % st['env'])
    return {
        'tblr_format_version': TBLR_FORMAT_VERSION, 'env_type': st['env'], 'outer_options': outer, 'inner_extra': inner_extra,
        'lines': '\n'.join(lines_), 'rows': st['rows'], 'cols': st['cols'], 'row_format': '',
        'cell_format': '\n'.join(st['cell_format']), 'generic_option': '\n'.join(st['general']), 'colspec': st['colspec'],
        'latex_code': '\n'.join(code),
        'cells': [[dict(text=('' if (r, c) in covered else cell['text']), row_span=cell['row_span'], col_span=cell['col_span']) for c, cell in enumerate(row)] for r, row in enumerate(st['cells'])],
        'column_widths': [int(min(400, max(80, round(w * 96 / 25.4)))) for w in st['widths_mm']],
        'radio_state': 'manual', 'bottomrule_checked': False, 'extra_cmd_text': ''}


# ───────────────────────── 문서 -> 파일 ─────────────────────────
def find_tables(doc):
    """바깥 표만 문서 순서대로 (표 안의 표는 바깥 표가 데리고 간다)"""
    out = []
    def walk(e, inside):
        for ch in e:
            if lname(ch) == 'tbl':
                if not inside: out.append(ch)
                walk(ch, True)
            else:
                walk(ch, inside)
    for r in doc.roots: walk(r, False)
    return out


def table_text_preview(tbl):
    t = ' '.join(''.join(x.itertext()) for x in tbl.iter(p_('t')))
    return ' '.join(t.split())[:40]


def build_parser():
    ap = argparse.ArgumentParser(description='hwpx 의 표 -> tabularray (tblr/longtblr)  (version %s)' % __version__)
    ap.add_argument('-V', '--version', action='version', version='hwpx2tblr %s' % __version__)
    ap.add_argument('input', help='.hwpx 파일')
    ap.add_argument('-o', '--output', help='출력 .tex (기본: 입력 이름.tblr.tex)')
    ap.add_argument('--split', action='store_true', help='표 하나마다 파일 하나로 낸다. -o 는 폴더 이름(기본: 입력이름_tblr/), 파일 이름은 table-001.tex …')
    ap.add_argument('--format', choices=['tex', 'tblr'], default='tex', help='tex: LaTeX 코드 / tblr: tblrDoumi 가 여는 .tblr(JSON) 파일을 표마다 하나씩 (--split 을 겸함, -o 는 폴더)')
    ap.add_argument('--standalone', action='store_true', help='바로 컴파일되는 완전한 문서로 낸다 (xelatex)')
    ap.add_argument('--font', default='Noto Serif CJK KR', help='--standalone 의 본문 글꼴 (fontspec)')
    ap.add_argument('--list', action='store_true', help='표 목록만 보여 주고 끝낸다')
    ap.add_argument('--only', help='이 번호의 표만 (쉼표로 여럿, 1부터; 예: 1,3-5)')
    ap.add_argument('--env', choices=['auto', 'tblr', 'longtblr'], default='auto', help='auto: 긴 표만 longtblr')
    ap.add_argument('--long-table', type=float, default=0.7, help='추정 높이가 본문 높이의 이 배 이상이면 longtblr (0=끔, 기본 0.7)')
    ap.add_argument('--long-table-rows', type=int, default=30, help='행이 이 수 이상이면 longtblr (0=끔, 기본 30)')
    ap.add_argument('--colspec', choices=['auto', 'width', 'linewidth', 'fixed', 'natural'], default='auto',
                    help='width: 모든 열을 X[co=칸 너비 비율]로 하고 width=표의 가로 길이(mm) / linewidth: width=\\linewidth / fixed: 칸마다 Q[wd=mm] / natural: 글 길이대로 / auto: width 이되 본문 너비보다 길면 본문 너비로 줄임')
    ap.add_argument('--textwidth', type=float, default=0, help='본문 너비(mm). 기본은 문서의 쪽 설정')
    ap.add_argument('--no-margins', dest='margins', action='store_false', help='한글의 칸 안쪽 여백을 쓰지 않고 tabularray 기본값을 쓴다')
    ap.add_argument('--max-sep', type=float, default=5.0, help='칸 안쪽 여백의 최대(mm, 기본 5)')
    ap.add_argument('--min-sep', type=float, default=0.8, help='칸 안쪽 여백의 최소(mm, 기본 0.8)')
    ap.add_argument('--no-borders', dest='borders', action='store_false', help='테두리를 옮기지 않는다')
    ap.add_argument('--no-fills', dest='fills', action='store_false', help='바탕색을 옮기지 않는다')
    ap.add_argument('--no-format', dest='format', action='store_false', help='굵게·기울임·밑줄·취소선을 옮기지 않는다')
    ap.add_argument('--justify', action='store_true', help='양쪽 정렬 문단을 j(양쪽 맞춤)로 낸다 (기본 l)')
    ap.add_argument('--no-wavedash', dest='wavedash', action='store_false', help='∼(U+223C)를 물결표(U+301C)로, 곧은 따옴표를 굽은 따옴표로 바꾸지 않는다')
    ap.add_argument('--header', choices=['auto', 'first', 'none'], default='auto', help='longtblr 머리글 행: 한글의 제목 행 / 첫 행 / 없음')
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    WAVE['on'] = a.wavedash
    doc = Doc(a.input)
    tbls = find_tables(doc)
    only = None
    if a.only:
        only = set()
        for tok in a.only.split(','):
            m = re.fullmatch(r'(\d+)(?:-(\d+))?', tok.strip())
            if not m: ap.error('--only 형식: 1,3-5')
            only |= set(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    out, infos, parts = [], [], []
    all_colors, all_need, all_warn = set(), set(), []
    for i, t in enumerate(tbls, 1):
        if only is not None and i not in only: continue
        info = {}
        doc.colors, doc.need, doc.warn = set(), set(), []                 # 표마다 따로 모아 --split 이 표 하나의 파일에 그 표가 쓴 것만 적게 한다
        tex = table_tex(doc, t, a, info=info)
        parts.append((i, info, tex, set(doc.colors), set(doc.need), list(doc.warn)))
        all_colors |= doc.colors; all_need |= doc.need; all_warn += doc.warn
        infos.append((i, info, table_text_preview(t)))
        out.append('%% 표 %d: %d행 %d열%s  “%s”\n%s' % (i, info['rows'], info['cols'], ('' if not info['merged'] else ', 병합 %d' % info['merged']), table_text_preview(t), tex))
    doc.colors, doc.need, doc.warn = all_colors, all_need, all_warn
    if a.list:
        for i, info, pv in infos: print('%3d  %2d행 %2d열  병합 %-2d  %-8s %6.1fmm  %s' % (i, info['rows'], info['cols'], info['merged'], info['env'], info['width_mm'], pv))
        return 0
    if not out:
        print('표가 없습니다', file=sys.stderr); return 1
    if a.format == 'tblr':
        d = a.output or os.path.splitext(a.input)[0] + '_tblr'
        os.makedirs(d, exist_ok=True)
        for i, info, tex, cols, need, warn in parts:
            with open(os.path.join(d, 'table-%03d.tblr' % i), 'w', encoding='utf-8') as fh:
                json.dump(tblr_json(info['struct']), fh, ensure_ascii=False, indent=2)
        if all_colors:
            with open(os.path.join(d, 'colors.tex'), 'w', encoding='utf-8') as fh:
                fh.write('%% 표의 바탕색. 문서 머리부(preamble)에 넣으십시오 (xcolor 필요)\n' + ''.join('\\providecolor{hwp%s}{HTML}{%s}\n' % (c, c) for c in sorted(all_colors)))
        print('표 %d개 -> %s/table-NNN.tblr%s' % (len(parts), d, ' (+ colors.tex)' if all_colors else ''), file=sys.stderr)
        for w in sorted(set(all_warn)): print('경고:', w, file=sys.stderr)
        return 0
    if a.split:
        d = a.output or os.path.splitext(a.input)[0] + '_tblr'
        os.makedirs(d, exist_ok=True)
        for i, info, tex, cols, need, warn in parts:
            pk1 = ','.join(['tabularray', 'xcolor'] + sorted(need))
            head1 = ['%% hwpx2tblr %s — %s 의 표 %d (%d행 %d열)' % (__version__, os.path.basename(a.input), i, info['rows'], info['cols']),
                     '%% 필요한 패키지: \\usepackage{%s}' % pk1] + ['\\providecolor{hwp%s}{HTML}{%s}' % (c, c) for c in sorted(cols)]
            if a.standalone:
                txt = '\n'.join(['\\documentclass[10pt]{article}', '\\usepackage[a4paper,margin=18mm]{geometry}', '\\usepackage{%s}' % pk1,
                                 '\\usepackage{fontspec}', '\\setmainfont{%s}' % a.font, '\\pagestyle{empty}', '\\setlength{\\parindent}{0pt}',
                                 '\\begin{document}'] + head1[0:1] + head1[2:]) + '\n\n' + tex + '\n\n\\end{document}\n'
            else:
                txt = '\n'.join(head1) + '\n\n' + tex + '\n'
            with open(os.path.join(d, 'table-%03d.tex' % i), 'w', encoding='utf-8') as fh: fh.write(txt)
        print('표 %d개 -> %s/table-NNN.tex' % (len(parts), d), file=sys.stderr)
        for w in sorted(set(all_warn)): print('경고:', w, file=sys.stderr)
        return 0
    pk = ['tabularray', 'xcolor'] + sorted(doc.need)
    pk = [','.join(pk)]
    head = ['%% hwpx2tblr %s — %s' % (__version__, os.path.basename(a.input)),
            '%% 필요한 패키지: \\usepackage{%s}' % pk[0],
            '%% (longtblr 를 쓰려면 tabularray 가 필요합니다. 본문 글꼴은 한글을 담은 것이어야 합니다.)']
    head += ['\\providecolor{hwp%s}{HTML}{%s}' % (c, c) for c in sorted(doc.colors)]
    body = '\n\n'.join(out) + '\n'
    if a.standalone:
        txt = '\n'.join(['\\documentclass[10pt]{article}', '\\usepackage[a4paper,margin=18mm]{geometry}',
                         '\\usepackage{%s}' % pk[0], '\\usepackage{fontspec}', '\\setmainfont{%s}' % a.font,
                         '\\pagestyle{empty}', '\\setlength{\\parindent}{0pt}', '\\begin{document}'] + head[0:1] + head[3:]) + '\n\n'
        txt += '\n\n\\bigskip\n\n'.join(out) + '\n\n\\end{document}\n'
    else:
        txt = '\n'.join(head) + '\n\n' + body
    outp = a.output or os.path.splitext(a.input)[0] + '.tblr.tex'
    with open(outp, 'w', encoding='utf-8') as fh: fh.write(txt)
    print('표 %d개 -> %s' % (len(out), outp), file=sys.stderr)
    for w in sorted(set(doc.warn)): print('경고:', w, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
