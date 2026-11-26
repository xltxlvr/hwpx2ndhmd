# -*- coding: utf-8 -*-
"""hwpx -> (ndh)md 변환기

 - 레이아웃 무시, 텍스트·수식 보존, 그림은 자리만, 표는 변환 가능한 것만 변환(아니면 자리 + 선택적으로 셀 글)
 - 문단 스타일 -> 환경  :::{이름} ... :::      (개요 N / 개요 수준이 있는 문단은 # 헤딩)
 - 스타일이 없는 문서를 위한 헤딩 추정(--headings=auto)
 - 글상자·표 셀 글 등 인용 형태로 남기는 것은 :::{quote} 로 낸다
수식은 hwpeq.py (rhwp 규칙 기반) 가 LaTeX 로 바꾼다.
"""
import sys, os, re, io, json, zipfile, argparse, collections, posixpath
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hwpeq

__version__ = '0.0.4'

PN = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HN = 'http://www.hancom.co.kr/hwpml/2011/head'
p_ = lambda t: '{%s}%s' % (PN, t)
h_ = lambda t: '{%s}%s' % (HN, t)

PLAIN_STYLES = {'바탕글', '본문', 'Normal', 'Body'}                      # 환경으로 만들지 않는 기본 스타일
SKIP_STYLES = {'머리말', '꼬리말', 'Header', 'Footer', '메모', 'Memo', '쪽 번호', 'Page Number'}   # 각주·미주 스타일은 본문에 글이 있으면 그 글을 살린다
OUTLINE_RE = re.compile(r'^(?:개요|Outline)\s*(\d+)$')
TITLE_RE = re.compile(r'제목|title|heading|소제목|대제목', re.I)
EQ_RE = '\x01[^\x02]*\x02'
KINDS = [  # (이름, 정규식, 번호체계 깊이를 알려 주는 그룹) -- 번호 머리표 뒤에 제목 내용이 있어야 한다
    ('chapter', re.compile(r'^(?:제\s*\d+\s*[장편부절]|chapter\s+\d+|part\s+[IVX\d]+)\s*\S', re.I)),
    ('dotnum',  re.compile(r'^\d+(?:\.\d+)*\.?\s+\S')),
    ('paren',   re.compile(r'^\d+\)\s*\S')),
    ('paren2',  re.compile(r'^\(\d+\)\s*\S')),
    ('hangul',  re.compile(r'^[가-힣][.)]\s*\S')),
    ('roman',   re.compile(r'^[IVX]+\.\s*\S')),
    ('circled', re.compile(r'^[①-⑳]\s*\S')),
]


class Ctx:
    def __init__(self, a, z):
        self.a = a
        self.stats = collections.Counter()
        hd = ET.fromstring(z.read('Contents/header.xml'))
        self.styles = {s.get('id'): s for s in hd.iter(h_('style'))}
        self.parapr = {p.get('id'): p for p in hd.iter(h_('paraPr'))}
        self.charpr = {c.get('id'): c for c in hd.iter(h_('charPr'))}
        self.smap = {}
        if a.style_map:
            self.smap = json.load(open(a.style_map, encoding='utf8'))
        self.used_styles = collections.Counter()
        self.envs = {}            # 스타일 이름 -> 환경 이름
        self.zip = z
        self.manifest = {}
        try:
            for it in ET.fromstring(z.read('Contents/content.hpf')).iter('{http://www.idpf.org/2007/opf/}item'):
                self.manifest[it.get('id')] = it.get('href')
        except Exception:
            pass
        self.outdir = os.path.dirname(os.path.abspath(a.output)) if a.output else os.getcwd()
        self.image_files = {}; self.image_info = []; self.warn = []; self.consumed = set()
        self.display_list = []
        self.tops = []; self.top_index = {}; self.image_sizes = []; self.textwidth = 51026
        self.headings = []        # 보고용
        self.endnotes = []; self._note_ids = set()      # 본문에서 만난 미주 (마지막에 모아 낸다)
        self.numdefs = {}                               # numbering id -> {수준(1~): (모양 글, 형식, 시작값)}
        for nm in hd.iter(h_('numbering')):
            lv = {}
            for ph in nm.findall(h_('paraHead')):
                lv[int(ph.get('level') or 1)] = (ph.text or '', ph.get('numFormat') or 'DIGIT', int(ph.get('start') or 1))
            self.numdefs[nm.get('id')] = lv
        self.in_note = False; self.used_endnote = False
        self.pending_notes = []                         # 지금 문단의 각주 정의 (문단 다음에 낸다)
        self.fn_labels = set()
        self.numcount = {}                              # numbering id -> [수준별 센 개수]

    # ---- 스타일 해석
    def style_name(self, p):
        s = self.styles.get(p.get('styleIDRef'))
        return s.get('name') if s is not None else ''

    def env_for(self, name):
        """스타일 이름 -> 환경 이름 (로마자). 서로 다른 이름이 같은 로마자가 되면 -2, -3 을 붙여 구별한다."""
        if name in self.envs: return self.envs[name]
        base = env_name(name) if self.a.env_names == 'romanize' else re.sub(r'[{}:\\\s]+', '-', name.strip())
        cand, k = base, 2
        while cand in self.envs.values():                 # 이름이 겹치면 로마 숫자를 붙인다 (글자만 허용)
            cand = base + roman(k); k += 1
        if self.a.env_names == 'romanize' and not re.fullmatch(r'[A-Za-z]+', cand): self.warn.append('환경 이름 %r 에 글자가 아닌 문자가 있습니다' % cand)
        self.envs[name] = cand
        return cand

    def outline_level(self, p):
        pr = self.parapr.get(p.get('paraPrIDRef'))
        if pr is not None:
            hd = pr.find(h_('heading'))
            if hd is not None and hd.get('type') == 'OUTLINE':
                return int(hd.get('level') or 0) + 1
        m = OUTLINE_RE.match(self.style_name(p))
        return int(m.group(1)) if m else None

    def number_prefix(self, p):
        """'문단 번호'(heading type=NUMBER) 가 걸린 문단이면 번호 글을 돌려준다. 번호 숫자는 {1}. 처럼 중괄호로 싸서
        마크다운 목록(1.)으로 읽히지 않게 한다. 번호는 numbering 마다 수준별로 이어서 센다."""
        pr = self.parapr.get(p.get('paraPrIDRef'))
        hd = pr.find(h_('heading')) if pr is not None else None
        if hd is None or hd.get('type') != 'NUMBER': return ''
        nid = hd.get('idRef'); lvl = int(hd.get('level') or 0) + 1
        defs = self.numdefs.get(nid)
        if not defs or lvl not in defs: return ''
        cnt = self.numcount.setdefault(nid, [0] * 10)
        cnt[lvl - 1] += 1
        for k in range(lvl, 10): cnt[k] = 0              # 더 깊은 수준은 다시 센다
        tmpl = defs[lvl][0]
        if not tmpl: return ''
        def rep(m):
            k = int(m.group(1)); d = defs.get(k)
            if d is None: return m.group(0)
            return '{%s}' % num_format(cnt[k - 1] - 1 + d[2], d[1])
        return re.sub(r'\^(\d)', rep, tmpl)

    def char_props(self, run):
        c = self.charpr.get(run.get('charPrIDRef'))
        if c is None: return (0, False, '#000000')
        return (int(c.get('height') or 0), c.find(h_('bold')) is not None, c.get('textColor') or '#000000')


