"""rhwp(MIT)의 symbols.rs 표를 읽어 한컴 수식 명령 -> LaTeX 표(hwpeq_tables.py)를 만든다. 생성 시에만 pylatexenc 필요."""
import re, sys, os, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
from pylatexenc.latexencode import UnicodeToLatexEncoder
SRC=sys.argv[1] if len(sys.argv) > 1 else 'rhwp/src/renderer/equation/symbols.rs'   # 사용법: python gen/gen_tables.py <rhwp>/src/renderer/equation/symbols.rs
src=open(SRC,encoding='utf8').read()
enc=UnicodeToLatexEncoder(non_ascii_only=True,replacement_latex_protection='none',unknown_char_policy='keep')
tabs={}
for m in re.finditer(r'static (\w+): LazyLock<HashMap<&\'static str, &\'static str>>.*?HashMap::from\(\[(.*?)\]\)\s*\}\);',src,re.S):
    name,body=m.groups()
    ents={}
    for a,b in re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)',body): ents[a]=b
    tabs[name]=ents
OVR={'×':r'\times','÷':r'\div','←':r'\leftarrow','→':r'\rightarrow','↑':r'\uparrow','↓':r'\downarrow','ı':r'\imath','◇':r'\diamond','★':r'\star','⌬':r'\mathrm{?}','−':'-','∙':r'\cdot','⋅':r'\cdot','′':"'",'″':"''",'∼':r'\sim','∝':r'\propto','∴':r'\therefore','∵':r'\because',
     '≤':r'\le','≥':r'\ge','≠':r'\ne','⋯':r'\cdots','…':r'\ldots','∞':r'\infty','∂':r'\partial','∇':r'\nabla'}
def tolatex(u):
    if u in OVR: return OVR[u]
    if all(ord(c)<128 for c in u): return u
    r=enc.unicode_to_latex(u).strip()
    return r
EXTRA={'MHO':r'\mho','CENTIGRADE':r'{}^\circ\mathrm{C}','DEG':r'{}^\circ','HUND':r'\text{\textperthousand}','THOU':r'\text{\textpertenthousand}','LNOT':r'\neg','lnot':r'\neg','neg':r'\neg','DAGGER':r'\dagger','dagger':r'\dagger','DDAGGER':r'\ddagger','ddagger':r'\ddagger','STAR':r'\star','JMATH':r'\jmath','BENZENE':None,'ODINT':r'\oiint','OTINT':r'\oiiint','LLL':r'\lll','<<<':r'\lll','GGG':r'\ggg','>>>':r'\ggg',
 'RTANGLE':r'\measuredangle','FAHRENHEIT':r'{}^\circ\mathrm{F}','LAPLACE':r'\mathcal{L}','IMAG':r'\Im','image':r'\Im','REIMAGE':r'\Re','TRIANGLE':r'\triangle','BASE':r'\triangle','TRIANGLED':r'\triangledown','DSUM':r'\boxplus'}
BIGNAME={'BIGCUP':r'\bigcup','BIGCAP':r'\bigcap','BIGSQCUP':r'\bigsqcup','BIGSQCAP':r'\bigsqcap','BIGUPLUS':r'\biguplus','BIGWEDGE':r'\bigwedge','BIGVEE':r'\bigvee','BIGODOT':r'\bigodot','BIGOPLUS':r'\bigoplus','BIGOTIMES':r'\bigotimes'}
def unwrap(l):
    m=re.fullmatch(r'\\ensuremath\{(.*)\}',l)
    return m.group(1) if m else l
out={};bad={}
for t,ents in tabs.items():
    out[t]={};
    for k,u in ents.items():
        l=unwrap(tolatex(u))
        if k in EXTRA and EXTRA[k]: l=EXTRA[k]
        if t=='BIG_OPERATORS' and k in BIGNAME: l=BIGNAME[k]
        if any(ord(c)>127 for c in l): bad.setdefault(t,{})[k]=(u,l)
        out[t][k]=l
print({t:len(v) for t,v in out.items()})
print('unconverted:',{t:len(v) for t,v in bad.items()})
for t,v in bad.items(): print(t,list(v.items())[:25])
hdr='''# -*- coding: utf-8 -*-
# 자동 생성: gen_tables.py  (직접 고치지 말 것)
# 원본: rhwp (https://github.com/edwardkim/rhwp) src/renderer/equation/symbols.rs
# Copyright (c) 2025-2026 Edward Kim, MIT License. 명령 이름 표를 가져와 LaTeX 명령으로 바꾼 것이다.
'''
open(os.path.join(ROOT,'hwpeq_tables.py'),'w',encoding='utf8').write(hdr+'TABLES = '+json.dumps(out,ensure_ascii=False,indent=1)+'\nUNMAPPED = '+json.dumps({t:list(v) for t,v in bad.items()},ensure_ascii=False)+'\n')