_HANGUL_SYL = '가나다라마바사아자차카타파하'
_HANGUL_JAMO = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ'
_CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'


def num_format(n, fmt):
    """번호 값 -> 한글 numFormat 모양"""
    def pick(chars, off=0):
        return chars[(n - 1) % len(chars)] if n >= 1 else str(n)
    if fmt == 'CIRCLED_DIGIT': return _CIRC[n - 1] if 1 <= n <= 20 else str(n)
    if fmt == 'HANGUL_SYLLABLE': return pick(_HANGUL_SYL)
    if fmt == 'HANGUL_JAMO': return pick(_HANGUL_JAMO)
    if fmt == 'CIRCLED_HANGUL_SYLLABLE': return chr(0x326E + (n - 1)) if 1 <= n <= 14 else str(n)
    if fmt == 'CIRCLED_HANGUL_JAMO': return chr(0x3260 + (n - 1)) if 1 <= n <= 14 else str(n)
    if fmt == 'LATIN_CAPITAL': return pick('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    if fmt == 'LATIN_SMALL': return pick('abcdefghijklmnopqrstuvwxyz')
    if fmt == 'ROMAN_CAPITAL': return roman(n)
    if fmt == 'ROMAN_SMALL': return roman(n).lower()
    return str(n)


# ===================== 그림 =====================
AUTO_COMMENT = re.compile(r'^(그림입니다\.?|원본 그림의 이름:.*|원본 그림의 크기:.*)$')   # 한글이 자동으로 넣는 설명
LABEL_RE = re.compile(r'^\s*[\[(<《]?\s*(?:그림|도|Figure|Fig\.?)\s*\d+(?:[-.]\d+)*\s*[\])>》]?\s*[.:：]?\s*(.*)$', re.I | re.S)


def clean_caption(t):
    return re.sub(r'\s+', ' ', re.sub(r'[\[\]]', '', t)).strip()


def section_paths(z):
    """HWPX 본문 구역(Contents/sectionN.xml)을 패키지(content.hpf)의 읽기 순서대로 돌려준다.
    목록에서 빠진 구역은 파일 이름의 번호순으로 뒤에 붙인다."""
    package_path = 'Contents/content.hpf'
    names = set(z.namelist())
    section_re = re.compile(r'(?:^|/)section(\d+)\.xml$')
    ordered = []
    try:
        package = ET.fromstring(z.read(package_path))
        OPF = '{http://www.idpf.org/2007/opf/}'
        manifest = {}
        for item in package.iter(OPF + 'item'):
            href = item.get('href')
            if not href: continue
            path = posixpath.normpath(href.lstrip('/') if href.startswith('/')
                                      else posixpath.join(posixpath.dirname(package_path), href))
            manifest[item.get('id')] = path
        for itemref in package.iter(OPF + 'itemref'):
            path = manifest.get(itemref.get('idref'))
            if path in names and section_re.search(path):
                ordered.append(path)
    except (KeyError, ET.ParseError):
        pass
    found = sorted((int(m.group(1)), n) for n in names for m in [section_re.search(n)] if m)
    ordered += [n for _, n in found if n not in ordered]
    return list(dict.fromkeys(ordered))


def normalize_para_text(s, keep_breaks=False):
    """공백 정리. keep_breaks 이면 줄 끝 두 칸 이상(한글의 강제 줄바꿈)을 마크다운 줄바꿈으로 남긴다.
    아니면 예전처럼 줄바꿈 표지도 한 칸 공백으로 눌러 버린다."""
    if not keep_breaks:
        return re.sub(r'[ \t]{2,}', ' ', s)
    lines = []
    for line in s.split('\n'):
        trailing = len(line) - len(line.rstrip(' \t'))
        body = re.sub(r'[ \t]{2,}', ' ', line[:-trailing] if trailing else line)
        lines.append(body + ('  ' if trailing >= 2 else ''))
    return '\n'.join(lines)


def image_caption(ctx, pic, p):
    """캡션 추정: (1) 그림의 caption 요소 (2) 사용자가 쓴 대체 글(자동 문구 제외) (3) 바로 다음 문단이 '그림 N. …' 꼴일 때"""
    cap = pic.find(p_('caption'))
    if cap is not None:
        t = clean_caption(' '.join(x.text or '' for x in cap.iter(p_('t'))))
        if t: return t
    sc = pic.find(p_('shapeComment'))
    if sc is not None and sc.text:
        lines = [l.strip() for l in sc.text.splitlines() if l.strip() and not AUTO_COMMENT.match(l.strip())]
        if lines: return clean_caption(' '.join(lines))
    i = ctx.top_index.get(id(p))
    if i is not None and i + 1 < len(ctx.tops):
        nxt = ctx.tops[i + 1]
        if not any(True for _ in nxt.iter(p_('pic'))) and not any(True for _ in nxt.iter(p_('equation'))):
            txt = ''.join(x.text or '' for x in nxt.iter(p_('t'))).strip()
            m = LABEL_RE.match(txt) if 0 < len(txt) <= 80 else None
            if m:
                ctx.consumed.add(i + 1)          # 번호 머리표는 조판이 붙이므로 이 문단은 캡션으로 흡수한다
                return clean_caption(m.group(1))
    return ''


def clip_fractions(ctx, pic):
    """hwpx 의 그림 잘라내기 -> (l, t, r, b) 비율. 잘라내지 않으면 None."""
    clip, dim = pic.find(p_('imgClip')), pic.find(p_('imgDim'))
    if not ctx.a.crop or clip is None or dim is None: return None
    dw, dh = int(dim.get('dimwidth') or 0), int(dim.get('dimheight') or 0)
    if not dw or not dh: return None
    l, r, t, b = (int(clip.get(k) or 0) for k in ('left', 'right', 'top', 'bottom'))
    if (l, t, r, b) == (0, 0, dw, dh) or not (0 <= l < r <= dw and 0 <= t < b <= dh): return None
    return (l / dw, t / dh, r / dw, b / dh)


def _png_chunk(tag, data):
    import zlib, struct
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)


def bmp24_to_png(raw, frac):
    """압축 없는 24비트 BMP -> PNG 바이트 (표준 라이브러리만 사용). 해당하지 않으면 None.
    frac 가 있으면 비율로 잘라 내고, 색이 256개 이하이면 팔레트 PNG 로 줄인다."""
    import zlib, struct
    if raw[:2] != b'BM' or len(raw) < 54: return None
    off = struct.unpack_from('<I', raw, 10)[0]
    hs, w, h, planes, bpp, comp = struct.unpack_from('<IiiHHI', raw, 14)
    if hs < 40 or bpp != 24 or comp != 0 or w <= 0 or h == 0: return None
    top_down = h < 0; h = abs(h); stride = ((w * 3 + 3) // 4) * 4
    if off + stride * h > len(raw): return None
    rows = [raw[off + y * stride: off + y * stride + w * 3] for y in range(h)]
    if not top_down: rows.reverse()
    x0, y0, x1, y1 = 0, 0, w, h
    if frac:
        x0, y0, x1, y1 = round(frac[0] * w), round(frac[1] * h), round(frac[2] * w), round(frac[3] * h)
        if x1 <= x0 or y1 <= y0: x0, y0, x1, y1 = 0, 0, w, h
    rgb = []
    for row in rows[y0:y1]:
        row = row[x0 * 3:x1 * 3]
        o = bytearray(len(row)); o[0::3] = row[2::3]; o[1::3] = row[1::3]; o[2::3] = row[0::3]    # BGR -> RGB
        rgb.append(bytes(o))
    W, H = x1 - x0, y1 - y0
    colors = {}
    for row in rgb:
        for i in range(0, len(row), 3):
            colors.setdefault(row[i:i + 3], len(colors))
            if len(colors) > 256: break
        if len(colors) > 256: break
    if len(colors) <= 256:                                                  # 팔레트 PNG
        pal = b''.join(c for c, _ in sorted(colors.items(), key=lambda kv: kv[1]))
        data = b''.join(b'\x00' + bytes(colors[row[i:i + 3]] for i in range(0, len(row), 3)) for row in rgb)
        ihdr = struct.pack('>IIBBBBB', W, H, 8, 3, 0, 0, 0); extra = _png_chunk(b'PLTE', pal)
    else:                                                                    # RGB, 줄마다 Sub 필터
        out = []
        for row in rgb:
            out.append(b'\x01' + row[:3] + bytes((row[i] - row[i - 3]) & 255 for i in range(3, len(row))))
        data = b''.join(out); ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0); extra = b''
    return (b'\x89PNG\r\n\x1a\n' + _png_chunk(b'IHDR', ihdr) + extra
            + _png_chunk(b'IDAT', zlib.compress(data, 9)) + _png_chunk(b'IEND', b''))


def save_image(ctx, pic, ref):
    """BinData 그림을 꺼내 PNG 로 저장하고 md 에서 쓸 경로를 돌려준다 (BMP -> PNG, 잘라내기 반영).
    Pillow 가 있으면 그것을, 없으면 24비트 BMP 에 한해 순수 파이썬으로 변환한다. 나머지는 원본 그대로 저장하고 경고한다."""
    if ref in ctx.image_files: return ctx.image_files[ref]
    href = ctx.manifest.get(ref)
    if not href or href not in ctx.zip.namelist():
        ctx.image_files[ref] = None; return None
    raw = ctx.zip.read(href); ext = os.path.splitext(href)[1].lower()
    name = '%s%s' % (ctx.a.image_prefix, ref)
    outdir = os.path.join(ctx.outdir, ctx.a.image_dir) if ctx.a.image_dir != '.' else ctx.outdir
    os.makedirs(outdir, exist_ok=True)
    frac = clip_fractions(ctx, pic)
    try:
        from PIL import Image
        if ctx.a.no_pillow: raise ImportError('--no-pillow')
    except ImportError:
        Image = None
    fn = None; how = ''
    if Image is not None:
        try:
            im = Image.open(io.BytesIO(raw)); im.load()
            crop = (round(frac[0] * im.width), round(frac[1] * im.height), round(frac[2] * im.width), round(frac[3] * im.height)) if frac else None
            if ext in ('.png', '.jpg', '.jpeg') and crop is None:
                fn = name + ('.jpg' if ext == '.jpeg' else ext); open(os.path.join(outdir, fn), 'wb').write(raw)
            else:
                if crop: im = im.crop(crop)
                if im.mode not in ('RGB', 'RGBA', 'L', 'P'): im = im.convert('RGB')
                if im.mode == 'RGB':
                    cols = im.getcolors(256)
                    if cols is not None: im = im.convert('P', palette=Image.ADAPTIVE, colors=len(cols))
                fn = name + '.png'; im.save(os.path.join(outdir, fn), optimize=True); how = 'Pillow'
        except Exception as e:
            ctx.warn.append('그림 %s(%s) 를 Pillow 로 열지 못했습니다: %s' % (ref, ext, e))
    if fn is None:
        png = bmp24_to_png(raw, frac) if ext == '.bmp' else None
        if png is not None:
            fn = name + '.png'; open(os.path.join(outdir, fn), 'wb').write(png); how = '표준 라이브러리'
        elif ext in ('.png', '.jpg', '.jpeg'):
            fn = name + ('.jpg' if ext == '.jpeg' else ext); open(os.path.join(outdir, fn), 'wb').write(raw)
            if frac: ctx.warn.append('그림 %s: Pillow 가 없어 잘라내기를 적용하지 못했습니다 (원본 그대로 저장).' % ref)
        else:
            fn = name + ext; open(os.path.join(outdir, fn), 'wb').write(raw); ctx.stats['img_raw'] += 1
            ctx.warn.append('그림 %s(%s) 는 PNG 로 바꾸지 못해 원본 그대로 저장했습니다 (Pillow 를 설치하면 더 많은 형식을 바꿀 수 있습니다).' % (ref, ext))
    if frac and how: ctx.stats['img_cropped'] += 1
    ctx.stats['img_saved'] += 1
    ctx.image_info.append((ref, ext.lstrip('.'), len(raw), os.path.getsize(os.path.join(outdir, fn))))
    path = fn if ctx.a.image_dir == '.' else ctx.a.image_dir.rstrip('/') + '/' + fn
    ctx.image_files[ref] = path
    return path


def image_width(ctx, pic, frame_w=None):
    """그림 폭 결정. 문서에 기록된 표시 크기를 본문 너비에 대한 비율로 옮기고 상한(기본 0.75)을 둔다.
    표시 크기를 알 수 없으면(묶음 개체 속 그림 등) 원본 크기와 묶음 크기 중 작은 쪽을 쓰고, 그것도 없으면 기본 폭."""
    if ctx.a.image_size == 'fixed': return ctx.a.image_width, None
    def num(tag, attr='width'):
        e = pic.find(p_(tag)); v = int(e.get(attr) or 0) if e is not None else 0
        return v if v > 0 else None
    w = num('sz') or num('curSz')
    if w is None:
        org = num('orgSz')
        w = min(x for x in (org, frame_w) if x) if (org or frame_w) else None
    if not w: return ctx.a.image_width, None
    r = w / ctx.textwidth
    r = min(r, ctx.a.image_max)
    r = round(r, 2) if r < 0.1 else round(round(r / 0.05) * 0.05, 2)       # 0.1 이상은 0.05 단위로 정돈
    r = max(r, 0.02)
    return '%g\\linewidth' % r, w / 7200 * 2.54                          # 한글 단위: 1/7200 인치


def image_md(ctx, pic, p, frame_w=None):
    ctx.stats['pic'] += 1
    r = pic.find('.//*[@binaryItemIDRef]')
    ref = r.get('binaryItemIDRef') if r is not None else None
    path = save_image(ctx, pic, ref) if ref else None
    if not path: return '<!-- PIC: %s (그림 파일 없음) -->' % ref
    width, cm = image_width(ctx, pic, frame_w)
    ctx.image_sizes.append((ref, cm, width))
    return '![%s](%s){width=%s}' % (image_caption(ctx, pic, p), path, width)


# ===================== 인라인 / 블록 =====================
def quote_block(paras):
    paras = [x for x in paras if x.strip()]
    return ':::{quote}\n' + '\n\n'.join(paras) + '\n:::' if paras else ''


def para_parts(ctx, p):
    """문단 -> [('t', 글), ('b', 블록문자열)] 순서 보존"""
    parts = []
    def t(s): parts.append(('t', s))
    for run in p.findall(p_('run')):
        for ch in run:
            tag = ch.tag.split('}')[1]
            if tag == 't':
                t(ch.text or '')
                for c in ch:
                    ct = c.tag.split('}')[1]
                    if ct == 'tab': t(' ')
                    elif ct == 'lineBreak': t('  \n')
                    t(c.tail or '')
            elif tag == 'ctrl':
                for c in ch:
                    ct = c.tag.split('}')[1]
                    if ct == 'endNote' and ctx.a.endnotes == 'ref':
                        ctx.stats['endnote'] += 1; ctx.used_endnote = True
                        label = footnote_label(ctx, c, 'en')
                        t('[^%s]{end}' % label)                      # ndhmd4tex: mappingrule notes.end -> \endnote{%s}
                        ctx.pending_notes.append((label, footnote_paras(ctx, c, True)))
                    elif ct == 'endNote' and ctx.a.endnotes == 'collect' and id(c) not in ctx._note_ids:
                        ctx._note_ids.add(id(c)); ctx.endnotes.append(c)
                    elif ct == 'footNote' and ctx.a.footnotes != 'drop':
                        ctx.stats['footnote'] += 1
                        label = footnote_label(ctx, c)
                        if ctx.a.footnotes == 'inline':
                            t('^[%s]' % ' '.join(footnote_paras(ctx, c)))
                        else:
                            t('[^%s]' % label)
                            ctx.pending_notes.append((label, footnote_paras(ctx, c)))
            elif tag == 'equation':
                t('\x01' + hwpeq.convert(ch.find(p_('script')).text or '') + '\x02'); ctx.stats['eq'] += 1
            elif tag == 'pic':
                o = ch.find(p_('orgSz'))
                if ctx.in_note and o is not None and int(o.get('width') or 0) <= 2400 and int(o.get('height') or 0) <= 1500:
                    ctx.stats['note_icon'] += 1; continue        # 미주 번호 곁의 '정답' 딱지 같은 작은 그림
                parts.append(('b', image_md(ctx, ch, p)))
            elif tag == 'tbl': parts.append(('b', table(ctx, ch)))
            elif tag in ('rect', 'container', 'connectLine', 'ellipse', 'line', 'polygon', 'curve', 'arc'):
                s = shape(ctx, ch)
                if s: parts.append(('b', s))
    return parts


def para_text(ctx, p):
    # 셀·글상자 글: 글 + 그림(![](…)) 을 이어 붙인다
    return ' '.join(s for k, s in para_parts(ctx, p) if k == 't' or s.startswith('!['))


def cell_paras(ctx, root):
    out = []
    for p in root.iter(p_('p')):
        s = ' '.join(para_text(ctx, p).split())
        if s: out.append(s)
    return out


def shape(ctx, e):
    ctx.stats['shape'] += 1
    paras = []
    for d in e.iter(p_('drawText')):
        for p in d.iter(p_('p')):
            s = ' '.join(para_text(ctx, p).split())
            if s: paras.append(s)
    kind = e.tag.split('}')[1]
    fw = e.find(p_('sz')); fw = int(fw.get('width') or 0) if fw is not None else None
    pics = [image_md(ctx, pc, None, fw) for pc in e.iter(p_('pic')) if not any(pc in list(d.iter()) for d in e.iter(p_('drawText')))]
    if pics:                                                    # 글상자/묶음 개체 안의 그림
        return '\n\n'.join(pics) + ('\n\n' + quote_block(paras) if paras else '')
    if paras:
        return '<!-- SHAPE:%s -->\n%s' % ('textbox', quote_block(paras))
    return '<!-- SHAPE:%s -->' % kind if ctx.a.show_empty_shapes else ''


def table(ctx, t):
    rows = [tr.findall(p_('tc')) for tr in t.findall(p_('tr'))]
    simple = all(c.find(p_('cellSpan')).get('colSpan') == '1' and c.find(p_('cellSpan')).get('rowSpan') == '1' for r in rows for c in r)
    simple = simple and not any(True for _ in t.iter(p_('pic'))) and not any(x is not t for x in t.iter(p_('tbl')))
    ctext = lambda c: ' '.join(' '.join(cell_paras(ctx, c)).split()).replace('|', '\\|')
    if simple and rows:
        ctx.stats['tbl_ok'] += 1
        L = ['| ' + ' | '.join(ctext(c) for c in rows[0]) + ' |', '|' + '---|' * len(rows[0])]
        L += ['| ' + ' | '.join(ctext(c) for c in r) + ' |' for r in rows[1:]]
        return '\n'.join(L)
    ctx.stats['tbl_ph'] += 1
    head = '<!-- TABLE %sx%s: 변환 불가(병합/그림 포함) -->' % (t.get('rowCnt'), t.get('colCnt'))
    if not ctx.a.keep_cell_text: return head
    texts = [x for c in (c for r in rows for c in r) for x in cell_paras(ctx, c)]
    return head + '\n' + quote_block(texts)


# ===================== 헤딩 추정 =====================
def kind_of(text):
    for name, rx in KINDS:
        m = rx.match(text)
        if m:
            if name == 'dotnum':
                num = re.match(r'^\d+(?:\.\d+)*', text).group()
                return 'dotnum%d' % (num.count('.') + 1)
            return name
    return None


def visible_len(text):
    return len(re.sub(EQ_RE, 'xx', text).strip())


def para_props(ctx, p):
    tot = big = 0; size = collections.Counter(); bold = 0; colored = 0
    for run in p.findall(p_('run')):
        n = len(''.join(x.text or '' for x in run.findall(p_('t'))).strip())
        if not n: continue
        h, b, col = ctx.char_props(run)
        size[h] += n; tot += n; bold += n if b else 0; colored += n if col.upper() not in ('#000000', '#000') else 0
    if not tot: return None
    return dict(size=size.most_common(1)[0][0], bold=bold / tot > .5, colored=colored / tot > .5)


def heading_candidates(ctx, paras, body_size):
    """자동 추정: 번호 머리표 + 짧음 + (굵음|큰 글자|색) ... 점수가 문턱을 넘는 문단만"""
    cand = {}
    for i, (p, text, kind_hint) in enumerate(paras):
        t = ' '.join(text.split())
        k = kind_of(t)
        if not k: continue
        pr = para_props(ctx, p)
        if pr is None: continue
        rest = re.sub(r'^\S+\s*', '', re.sub(EQ_RE, '', t), count=1)      # 번호 머리표와 수식을 뺀 나머지
        if len(re.findall(r'[A-Za-z가-힣]', rest)) < 2: continue                 # '1) lim …' 같은 문항 번호는 제목이 아니다
        score = 2
        if pr['size'] > body_size: score += 1
        if pr['bold']: score += 1
        if pr['colored']: score += 1
        if visible_len(t) <= ctx.a.heading_maxlen: score += 1
        if not re.search(r'(다|요|까|죠)\s*[.?!]?$|[.?!:;,]$', t): score += 1
        if '\n' in text: score -= 2
        if score >= ctx.a.heading_threshold:
            cand[i] = dict(kind=k, size=pr['size'], bold=pr['bold'], score=score)
    # 번호 종류별로 묶어 (글자 크기, 굵기) 가 큰 쪽이 상위 수준
    groups = collections.OrderedDict()
    for i, c in cand.items(): groups.setdefault(c['kind'], []).append(c)
    ranked = sorted(groups, key=lambda k: (-max(c['size'] for c in groups[k]), -max(c['bold'] for c in groups[k]), list(groups).index(k)))
    for lvl, k in enumerate(ranked):
        for c in groups[k]: c['level'] = min(6, ctx.a.heading_base + lvl)
    return cand


# ===================== 디스플레이 수식 추정 =====================
EQ_ONLY = re.compile(r'^\s*(?:\x01[^\x02]*\x02\s*)+[,.;]?\s*$')


def display_math(ctx, text):
    """수식만 있는 줄이면 [(LaTeX, 점수), …] 를, 아니면 None.
    HWP 문서는 거의 모든 수식을 글자처럼(인라인) 넣기 때문에 구조로 추정한다:
      수식만 있는 줄(필수 3점) + 분수·극한·합·적분·루트·행렬·left(+1) + 길이 14자 이상(+1) + 등호·부등호(+1) - 아주 짧은 식(-2)
    수식 사이 공백이 없거나 짧으면 한 식으로 이어 붙이고(\\quad), 길게(6칸 이상) 떨어져 있으면 별개의 식으로 나눈다."""
    if not EQ_ONLY.match(text): return None
    pieces = re.split('(\x01[^\x02]*\x02)', text.strip())
    groups = [[]]; punct = ''
    for i, pc in enumerate(pieces):
        if pc.startswith('\x01'): groups[-1].append(pc[1:-1]); continue
        if i == len(pieces) - 1: punct = pc.strip(); continue
        if i == 0: continue
        if len(pc) >= 6: groups.append([])                   # 긴 공백 = 별개의 식 (한 줄에 나란히 놓은 두 식 등)
        elif pc: groups[-1].append(r'\quad ')
    res = []
    for gi, g in enumerate(groups):
        m = re.sub(r'^(?:\\quad\s*)+|(?:\\quad\s*)+$', '', ''.join(g)).strip()
        if not m: continue
        if gi == len(groups) - 1: m += punct
        score = 3
        if re.search(r'\\(frac|lim|sum|int|prod|sqrt|begin|left)', m): score += 1
        if len(m) >= 14: score += 1
        if re.search(r'=|\\le\b|\\ge\b|\\ne\b|\\approx|<|>', m): score += 1
        if len(m) < 8: score -= 2
        res.append((m, score))
    return res or None


# ===================== 변환 =====================
def lsafe(s):
    """문단 첫머리가 마크다운 목록·제목·인용으로 읽히지 않게 한다.
    글로 쓴 번호 '1. ' / '2)' 는 {1}. 꼴로(문단 번호와 같은 방식), '* ' '- ' '+ ' '# ' '> ' 는 역슬래시로 막는다."""
    m = re.match(r'^(\d{1,9})([.)])(\s|$)', s)
    if m: return '{%s}%s%s' % (m.group(1), m.group(2), s[m.end(1) + 1:])
    m = re.match(r'^([*+\-#>])(\s|$)', s)
    if m: return '\\' + s
    return s


_MATH_SPLIT = re.compile(r'(\$\$.*?\$\$|\x01[^\x02]*\x02)', re.S)


def split_links(md):
    """본문 글에서 ] 바로 뒤에 [ 나 ( 가 오면 마크다운이 참조 링크 [글][이름] / 링크 [글](주소) 로 읽는다
    (각주 앵커 [^3][눈썹…] 도 마찬가지). 그 사이에 빈 TeX 묶음 {} 을 끼워 떼어 놓는다.
    수식($…$, $$…$$)과 그림(![…](…))·주석(<!--)·정의 머리([^3]:) 는 건드리지 않는다."""
    out = []; disp = False
    for line in md.split('\n'):
        if line.strip() in ('$$', '\\[', '\\]'): disp = line.strip() != '\\]' and not (line.strip() == '$$' and disp); out.append(line); continue
        if disp or line.startswith(('![', '<!--', '|')) or ']' not in line:     # $$ 블록 안은 수식
            out.append(line); continue
        out.append(''.join(p if i % 2 else re.sub(r'\](?=[\[(])', ']{}', p) for i, p in enumerate(_MATH_SPLIT.split(line))))
    return '\n'.join(out)


def footnote_label(ctx, fn, prefix=''):
    """각주 이름: 한글의 각주 번호 그대로 ([^12]). 미주는 앞에 en 을 붙인다 ([^en3]). 겹치면 알파벳을 덧붙인다."""
    base = prefix + ((fn.get('number') or str(len(ctx.fn_labels) + 1)).strip() or str(len(ctx.fn_labels) + 1))
    lab, k = base, 0
    while lab in ctx.fn_labels:
        k += 1; lab = base + 'abcdefghijklmnopqrstuvwxyz'[(k - 1) % 26] * ((k - 1) // 26 + 1)
    ctx.fn_labels.add(lab)
    return lab


def footnote_paras(ctx, fn, endnote=False):
    """각주 안 문단들 -> 글(수식 표지 포함) 목록. 그림·표 같은 블록은 그 자리에 문단으로 끼운다."""
    prev = ctx.in_note
    if endnote: ctx.in_note = True                 # 미주 안의 작은 아이콘 그림은 건너뛴다
    try:
        return _footnote_paras(ctx, fn)
    finally:
        ctx.in_note = prev


def _footnote_paras(ctx, fn):
    out = []
    sub = fn.find(p_('subList'))
    for p in (sub.findall(p_('p')) if sub is not None else []):
        acc = ''
        for k, s in para_parts(ctx, p):
            if k == 't': acc += s
            else:
                if acc.strip(): out.append(lsafe(normalize_para_text(acc if ctx.a.keep_linebreaks else acc.replace('  \n', ' '), ctx.a.keep_linebreaks).strip()))
                acc = ''; out.append(s)
        if acc.strip(): out.append(lsafe(normalize_para_text(acc if ctx.a.keep_linebreaks else acc.replace('  \n', ' '), ctx.a.keep_linebreaks).strip()))
    return out or ['']


def footnote_def(label, paras):
    """[^n]: 첫 문단 / (빈 줄) 4칸 들여쓴 나머지 문단"""
    # ndhmd4tex 의 각주는 한 문단이다: 글 문단들은 강제 줄바꿈(줄 끝 두 칸)으로 잇고, 그림·표 같은 블록만 따로 들여쓴 문단으로 둔다
    BLOCK = ('![', '<!--', '|', '\\[', '$$', ':::')
    chunks = []                                     # [('t', [글 문단들]) | ('b', 블록)]
    for r in paras:
        if r.startswith(BLOCK): chunks.append(('b', r))
        elif chunks and chunks[-1][0] == 't': chunks[-1][1].append(r)
        else: chunks.append(('t', [r]))
    out = '[^%s]: ' % label
    for i, (k, v) in enumerate(chunks):
        if k == 't': txt = '  \n'.join(v)
        else: txt = v
        if i == 0: out += txt
        else: out += '\n\n    ' + txt.replace('\n', '\n    ')
    return out


def endnotes_md(ctx):
    """모아 둔 미주 -> [블록 문자열]. 미주마다 '{번호})' 로 시작한다."""
    out = []
    ctx.in_note = True
    for n in ctx.endnotes:
        label = '{%s}%s' % (n.get('number'), chr(int(n.get('suffixChar') or 41)))
        sub = n.find(p_('subList'))
        seq = []
        for p in (sub.findall(p_('p')) if sub is not None else []):
            acc = ''
            for k, s in para_parts(ctx, p):
                if k == 't': acc += s
                else:
                    if acc.strip(): seq.append(lsafe(normalize_para_text(acc, ctx.a.keep_linebreaks).strip()))
                    acc = ''; seq.append(s)
            if acc.strip(): seq.append(lsafe(normalize_para_text(acc, ctx.a.keep_linebreaks).strip()))
        if seq and not seq[0].startswith(('![', '<!--', '|')): seq[0] = label + ' ' + seq[0]
        else: seq.insert(0, label)
        out.extend(seq)
    ctx.in_note = False
    ctx.stats['endnote'] = len(ctx.endnotes)
    return out


def convert(path, a):
    z = zipfile.ZipFile(path)
    ctx = Ctx(a, z)
    roots = [ET.fromstring(z.read(name)) for name in section_paths(z)]
    if not roots: raise ValueError('HWPX 에서 sectionN.xml 본문을 찾지 못했습니다')
    root = roots[0]                                           # 쪽 너비·단 수는 첫 구역 설정을 쓴다
    tops = [p for r in roots for p in r.findall(p_('p'))]
    ctx.stats['section'] = len(roots)
    sp = next((e for r in roots for e in r.iter(p_('secPr'))), None)                  # 본문 너비 = 쪽 너비 - 좌우 여백 (단이 여럿이면 단 수로 나눔)
    if sp is not None and sp.find(p_('pagePr')) is not None:
        pg = sp.find(p_('pagePr')); mg = pg.find(p_('margin'))
        tw = int(pg.get('width') or 0) - int(mg.get('left') or 0) - int(mg.get('right') or 0) - int(mg.get('gutter') or 0)
        cp = next(root.iter(p_('colPr')), None); cols = int(cp.get('colCount') or 1) if cp is not None else 1
        if tw > 0: ctx.textwidth = tw // max(cols, 1)
    ctx.tops = tops; ctx.top_index = {id(p): i for i, p in enumerate(tops)}

    # 본문 글자 크기(최빈값)
    sz = collections.Counter()
    for p in tops:
        for run in p.findall(p_('run')):
            n = len(''.join(x.text or '' for x in run.findall(p_('t'))).strip())
            if n: sz[ctx.char_props(run)[0]] += n
    body_size = sz.most_common(1)[0][0] if sz else 1000

    info = []   # 문단별: parts, text, kind(스타일 종류), 값
    pref = {}
    for i, p in enumerate(tops):
        if a.para_numbers:
            pf = ctx.number_prefix(p)
            if pf: pref[i] = pf; ctx.stats['numbered'] += 1
    for i, p in enumerate(tops):
        if i in ctx.consumed:                          # 그림 캡션으로 흡수된 문단
            info.append((p, '', [])); continue
        ctx.pending_notes = []
        parts = para_parts(ctx, p)
        notes = ctx.pending_notes; ctx.pending_notes = []
        text = ''.join(s for k, s in parts if k == 't')
        # 같은 문단에 그림과 '그림 N. 설명' 글만 있을 때: 글을 캡션으로
        imgs = [j for j, (k, s) in enumerate(parts) if k == 'b' and s.startswith('![]')]
        if len(imgs) == 1 and text.strip() and len(text.strip()) <= 80 and not any('\x01' in s for k, s in parts if k == 't'):
            m = LABEL_RE.match(text.strip())
            if m:
                k0, s0 = parts[imgs[0]]
                parts[imgs[0]] = ('b', '![%s]' % clean_caption(m.group(1)) + s0[3:])
                parts = [x for x in parts if x[0] != 't']; text = ''
        if a.display != 'none' and not [1 for k, _ in parts if k == 'b']:
            dm = display_math(ctx, text)
            if dm and any(sc >= a.display_threshold for _, sc in dm):
                parts = []
                for m, sc in dm:
                    if sc >= a.display_threshold:
                        parts.append(('b', ('\\[\n%s\n\\]' if ctx.a.display_style == 'brackets' else '$$\n%s\n$$') % m)); ctx.stats['display'] += 1; ctx.display_list.append((i, sc, m[:60]))
                    else:
                        parts.append(('b', '$%s$' % m))          # 점수 미달 식은 그 줄에 따로 인라인으로
                text = ''
        parts = list(parts) + [('b', footnote_def(lb, ps)) for lb, ps in notes]      # 각주 정의는 그 문단 바로 뒤에
        info.append((p, text, parts))

    cand = {}
    has_outline = any(ctx.outline_level(p) for p in tops)
    if a.headings == 'auto' and not has_outline:      # 개요 스타일이 있는 문서는 그것을 믿고 추정은 끈다
        cand = heading_candidates(ctx, [(p, t, None) for p, t, _ in info], body_size)

    # 각 문단의 역할 결정: ('h', level) / ('env', name) / ('plain',) / ('skip',)
    roles = []
    for i, (p, text, parts) in enumerate(info):
        name = ctx.style_name(p)
        ctx.used_styles[name] += 1
        role = ('plain',)
        lvl = ctx.outline_level(p) if a.headings != 'none' else None
        m = ctx.smap.get(name, '__none__')
        if name in SKIP_STYLES:
            role = ('plain',) if False else ('plain',)
        if lvl:
            role = ('h', min(6, lvl + a.heading_base - 1)); ctx.stats['h_style'] += 1
        elif isinstance(m, str) and m.startswith('heading:'):
            role = ('h', int(m.split(':')[1]))
        elif m is None:
            role = ('plain',)
        elif isinstance(m, str) and m != '__none__':
            role = ('env', m)
            if not re.fullmatch(r'[A-Za-z]+', m): ctx.warn.append('--style-map 의 환경 이름 %r 은 글자(A-Z, a-z)만으로 되어 있지 않아 ndhmd4tex이 처리하지 못합니다.' % m)
        elif name not in PLAIN_STYLES and name not in SKIP_STYLES and name:
            if a.headings != 'none' and TITLE_RE.search(name) and text.strip():
                role = ('h', a.heading_base); ctx.stats['h_name'] += 1
            else:
                role = ('env', ctx.env_for(name))
        if role == ('plain',) and i in cand and text.strip():
            role = ('h', cand[i]['level']); ctx.stats['h_auto'] += 1
            ctx.headings.append((i, cand[i]['score'], cand[i]['kind'], ' '.join(text.split())[:50]))
        roles.append(role)

    # 빈 문단은 앞뒤가 같은 환경이면 환경을 잇는다
    for i, (p, text, parts) in enumerate(info):
        if roles[i][0] == 'env' or text.strip() or any(k == 'b' for k, _ in parts): continue
        prev = next((roles[j] for j in range(i - 1, -1, -1) if info[j][1].strip()), None)
        nxt = next((roles[j] for j in range(i + 1, len(info)) if info[j][1].strip()), None)
        if prev and prev == nxt and prev[0] == 'env': roles[i] = prev

    # 출력
    out = []; cur = None; buf = []

    def flush():
        nonlocal cur, buf
        if cur is None: return
        body = '\n\n'.join(b for b in buf if b.strip())
        fence = ':::'                                   # 중첩해도 ::: 그대로 (ndhmd4tex 는 :::: 를 인정하지 않는다)
        if body.strip(): out.append('%s{%s}\n%s\n%s' % (fence, cur, body, fence))
        cur = None; buf = []

    def emit(role, text):
        nonlocal cur
        if role[0] == 'env':
            if cur != role[1]: flush(); cur = role[1]
            buf.append(text)
        else:
            flush(); out.append(text)

    for i, ((p, text, parts), role) in enumerate(zip(info, roles)):
        if i in pref and (text.strip() or any(k == 'b' for k, _ in parts)):
            parts = [('t', pref[i] + ' ')] + list(parts); text = pref[i] + ' ' + text
        txt = normalize_para_text(text, ctx.a.keep_linebreaks).strip()
        blocks = [s for k, s in parts if k == 'b']
        if role[0] == 'h' and txt:
            emit(('plain',), '#' * role[1] + ' ' + ' '.join(txt.split()))
            for b in blocks: emit(('plain',), b)
            continue
        # 일반/환경 문단: 글과 블록을 원래 순서로 (글 덩어리 = 한 문단)
        seq = []; acc = ''
        for k, s in parts:
            if k == 't': acc += s
            else:
                if acc.strip(): seq.append(lsafe(normalize_para_text(acc, ctx.a.keep_linebreaks).strip()))
                acc = ''; seq.append(s)
        if acc.strip(): seq.append(lsafe(normalize_para_text(acc, ctx.a.keep_linebreaks).strip()))
        if not seq:
            if role[0] != 'env': flush()
            if role[0] == 'plain' and out and out[-1] != '': out.append('')   # 빈 문단은 한 줄 띄움으로
            continue
        for s in seq: emit(role, s)
    flush()
    if ctx.endnotes and a.endnotes == 'collect':
        out.append(a.endnote_break)
        out.extend(endnotes_md(ctx))
    md = re.sub(r'\n{3,}', '\n\n', '\n\n'.join(x for x in out)).strip() + '\n'
    md = split_links(md)
    md = md.replace('\x02\x01', '')                               # 맞붙은 수식은 하나로 ($a$$b$ 는 $$ 로 읽히므로)
    md = re.sub('\x01([^\x02]*)\x02', r'$\1$', md)             # 남은 수식 표지를 인라인 $…$ 로
    pre = []
    if a.preamble and '$' in md:          # 수식이 하나라도 있으면 front matter 로 패키지를 불러 둔다
        pre.append('\\usepackage{amsmath,amssymb}')
    for pk in (a.custompkg or '').replace(';', ',').split(','):   # --custompkg "esint,mystyle" -> \usepackage{esint} \usepackage{mystyle}
        pk = pk.strip()
        if not pk: continue
        if not re.fullmatch(r'[A-Za-z0-9_.\-]+', pk): ctx.warn.append('--custompkg: 패키지 이름이 이상합니다: %r (그대로 넣음)' % pk)
        line = '\\usepackage{%s}' % pk
        if line not in pre: pre.append(line)
    if getattr(a, 'env_in_preamble', False) and ctx.envs:
        pre += [l for l in env_table_tex(ctx, a.input).splitlines() if l.startswith('\\ifcsname')]
    fm = ''
    if getattr(ctx, 'used_endnote', False):       # [^enN]{end} 를 \endnote{…} 로 바꾸고 문서 끝에 미주를 모은다
        fm += "mappingrule: |\n  notes:\n    end: '\\endnote{%s}'\n"
        pre += ['\\usepackage{endnotes}', '\\AtEndDocument{\\theendnotes}']
    if pre:
        fm += 'preamble+: |\n' + ''.join('  %s\n' % l for l in pre)
    if fm:
        md = '---\n' + fm + '---\n\n' + md
    ctx.needs_other = sorted(set(re.findall(r'\\(?:oiint|oiiint)\b', md)))   # amsmath/amssymb 만으로는 안 되는 명령
    return md, ctx


def env_table_tex(ctx, src):
    """스타일 이름 -> 환경 이름 대응표(주석)와, 한꺼번에 정의하는 \\newenvironment 목록.
    이미 정의된 환경이면 건드리지 않도록 \\ifcsname 으로 감싼다 (quote 같은 기본 환경과 충돌하지 않게)."""
    names = sorted(ctx.envs.items(), key=lambda kv: kv[1].lower())
    w = max(len(k) for k, _ in names) if names else 0
    L = ['%% hwpx 스타일 이름 -> 환경 이름 대응표  (원본: %s)' % os.path.basename(src),
         '% 아래 정의는 비어 있는 틀입니다. 환경마다 모양을 채워 쓰세요.', '%']
    for k, v in names:
        L.append('%%   %-*s -> %-24s (%d문단)' % (w, k, v, ctx.used_styles.get(k, 0)))
    L.append('')
    for k, v in names:
        L.append('\\ifcsname %s\\endcsname\\else\\newenvironment{%s}{}{}\\fi %% %s' % (v, v, k))
    return '\n'.join(L) + '\n'


_CHO = ['g', 'kk', 'n', 'd', 'tt', 'r', 'm', 'b', 'pp', 's', 'ss', '', 'j', 'jj', 'ch', 'k', 't', 'p', 'h']
_JUNG = ['a', 'ae', 'ya', 'yae', 'eo', 'e', 'yeo', 'ye', 'o', 'wa', 'wae', 'oe', 'yo', 'u', 'wo', 'we', 'wi', 'yu', 'eu', 'ui', 'i']
_JONG = ['', 'g', 'kk', 'gs', 'n', 'nj', 'nh', 'd', 'l', 'lg', 'lm', 'lb', 'ls', 'lt', 'lp', 'lh', 'm', 'b', 'bs', 's', 'ss', 'ng',
         'j', 'ch', 'k', 't', 'p', 'h']


def romanize(text):
    """한글 -> 로마자 (국어의 로마자 표기법의 전자법: 글자 단위 1:1, 받침 ㄱ=g ㄷ=d ㅂ=b ㄹ=l). 연습문제 -> yeonseubmunje"""
    import unicodedata
    out = []
    for ch in unicodedata.normalize('NFC', text):
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:
            o -= 0xAC00
            out.append(_CHO[o // 588] + _JUNG[(o % 588) // 28] + _JONG[o % 28])
        else:
            out.append(ch)
    return ''.join(out)


_ROMAN = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]


def roman(n):
    """자연수 -> 로마 숫자 (대문자). 0 은 'Nulla', 4000 이상은 자리마다 따로 옮긴다."""
    if n == 0: return 'Nulla'
    if n >= 4000: return ''.join(roman(int(d)) if d != '0' else 'Nulla' for d in str(n))
    out = ''
    for v, r in _ROMAN:
        while n >= v: out += r; n -= v
    return out


def env_name(name):
    """스타일 이름 -> 환경 이름. ndhmd4tex은 환경 이름을 글자(letter, catcode 11)로만 받으므로
    한글은 로마자로, 숫자는 로마 숫자(대문자)로 바꾸고, 공백·하이픈 등 글자가 아닌 것은 지운다.
    낱말 경계는 다음 낱말의 첫 글자를 대문자로 하여 표시한다:  01-문제 -> IMunje,  연습문제 -> yeonseubmunje"""
    segs = re.findall(r'[A-Za-z]+|\d+', romanize(name.strip()))
    out = []
    for i, sg in enumerate(segs):
        if sg.isdigit(): out.append(roman(int(sg)))
        else: out.append(sg if i == 0 else sg[0].upper() + sg[1:])
    return ''.join(out) or 'style'


def main():
    ap = argparse.ArgumentParser(description='hwpx -> (ndh)md  (version %s)' % __version__)
    ap.add_argument('-V', '--version', action='version', version='hwpx2ndhmd %s' % __version__)
    ap.add_argument('input'); ap.add_argument('-o', '--output')
    ap.add_argument('--headings', choices=['auto', 'style', 'none'], default='auto',
                    help='style: 개요 스타일만 / auto: 개요 스타일 + 번호 머리표 휴리스틱 / none')
    ap.add_argument('--heading-base', type=int, default=1, help='가장 높은 헤딩 수준 (기본 1)')
    ap.add_argument('--heading-threshold', type=int, default=5, help='자동 추정 점수 문턱 (최대 7)')
    ap.add_argument('--heading-maxlen', type=int, default=40)
    ap.add_argument('--style-map', help='JSON: {"스타일 이름": "환경이름" | "heading:2" | null}')
    ap.add_argument('--env-names', choices=['romanize', 'keep'], default='romanize',
                    help='romanize: 글자만 쓰도록 한글은 로마자로, 숫자는 로마 숫자로 (01-문제 -> IMunje) / keep: 이름 그대로')
    ap.add_argument('--image-width', default=r'0.75\linewidth', help='그림 width (기본 0.75\\linewidth)')
    ap.add_argument('--image-size', choices=['auto', 'fixed'], default='auto',
                    help='auto: 문서의 그림 크기를 본문 너비에 대한 비율로 옮김(상한 --image-max) / fixed: 모두 --image-width')
    ap.add_argument('--image-max', type=float, default=0.75, help='auto 일 때 폭 상한 (기본 0.75)')
    ap.add_argument('--image-dir', default='.', help='그림을 저장할 폴더 (출력 파일 기준 상대 경로, 기본 같은 폴더)')
    ap.add_argument('--image-prefix', default='', help='그림 파일 이름 앞에 붙일 글 (예: ch1-)')
    ap.add_argument('--no-pillow', action='store_true', help='Pillow 가 있어도 쓰지 않는다 (24비트 BMP 는 표준 라이브러리로 변환)')
    ap.add_argument('--no-crop', dest='crop', action='store_false', help='hwpx 의 그림 잘라내기 정보를 무시한다')
    ap.add_argument('--display', choices=['auto', 'none'], default='auto',
                    help='auto: 수식만 있는 줄을 구조로 추정해 디스플레이 수식으로 / none: 모두 인라인')
    ap.add_argument('--display-style', choices=['brackets', 'dollars'], default='brackets',
                    help='디스플레이 수식 표기: brackets=\\[ … \\] (기본) / dollars=$$ … $$')
    ap.add_argument('--display-threshold', type=int, default=5, help='디스플레이 수식 추정 점수 문턱 (최대 6)')
    ap.add_argument('--custompkg', metavar='PKGS', default='',
                    help='쉼표로 나눈 패키지 이름을 preamble+: 에 \\usepackage{…} 로 추가 (예: "esint,mystyle"). 수식이 없어도 front matter 를 만든다')
    ap.add_argument('--no-preamble', dest='preamble', action='store_false',
                    help='수식이 있어도 front matter(preamble+: amsmath,amssymb)를 넣지 않는다')
    ap.add_argument('--env-table', metavar='FILE', help='스타일 이름 -> 환경 이름 대응표와 \\newenvironment 목록을 쓸 파일 (기본: 출력파일.envs.tex, 환경이 있을 때만)')
    ap.add_argument('--env-in-preamble', action='store_true', help='\\newenvironment 목록을 front matter 의 preamble+: 에도 넣는다')
    ap.add_argument('--footnotes', choices=['ref', 'inline', 'drop'], default='ref',
                    help='ref: [^1] 과 [^1]: 정의 (문단 바로 뒤) / inline: ^[…] / drop: 버린다')
    ap.add_argument('--endnotes', choices=['ref', 'collect', 'drop'], default='ref',
                    help='ref: 본문에 [^en1]{end}, 정의는 문단 뒤에 내고 front matter 에 \\endnote 설정을 넣는다 (ndhmd4tex) / '
                         'collect: 번호 붙인 미주를 문서 끝 별면에 모아 낸다 (본문에 표지 없음) / drop: 버린다')
    ap.add_argument('--endnote-break', default='\\newpage', help='collect 일 때 미주 앞에 넣을 줄 (기본 \\newpage)')
    ap.add_argument('--keep-linebreaks', action='store_true',
                    help='한글의 강제 줄바꿈(Shift+Enter)을 마크다운 줄바꿈(줄 끝 두 칸)으로 남긴다 (기본: 공백으로 이어 붙임)')
    ap.add_argument('--no-para-numbers', dest='para_numbers', action='store_false',
                    help='한글의 자동 문단 번호({1}. 꼴)를 넣지 않는다')
    ap.add_argument('--keep-cell-text', action='store_true', default=True)
    ap.add_argument('--no-cell-text', dest='keep_cell_text', action='store_false')
    ap.add_argument('--show-empty-shapes', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    md, ctx = convert(a.input, a)
    if a.output: open(a.output, 'w', encoding='utf8').write(md)
    else: sys.stdout.write(md)
    if ctx.envs and (a.env_table or a.output):
        ep = a.env_table or os.path.splitext(a.output)[0] + '.envs.tex'
        open(ep, 'w', encoding='utf8').write(env_table_tex(ctx, a.input))
        print('환경 대응표:', ep, file=sys.stderr)
    if a.report or a.output:
        print('통계:', dict(ctx.stats), file=sys.stderr)
        print('문단 스타일:', dict(ctx.used_styles), file=sys.stderr)
        for i, sc, m in ctx.display_list: print('  디스플레이 수식 #%d (점수 %d): %s' % (i, sc, m), file=sys.stderr)
        for ref, ext, a0, b0 in ctx.image_info: print('  그림 %s: %s %d바이트 -> %d바이트' % (ref, ext, a0, b0), file=sys.stderr)
        for ref, cm, wd in ctx.image_sizes: print('  크기 %s: %s -> %s' % (ref, '%.1fcm' % cm if cm else '기록 없음', wd), file=sys.stderr)
        for w in ctx.warn: print('경고:', w, file=sys.stderr)
        for src, m in hwpeq.WARN: print('경고: 수식 괄호 짝 보정 (%s): %s' % (src.strip()[:50], m), file=sys.stderr)
        if ctx.envs: print('환경 이름:', ctx.envs, file=sys.stderr)
        for i, sc, k, t in ctx.headings: print('  추정 헤딩 #%d (점수 %d, %s): %s' % (i, sc, k, t), file=sys.stderr)
        if getattr(ctx, 'needs_other', None) and 'esint' not in [x.strip() for x in a.custompkg.replace(';', ',').split(',')]:
            print('주의: %s 는 esint 패키지가 필요합니다 (amsmath, amssymb 에는 없음)' % ', '.join(ctx.needs_other), file=sys.stderr)
        if hwpeq.UNKNOWN: print('미해석 수식 명령:', sorted(hwpeq.UNKNOWN), file=sys.stderr)


if __name__ == '__main__':
    main()
