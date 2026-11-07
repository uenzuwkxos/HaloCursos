#!/usr/bin/env python3
"""Halo Cursors generator: 17 Windows cursors x 2 themes (Light, Dark).

Usage: python3 gen_halo3.py OUTPUT_DIR
Needs: Pillow, numpy and rsvg-convert (librsvg).
"""
import io
import math
import os
import shutil
import struct
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
SIZES = [32, 48, 64, 96, 128]    # sizes stored in each static cursor
ANI_SIZES = [32, 48, 64, 96]     # animated cursors stay lighter: Windows ignores heavy .ani files
HALF = 30.0                      # the canvas spans -30..+30 units; the halo radius is 20
NFRAMES = 12                     # frames per animated cursor
FONT = '/usr/share/fonts/opentype/inter/Inter-Medium.otf'


# ------------------------------------------------------------ geometry
def circ(r):
    return f"M{r} 0A{r} {r} 0 1 1 {-r} 0A{r} {r} 0 1 1 {r} 0Z"


def gap_arc(r):
    """Ring with a gap centered at the bottom (mirror-symmetric, spins when rotated)."""
    x = r * math.cos(math.radians(125))
    y = r * math.sin(math.radians(125))
    return f"M{x:.3f} {y:.3f}A{r} {r} 0 1 1 {-x:.3f} {y:.3f}"


P_I = "M0 -8h.01M0 -2.2V8"
P_IBEAM = "M0 -10V10M-4.5 -10H4.5M-4.5 10H4.5"
P_CROSS = "M0 -13V-5M0 5V13M-13 0H-5M5 0H13"
P_NS = "M-3.2 -9.2L0 -12.6L3.2 -9.2M-3.2 9.2L0 12.6L3.2 9.2"
P_MOVE = ("M-3.2 -9.2L0 -12.6L3.2 -9.2M-3.2 9.2L0 12.6L3.2 9.2"
          "M-9.2 -3.2L-12.6 0L-9.2 3.2M9.2 -3.2L12.6 0L9.2 3.2")
P_BAR = "M-5 0H5"
P_PIN = ("M0 0C-6 -7 -7.5 -9 -7.5 -12A7.5 7.5 0 0 1 7.5 -12C7.5 -9 6 -7 0 0Z"
         "M-2.6 -12a2.6 2.6 0 1 0 5.2 0a2.6 2.6 0 1 0 -5.2 0Z")
P_PEN = "M0 6L-3 0V-9.5Q-3 -11.5 -1.2 -11.5H1.2Q3 -11.5 3 -9.5V0Z"
P_PERSON = ("M-3.6 -4.6a3.6 3.6 0 1 0 7.2 0a3.6 3.6 0 1 0 -7.2 0Z"
            "M-7.2 8.4C-7.2 3 -4 0.6 0 0.6C4 0.6 7.2 3 7.2 8.4Q7.2 9.4 6.2 9.4H-6.2Q-7.2 9.4 -7.2 8.4Z")


# Drawing primitives. Each cursor is a list of them, drawn on top of the halo.
def core(r=4.8, sw=3.4, acc=False):          # center dot; sw is the contrasting ring width
    return dict(t='core', r=r, sw=sw, acc=acc)


def glyph(d, w=2.6, tf='', ow=None):          # main stroke with a contrasting outline underneath
    return dict(t='glyph', d=d, w=w, tf=tf, ow=ow or (w + 4.4))


def acc(d, w, tf=''):                         # accent stroke (spinner arcs, link ring)
    return dict(t='acc', d=d, w=w, tf=tf)


def bad(d, w):                                # "unavailable" red stroke
    return dict(t='bad', d=d, w=w, tf='')


def trk(d, w):                                # faint track behind a spinner
    return dict(t='trk', d=d, w=w, tf='')


def shape(d, tf=''):                          # filled silhouette (pin, person, pen)
    return dict(t='shape', d=d, tf=tf)


def blk(d, w, tf=''):                         # detail line drawn over a silhouette
    return dict(t='blk', d=d, w=w, tf=tf)


def dot(x, y, r, op, ink=False):              # small dot (accent color, or pointer ink when ink=True)
    return dict(t='dot', x=x, y=y, r=r, op=op, ink=ink)


def rot(deg):
    return f'rotate({deg})'


# Busy spinner timing (measured from the reference video: 60 frames = one 2 s cycle).
# Angles in degrees, clockwise from 12 o'clock, outer edge of the round caps.
_TAIL = [170,181,192,201,210,217,223,230,235,239,244,247,251,254,258,261,264,267,271,274,278,282,286,292,297,304,311,320,329,339,351,4,17,32,48,64,81,100,119,138,157,178,198,218,239,261,281,302,323,343,4,24,43,61,80,98,114,130,144,157]
_HEAD = [189,201,214,227,240,255,268,283,298,312,328,343,358,14,29,45,60,76,91,107,122,138,153,167,181,196,209,223,236,249,261,273,284,295,306,316,325,335,344,353,2,11,20,28,37,45,53,62,71,79,88,96,106,115,125,135,145,155,166,177]


def _unwrap(v):
    out = [float(v[0])]
    for x in v[1:] + v[:1]:                    # the extra last point closes the loop
        out.append(out[-1] + (x - out[-1]) % 360)
    return out


_TAIL_U, _HEAD_U = _unwrap(_TAIL), _unwrap(_HEAD)


def _at(tab, ph):
    x = ph * 60
    i = int(x) % 60
    return tab[i] + (tab[i + 1] - tab[i]) * (x - int(x))


def spinner(ph, r=11.5, w=3.2):
    """Busy ring: an arc that grows from a dot to ~270 deg and shrinks back while it turns; ph in [0, 1)."""
    cap = math.degrees(w / 2 / r)
    t0 = _at(_TAIL_U, ph) + cap
    t1 = max(_at(_HEAD_U, ph) - cap, t0 + 1.0)
    return dict(t='spin', r=r, w=w, t0=t0, t1=t1)


def comet(a, radius=11.0):
    """Working in background: three round dots chasing each other around the core, each smaller and fainter
    than the one in front (clearly bigger and bolder than the Busy ring, so the two are easy to tell apart)."""
    out = []
    for k, (r, op) in reversed(list(enumerate([(3.1, 1.0), (2.5, .66), (1.9, .38)]))):
        t = math.radians(a - 36 * k - 90)      # starts at 12 o'clock, moves clockwise
        out.append(dot(radius * math.cos(t), radius * math.sin(t), r, op))
    return out


# hot: vertical offset of the hotspot from the center (units). nosym: not mirror-symmetric.
# mirror: exact horizontal mirror of the previous cursor. rate: animation speed in 1/60 s.
CURS = [
    dict(key='pointer', file='01-pointer', name='Normal',
         prims=lambda a: [core()]),
    dict(key='help', file='02-help', name='Help',
         prims=lambda a: [glyph(P_I, 3.0, ow=7.4)]),
    dict(key='working', file='03-working', name='Working in background', anim=True, rate=6,
         prims=lambda a: comet(a) + [core(3.0, 2.6)]),
    dict(key='busy', file='04-busy', name='Busy', anim=True, rate=5, nframes=24, ani_sizes=[32, 48, 64],
         prims=lambda a: [spinner(a / 360), core(3.2, 2.6)]),
    dict(key='precision', file='05-precision', name='Precision',
         prims=lambda a: [glyph(P_CROSS), core(2.6, 2.4)]),
    dict(key='text', file='06-text', name='Text',
         prims=lambda a: [glyph(P_IBEAM)]),
    dict(key='handwriting', file='07-handwriting', name='Handwriting', hot=6.0,
         prims=lambda a: [shape(P_PEN), blk("M-3 -6.5H3", 1.4)]),
    dict(key='unavailable', file='08-unavailable', name='Unavailable', bad=True,
         prims=lambda a: [bad(circ(9.5), 2.6), bad(P_BAR, 2.8)]),
    dict(key='vertical', file='09-vertical', name='Vertical resize',
         prims=lambda a: [glyph(P_NS, ow=5.6), core(3.2, 2.6)]),
    dict(key='horizontal', file='10-horizontal', name='Horizontal resize',
         prims=lambda a: [glyph(P_NS, tf=rot(90), ow=5.6), core(3.2, 2.6)]),
    dict(key='diagonal1', file='11-diagonal1', name='Diagonal resize 1', nosym=True,
         prims=lambda a: [glyph(P_NS, tf=rot(-45), ow=5.6), core(3.2, 2.6)]),
    dict(key='diagonal2', file='12-diagonal2', name='Diagonal resize 2', nosym=True, mirror=True,
         prims=lambda a: [glyph(P_NS, tf=rot(-45), ow=5.6), core(3.2, 2.6)]),
    dict(key='move', file='13-move', name='Move',
         prims=lambda a: [glyph(P_MOVE, ow=5.6), core(3.2, 2.6)]),
    dict(key='alternate', file='14-alternate', name='Alternate',
         prims=lambda a: [glyph(circ(5.5))]),
    dict(key='link', file='15-link', name='Link',
         prims=lambda a: [acc(circ(10), 1.8), core(4.8, 3.4, True)]),
    dict(key='pin', file='16-pin', name='Location', hot=6.0,
         prims=lambda a: [shape(P_PIN, 'translate(0 6) scale(.8)')]),
    dict(key='person', file='17-person', name='Person',
         prims=lambda a: [shape(P_PERSON, 'translate(0 -0.6)')]),
]

# ------------------------------------------------------------ themes
# Themes are named by the pointer itself: Light = predominantly light, Dark = predominantly dark.
# Double rim: dark line outside, light line inside, so the halo shows on any background.
RIMS = [(20.3, '#17181c', .60, 1.5), (18.9, '#ffffff', .85, 1.3)]


def aura(color, edge=.30):
    return [(0, color, .04), (.65, color, .13), (1, color, edge)]


THEMES = {
    'Light': dict(ink='#ffffff', core='#ffffff', ring='#17181c', gout='#17181c', gout_op=1, rims=RIMS,
                  acc='#FFFF00', bad='#FF6B6B', trk='#ffffff', trk_op=.22,
                  aura=aura('#ffffff'), aura_b=[(0, '#FF6B6B', .06), (1, '#FF6B6B', .36)]),
    'Dark': dict(ink='#17181c', core='#17181c', ring='#ffffff', gout='#ffffff', gout_op=1, rims=RIMS,
                 acc='#0000FF', bad='#E5484D', trk='#17181c', trk_op=.16,
                 aura=aura('#17181c'), aura_b=[(0, '#E5484D', .05), (1, '#E5484D', .34)]),
}
ORDER = ['Light', 'Dark']                  # main pair: yellow accent on Light, blue accent on Dark

# Extra accent colors: name -> (tone used on Light, tone used on Dark). Light uses brighter tones, Dark deeper ones.
COLORS = {
    'Red': ('#FF4D4D', '#E00000'), 'Cyan': ('#00E5FF', '#0099B8'), 'Green': ('#3DFF7A', '#0B9A3A'),
    'Magenta': ('#FF4DE0', '#D100B3'), 'Blue': ('#4D9BFF', '#0057FF'), 'Yellow': ('#FFD60A', '#E5A800'),
    'Violet': ('#B28DFF', '#6A1BFF'), 'Orange': ('#FFA033', '#F25C00'),
}
ACC_KEYS = ('working', 'busy', 'link')       # the only cursors that use the accent color
VARIANTS = []                                # e.g. 'Red-Light'
for _cn, (_lt, _dk) in COLORS.items():
    for _base, _tone in (('Light', _lt), ('Dark', _dk)):
        THEMES[f'{_cn}-{_base}'] = dict(THEMES[_base], acc=_tone)
        VARIANTS.append(f'{_cn}-{_base}')
ALL_THEMES = ORDER + VARIANTS


def base_of(tname):
    return tname.split('-')[-1]


def pretty(tname):
    return tname.replace('-', ' ')



# ------------------------------------------------------------ SVG
def svg_wrap(body, defs=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-HALF} {-HALF} {2 * HALF} {2 * HALF}">'
            f'{defs}{body}</svg>')


def stops(lst):
    return ''.join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{op}"/>' for o, c, op in lst)


def tfa(tf):
    return f' transform="{tf}"' if tf else ''


def svg_color(c, th, a=0):
    """SVG of cursor c in theme th; a is the animation angle in degrees."""
    defs = (f'<defs><radialGradient id="au">{stops(th["aura"])}</radialGradient>'
            f'<radialGradient id="ab">{stops(th["aura_b"])}</radialGradient></defs>')
    b = f'<circle r="20" fill="url(#{"ab" if c.get("bad") else "au"})"/>'
    for r_, c_, op_, w_ in th['rims']:
        b += f'<circle r="{r_}" fill="none" stroke="{c_}" stroke-opacity="{op_}" stroke-width="{w_}"/>'
    rnd = 'stroke-linecap="round" stroke-linejoin="round"'
    go, goo = th['gout'], th['gout_op']
    ink, core_c, acc_c = th['ink'], th['core'], th['acc']
    for p in c['prims'](a):
        t = p['t']
        if t == 'core':
            b += (f'<circle r="{p["r"]}" fill="{acc_c if p["acc"] else core_c}" '
                  f'stroke="{th["ring"]}" stroke-width="{p["sw"]}"/>')
        elif t == 'glyph':
            b += (f'<path d="{p["d"]}"{tfa(p["tf"])} fill="none" stroke="{go}" stroke-opacity="{goo}" '
                  f'stroke-width="{p["ow"]}" {rnd}/>')
            b += f'<path d="{p["d"]}"{tfa(p["tf"])} fill="none" stroke="{ink}" stroke-width="{p["w"]}" {rnd}/>'
        elif t in ('acc', 'bad'):
            col = acc_c if t == 'acc' else th['bad']
            b += (f'<path d="{p["d"]}"{tfa(p["tf"])} fill="none" stroke="{go}" stroke-opacity="{goo}" '
                  f'stroke-width="{p["w"] + 2.4}" {rnd}/>')
            b += f'<path d="{p["d"]}"{tfa(p["tf"])} fill="none" stroke="{col}" stroke-width="{p["w"]}" {rnd}/>'
        elif t == 'spin':
            def pt(deg):
                q = math.radians(deg)
                return p['r'] * math.sin(q), -p['r'] * math.cos(q)

            def arc(a0, a1):
                (x0, y0), (x1, y1) = pt(a0), pt(a1)
                return f'M{x0:.3f} {y0:.3f}A{p["r"]} {p["r"]} 0 {1 if a1 - a0 > 180 else 0} 1 {x1:.3f} {y1:.3f}'
            t0, t1, w = p['t0'], p['t1'], p['w']
            ln = t1 - t0
            fade = max(min(80.0, ln * .6), 1.0)        # the tail end is lighter than the head
            op = lambda s_: .4 + .6 * min(1.0, s_ / fade)
            b += (f'<path d="{arc(t0, t1)}" fill="none" stroke="{go}" stroke-opacity="{goo}" '
                  f'stroke-width="{w + 2.4}" {rnd}/>')
            nseg = max(1, math.ceil(ln / 4))
            for k in range(nseg):
                a0, a1 = t0 + ln * k / nseg, t0 + ln * (k + 1) / nseg
                b += (f'<path d="{arc(a0, min(a1 + .6, t1))}" fill="none" stroke="{acc_c}" '
                      f'stroke-opacity="{op((a0 + a1) / 2 - t0):.3f}" stroke-width="{w}"/>')
            for ang, o_ in ((t0, op(0)), (t1, 1.0)):
                x, y = pt(ang)
                b += f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{w / 2}" fill="{acc_c}" fill-opacity="{o_:.3f}"/>'
        elif t == 'trk':
            b += (f'<path d="{p["d"]}" fill="none" stroke="{th["trk"]}" stroke-opacity="{th["trk_op"]}" '
                  f'stroke-width="{p["w"]}" {rnd}/>')
        elif t == 'shape':
            b += (f'<path d="{p["d"]}"{tfa(p["tf"])} fill="{ink}" fill-rule="evenodd" stroke="{go}" '
                  f'stroke-opacity="{goo}" stroke-width="2.8" stroke-linejoin="round"/>')
        elif t == 'blk':
            b += (f'<path d="{p["d"]}"{tfa(p["tf"])} fill="none" stroke="{go}" '
                  f'stroke-opacity="{max(goo, .6)}" stroke-width="{p["w"]}" {rnd}/>')
        elif t == 'dot':
            b += (f'<circle cx="{p["x"]:.3f}" cy="{p["y"]:.3f}" r="{p["r"] + 1.3}" fill="{go}" '
                  f'fill-opacity="{goo * p["op"]}"/>')
            b += f'<circle cx="{p["x"]:.3f}" cy="{p["y"]:.3f}" r="{p["r"]}" fill="{ink if p["ink"] else acc_c}" fill-opacity="{p["op"]}"/>'
    return svg_wrap(b, defs)


def render(svg, px):
    p = subprocess.run(['rsvg-convert', '-w', str(px), '-h', str(px), '-f', 'png'],
                       input=svg.encode(), capture_output=True, check=True)
    return Image.open(io.BytesIO(p.stdout)).convert('RGBA')


def sym_img(img):
    """Average the image with its mirror image so it is exactly left/right symmetric."""
    a = np.asarray(img).astype(np.float32)
    al = a[:, :, 3:4]
    pm = a[:, :, :3] * al / 255.0
    pm2 = (pm + pm[:, ::-1]) / 2
    al2 = (al + al[:, ::-1]) / 2
    rgb = np.where(al2 > 0, pm2 * 255.0 / np.maximum(al2, 1e-6), 0)
    return Image.fromarray(np.clip(np.concatenate([rgb, al2], axis=2), 0, 255).round().astype(np.uint8), 'RGBA')


def cursor_image(c, th, n, angle=0):
    im = render(svg_color(c, th, angle), n)
    if not c.get('nosym') and not c.get('anim'):
        im = sym_img(im)
    if c.get('mirror'):
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


# ------------------------------------------------------------ binary formats
def pad4(b):
    return b + b'\x00' * ((4 - len(b) % 4) % 4)


def dib32(img, n):
    """32-bit BGRA bitmap with straight alpha plus an AND mask, as stored inside .cur files."""
    a = np.asarray(img)
    bgra = a[:, :, [2, 1, 0, 3]].copy()
    bgra[a[:, :, 3] == 0] = 0
    pix = bgra[::-1].tobytes()
    m = (a[:, :, 3] == 0)[::-1]
    msk = b''.join(pad4(np.packbits(row).tobytes()) for row in m)
    data = pix + msk
    hdr = struct.pack('<IiiHHIIiiII', 40, n, 2 * n, 1, 32, 0, len(data), 0, 0, 0, 0)
    return hdr + data


def make_cur(entries):
    cnt = len(entries)
    hdr = struct.pack('<HHH', 0, 2, cnt)
    off = 6 + 16 * cnt
    d = b''
    blob = b''
    for n, hx, hy, data in entries:
        d += struct.pack('<BBBBHHII', n, n, 0, 0, hx, hy, len(data), off + len(blob))
        blob += data
    return hdr + d + blob


def chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + (b'\x00' if len(data) % 2 else b'')


def make_ani(frames, rate, title):
    n = len(frames)
    anih = struct.pack('<9I', 36, n, n, 0, 0, 0, 0, rate, 1)
    info = b'INFO' + chunk(b'INAM', title.encode() + b'\0') + chunk(b'IART', b'Halo\0')
    fram = b'fram' + b''.join(chunk(b'icon', f) for f in frames)
    body = b'ACON' + chunk(b'LIST', info) + chunk(b'anih', anih) + chunk(b'LIST', fram)
    return b'RIFF' + struct.pack('<I', len(body)) + body


def hotspot(c, n):
    hy = c.get('hot', 0.0)
    return n // 2, min(n - 1, int(round(n * (HALF + hy) / (2 * HALF))))


def build_cur(c, tname, frame=0, sizes=None):
    th = THEMES[tname]
    entries = []
    nf = c.get('nframes', NFRAMES)
    for n in (sizes or SIZES):
        hx, hy = hotspot(c, n)
        entries.append((n, hx, hy, dib32(cursor_image(c, th, n, frame * 360 / nf), n)))
    return make_cur(entries)


# ------------------------------------------------------------ installation files
# (registry value, INF string, file); the order is the one Windows uses for a cursor scheme
REG = [('Arrow', 'pointer', '01-pointer.cur'), ('Help', 'help', '02-help.cur'),
       ('AppStarting', 'working', '03-working.ani'), ('Wait', 'busy', '04-busy.ani'),
       ('Crosshair', 'precision', '05-precision.cur'), ('IBeam', 'text', '06-text.cur'),
       ('NWPen', 'handwriting', '07-handwriting.cur'), ('No', 'unavailable', '08-unavailable.cur'),
       ('SizeNS', 'vertical', '09-vertical.cur'), ('SizeWE', 'horizontal', '10-horizontal.cur'),
       ('SizeNWSE', 'diagonal1', '11-diagonal1.cur'), ('SizeNESW', 'diagonal2', '12-diagonal2.cur'),
       ('SizeAll', 'move', '13-move.cur'), ('UpArrow', 'alternate', '14-alternate.cur'),
       ('Hand', 'link', '15-link.cur'), ('Pin', 'pin', '16-pin.cur'), ('Person', 'person', '17-person.cur')]


def inf_text(theme):
    path = lambda k: f'%10%\\%CUR_DIR%\\%{k}%'
    scheme = ','.join(path(k) for _, k, _ in REG)
    active = '\n'.join(f'HKCU,"Control Panel\\Cursors",{r},0x00020000,"{path(k)}"' for r, k, _ in REG)
    files = '\n'.join(f'"{f}"' for _, _, f in REG)
    strs = '\n'.join(f'{k} = "{f}"' for _, k, f in REG)
    theme = pretty(theme)
    return f'''; Halo Cursors - {theme}
[Version]
signature="$CHICAGO$"

[DefaultInstall]
CopyFiles = Scheme.Cur
AddReg    = Scheme.Reg, Scheme.Active

[DestinationDirs]
Scheme.Cur = 10,"%CUR_DIR%"

; adds the scheme to the list in Mouse > Pointers
[Scheme.Reg]
HKCU,"Control Panel\\Cursors\\Schemes","%SCHEME_NAME%",,"{scheme}"

; makes it the active scheme and opens the Mouse window so you can confirm
[Scheme.Active]
HKCU,"Control Panel\\Cursors",,0x00020000,"%SCHEME_NAME%"
{active}
HKLM,"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Runonce\\Setup\\","",,"rundll32.exe shell32.dll,Control_RunDLL main.cpl @0,1"

[Scheme.Cur]
{files}

[Strings]
CUR_DIR = "Cursors\\Halo {theme}"
SCHEME_NAME = "Halo {theme}"
{strs}
'''


# Engine behind Install.bat and Restore.bat (per user, no administrator needed)
PS1 = r'''<#
  Halo Cursors installer engine. Run it through Install.bat or Restore.bat.
  Options: -Theme Light|Dark   -Accent Red|Cyan|...   -Size 1..15 (pointer size)   -Restore
#>
param(
    [ValidateSet('Light', 'Dark')][string]$Theme,
    [ValidateSet('Default', %ACCENTS%)][string]$Accent = 'Default',
    [ValidateRange(1, 15)][int]$Size,
    [switch]$Restore
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$map = [ordered]@{
    Arrow       = '01-pointer.cur'
    Help        = '02-help.cur'
    AppStarting = '03-working.ani'
    Wait        = '04-busy.ani'
    Crosshair   = '05-precision.cur'
    IBeam       = '06-text.cur'
    NWPen       = '07-handwriting.cur'
    No          = '08-unavailable.cur'
    SizeNS      = '09-vertical.cur'
    SizeWE      = '10-horizontal.cur'
    SizeNWSE    = '11-diagonal1.cur'
    SizeNESW    = '12-diagonal2.cur'
    SizeAll     = '13-move.cur'
    UpArrow     = '14-alternate.cur'
    Hand        = '15-link.cur'
    Pin         = '16-pin.cur'
    Person      = '17-person.cur'
}

Add-Type -Namespace Win32 -Name Native -MemberDefinition '[DllImport("user32.dll", SetLastError=true)] public static extern bool SystemParametersInfo(uint uiAction, uint uiParam, IntPtr pvParam, uint fWinIni);'
function Update-Cursors { [void][Win32.Native]::SystemParametersInfo(0x0057, 0, [IntPtr]::Zero, 0x03) }

$regPath = 'HKCU:\Control Panel\Cursors'

function Set-PointerSize([int]$n) {
    $base = 16 * ($n + 1)
    Set-ItemProperty -Path $regPath -Name 'CursorBaseSize' -Value $base -Type DWord
    try { [void][Win32.Native]::SystemParametersInfo(0x2029, 0, [IntPtr]$base, 0x03) } catch { }
    Update-Cursors
    Write-Host "Pointer size: $n ($base px base)."
    Write-Host 'If it does not change right away, use Settings > Accessibility > Mouse pointer and touch > Size.'
}

if ($Restore) {
    foreach ($k in $map.Keys) { Set-ItemProperty -Path $regPath -Name $k -Value '' }
    Set-ItemProperty -Path $regPath -Name '(default)' -Value 'Windows Default'
    Update-Cursors
    Write-Host 'Windows default cursors restored.'
    return
}

$wantSize = $PSBoundParameters.ContainsKey('Size')

if ($wantSize -and -not $Theme) {
    Set-PointerSize $Size
    return
}

if (-not $Theme) {
    $opts = @('Light', 'Dark')
    for ($i = 0; $i -lt $opts.Count; $i++) { Write-Host ("  {0}) {1}" -f ($i + 1), $opts[$i]) }
    $n = [int](Read-Host 'Choose a theme (1-2)')
    if ($n -lt 1 -or $n -gt 2) { throw 'Invalid option.' }
    $Theme = $opts[$n - 1]
    $accents = @('Default', %ACCENTS%)
    Write-Host ''
    for ($i = 0; $i -lt $accents.Count; $i++) { Write-Host ("  {0}) {1}" -f ($i + 1), $accents[$i]) }
    $a = [int](Read-Host 'Choose an accent color (1-%NACC%, Default = yellow on Light, blue on Dark)')
    if ($a -lt 1 -or $a -gt $accents.Count) { throw 'Invalid option.' }
    $Accent = $accents[$a - 1]
    $s = Read-Host 'Pointer size from 1 to 15 (press Enter to keep the current one)'
    if ($s -match '^\d+$' -and [int]$s -ge 1 -and [int]$s -le 15) { $Size = [int]$s; $wantSize = $true }
}

if ($Accent -eq 'Default') { $name = $Theme; $src = Join-Path $root $Theme }
else { $name = "$Accent-$Theme"; $src = Join-Path $root "Colors\$name" }
if (-not (Test-Path $src)) { throw "Theme folder not found: $src" }
$dest = Join-Path $env:LOCALAPPDATA "HaloCursors\$name"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -Path (Join-Path $src '*.cur'), (Join-Path $src '*.ani') -Destination $dest -Force

$schemeName = "Halo " + $name.Replace('-', ' ')
$paths = @()
foreach ($k in $map.Keys) {
    $full = Join-Path $dest $map[$k]
    Set-ItemProperty -Path $regPath -Name $k -Value $full
    $paths += $full
}
Set-ItemProperty -Path $regPath -Name '(default)' -Value $schemeName

$schemes = "$regPath\Schemes"
if (-not (Test-Path $schemes)) { New-Item -Path $schemes -Force | Out-Null }
New-ItemProperty -Path $schemes -Name $schemeName -Value ($paths -join ',') -PropertyType ExpandString -Force | Out-Null

Update-Cursors
Write-Host "Theme '$schemeName' applied."
if ($wantSize) { Set-PointerSize $Size }
'''

BAT_INSTALL = '''@echo off
rem Runs the installer without changing the system execution policy (this run only).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Cursors.ps1" %*
echo.
pause
'''

BAT_RESTORE = '''@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Cursors.ps1" -Restore
echo.
pause
'''

README = '''<h1 align="center">Halo Cursors</h1>

<p align="center">
  <img src="preview.png" alt="Halo Cursors preview" width="860">
</p>

Round, mirror-symmetric cursors for Windows and Linux, equally comfortable for left- and right-handed use.
17 cursors, two themes:

| Theme | Pointer | Accent (Working, Busy, Link) |
|-------|---------|------------------------------|
| **Light** | White, dark outline | Yellow |
| **Dark** | Dark, white outline | Blue |

Eight extra accent colors, each in Light and Dark: Red, Cyan, Green, Magenta, Blue, Yellow, Violet and Orange.

<p align="center">
  <img src="colors.png" alt="Accent colors" width="520">
</p>

## Windows

1. Open the `Windows` folder and double-click `Install.bat`.
2. Pick a theme, an accent color and, if you want, a pointer size.

Alternatively, open `Light` or `Dark` (or a folder inside `Colors`), right-click `Install.inf` and choose **Install**,
then click **OK** in the Mouse window that opens.

To go back, double-click `Restore.bat`.

### Pointer size

Every cursor file holds several sizes and Windows picks one automatically. To change it:

- **Windows 11:** Settings > Accessibility > Mouse pointer and touch > Size
- **Windows 10:** Settings > Ease of Access > Cursor & pointer > Change pointer size
- **Install.bat:** it also asks for a size from 1 to 15

Cursors stay sharp up to 128 px (size 7 at 100% display scale); Working in background up to 96 px (size 5) and Busy up to 64 px (size 3).

## Linux

Works on Plasma, GNOME, XFCE, Cinnamon and COSMIC (Xcursor themes).

```sh
cd Linux
./install.sh Light          # or Dark
./install.sh Dark Red       # with an accent color
```

It installs the theme for your user and applies it. If the cursor does not change, log out and back in;
on COSMIC you may need to pick Halo in Settings > Desktop > Appearance.
To install by hand, copy a `Halo-*` folder to `~/.local/share/icons` and select it in your desktop settings.

## Source

`tools/generate.py` regenerates everything (`python3 tools/generate.py OUTPUT_DIR`; needs Python 3, Pillow, NumPy and `rsvg-convert`).
'''


def write(path, data, mode='wb'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(data)


# ------------------------------------------------------------ preview image
def make_preview(path):
    """README banner: two panels side by side; each shows all 17 cursors of a theme on a contrasting background."""
    T, n, pad, label_h, gap, cols = 112, 96, 28, 56, 36, 6
    rows = (len(CURS) + cols - 1) // cols
    pw, ph = cols * T + 2 * pad, rows * T + 2 * pad + label_h
    img = Image.new('RGBA', (2 * pw + gap, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT, 30)
    except OSError:
        font = ImageFont.load_default()
    panels = [('Light', 'dark'), ('Dark', 'light')]
    for k, (name, kind) in enumerate(panels):
        px, py = k * (pw + gap), 0
        dark = kind == 'dark'
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=28, fill=(28, 29, 33, 255) if dark else (242, 243, 245, 255))
        d.text((px + pad, py + pad - 4), name, font=font, fill=(255, 255, 255, 255) if dark else (23, 24, 28, 255))
        for i, c in enumerate(CURS):
            cx = px + pad + (i % cols) * T + (T - n) // 2
            cy = py + pad + label_h + (i // cols) * T + (T - n) // 2
            img.alpha_composite(cursor_image(c, THEMES[name], n, 150 if c['key'] == 'busy' else 0), (cx, cy))
    img.save(path)


# ------------------------------------------------------------ Linux (Xcursor)
LINUX_SIZES = [24, 32, 48, 64, 96, 128]
LINUX_ANI_SIZES = [24, 32, 48, 64, 96]
# Xcursor name -> extra names (CSS cursor names, legacy X11 names and the hashed names old GTK/Qt/Firefox look up)
LINUX_NAMES = {
    'pointer': ['default', 'arrow', 'left_ptr', 'top_left_arrow', 'right_ptr', 'context-menu'],
    'help': ['help', 'question_arrow', 'whats_this', 'left_ptr_help', 'dnd-ask',
             'd9ce0ab605698f320427677b458ad60b', '5c6cd98b3f3ebcb1f9c7f1c204630408'],
    'working': ['progress', 'left_ptr_watch', 'half-busy',
                '08e8e1c95fe2fc01f976f1e063a24ccd', '3ecb610c1bf2410f44200f48c40d3599'],
    'busy': ['wait', 'watch'],
    'precision': ['crosshair', 'cross', 'tcross', 'cross_reverse', 'diamond_cross', 'cell', 'plus', 'color-picker', 'zoom-in', 'zoom-out'],
    'text': ['text', 'xterm', 'ibeam', 'vertical-text'],
    'handwriting': ['pencil', 'draft', 'draft_large', 'draft_small'],
    'unavailable': ['not-allowed', 'no-drop', 'crossed_circle', 'forbidden', 'circle', 'dnd-no-drop', 'dnd-none',
                    '03b6e0fcb3499374a867c041f52298f0'],
    'vertical': ['ns-resize', 'n-resize', 's-resize', 'row-resize', 'size_ver', 'sb_v_double_arrow',
                 'v_double_arrow', 'split_v', 'top_side', 'bottom_side', 'double_arrow',
                 '00008160000006810000408080010102'],
    'horizontal': ['ew-resize', 'e-resize', 'w-resize', 'col-resize', 'size_hor', 'sb_h_double_arrow',
                   'h_double_arrow', 'split_h', 'left_side', 'right_side', '14fef782d02440884392942c11205230'],
    'diagonal1': ['nwse-resize', 'nw-resize', 'se-resize', 'size_fdiag', 'top_left_corner', 'bottom_right_corner',
                  'c7088f0f3e6c8088236ef8e1e3e70000'],
    'diagonal2': ['nesw-resize', 'ne-resize', 'sw-resize', 'size_bdiag', 'top_right_corner', 'bottom_left_corner',
                  'fcf1c3c7cd4491d801f1e1c78f100000'],
    'move': ['move', 'all-scroll', 'fleur', 'size_all', 'dnd-move', '4498f0e0c1937ffe01fd06f973665830',
             '9081237383d90e509aa00f00170e968f'],
    'alternate': ['up_arrow', 'center_ptr', 'sb_up_arrow'],
    'link': ['pointer', 'hand1', 'hand2', 'pointing_hand', 'grab', 'grabbing', 'openhand', 'closedhand', 'alias',
             'dnd-link', 'copy', 'dnd-copy', 'e29285e634086352946a0e7090d73106', '9d800788f1b08800ae810202380a0822',
             '3085a0e285b5894151d0f0e5c3a0f800', '1081e37283d90000800003c07f3ef6bf'],
    'pin': ['pin'],
    'person': ['person'],
}


def make_xcursor(chunks):
    """Xcursor file. chunks: (nominal_size, hot_x, hot_y, delay_ms, RGBA image) in playback order."""
    toc, body = [], b''
    base = 16 + 12 * len(chunks)
    for size, hx, hy, delay, im in chunks:
        w, h = im.size
        a = np.asarray(im.convert('RGBA'), dtype=np.float64)
        al = a[..., 3:4] / 255.0
        px = np.concatenate([a[..., 3:4], a[..., :3] * al], axis=2)        # premultiplied ARGB
        data = np.clip(np.rint(px), 0, 255).astype(np.uint8)
        data = (data[..., 0].astype('<u4') << 24 | data[..., 1].astype('<u4') << 16
                | data[..., 2].astype('<u4') << 8 | data[..., 3].astype('<u4'))
        toc.append((0xfffd0002, size, base + len(body)))
        body += struct.pack('<9I', 36, 0xfffd0002, size, 1, w, h, hx, hy, delay) + data.astype('<u4').tobytes()
    head = b'Xcur' + struct.pack('<3I', 16, 0x10000, len(chunks))
    return head + b''.join(struct.pack('<3I', *t) for t in toc) + body


_CACHE = {}


def cached(kind, tname, c, fn):
    """Cursors that do not use the accent color are identical across the color variants of a theme: build once."""
    if c['key'] in ACC_KEYS:
        return fn()
    k = (kind, base_of(tname), c['key'])
    if k not in _CACHE:
        _CACHE[k] = fn()
    return _CACHE[k]


def build_xcursor(c, th):
    if c.get('anim'):
        nf = c.get('nframes', NFRAMES)
        delay = round(c['rate'] * 1000 / 60)
        chunks = []
        for f in range(nf):
            for n in LINUX_ANI_SIZES:
                hx, hy = hotspot(c, n)
                chunks.append((n, hx, hy, delay, cursor_image(c, th, n, f * 360 / nf)))
        return make_xcursor(chunks)
    chunks = []
    for n in LINUX_SIZES:
        hx, hy = hotspot(c, n)
        chunks.append((n, hx, hy, 50, cursor_image(c, th, n)))
    return make_xcursor(chunks)


LINUX_INSTALL = '''#!/bin/sh
# Installs Halo Cursors for the current user and applies the theme when the desktop is recognized.
set -e
here=$(cd "$(dirname "$0")" && pwd)
dest="${XDG_DATA_HOME:-$HOME/.local/share}/icons"

case "$1" in
    Light|light) base=Light ;;
    Dark|dark) base=Dark ;;
    *)
        echo "Usage: ./install.sh Light|Dark [Color]"
        echo "Colors: %COLORS%"
        exit 1 ;;
esac

if [ -n "$2" ]; then
    color=$(printf '%s' "$2" | awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}')
    theme="Halo-$color-$base"
    src="$here/Colors/$theme"
else
    theme="Halo-$base"
    src="$here/$theme"
fi
[ -d "$src" ] || { echo "Theme not found: $theme"; exit 1; }

mkdir -p "$dest"
rm -rf "$dest/$theme"
cp -a "$src" "$dest/$theme"
mkdir -p "$HOME/.icons/default"
printf '[Icon Theme]\\nInherits=%s\\n' "$theme" > "$HOME/.icons/default/index.theme"

have() { command -v "$1" >/dev/null 2>&1; }
desktop=$(printf '%s' "${XDG_CURRENT_DESKTOP:-}" | tr 'A-Z' 'a-z')

case "$desktop" in
    *kde*)
        if have plasma-apply-cursortheme; then plasma-apply-cursortheme "$theme"; fi ;;
    *cinnamon*)
        if have gsettings; then gsettings set org.cinnamon.desktop.interface cursor-theme "$theme"; fi ;;
    *xfce*)
        if have xfconf-query; then xfconf-query -c xsettings -p /Gtk/CursorThemeName -n -t string -s "$theme"; fi ;;
    *)
        if have gsettings; then gsettings set org.gnome.desktop.interface cursor-theme "$theme"; fi ;;
esac

echo "Installed $theme in $dest."
echo "If the cursor does not change right away, log out and back in."
case "$desktop" in *cosmic*) echo "COSMIC: if it still shows the old cursor, pick Halo in Settings > Desktop > Appearance." ;; esac
'''


def make_linux(out):
    for tname in ALL_THEMES:
        th = THEMES[tname]
        name = f'Halo-{tname}'
        tdir = os.path.join(out, 'Linux', name if tname in ORDER else os.path.join('Colors', name))
        os.makedirs(os.path.join(tdir, 'cursors'))
        write(os.path.join(tdir, 'index.theme'), f'[Icon Theme]\nName={name}\nComment=Round, mirror-symmetric cursors\n', 'w')
        for c in CURS:
            names = LINUX_NAMES[c['key']]
            main = names[0]
            write(os.path.join(tdir, 'cursors', main), cached('x', tname, c, lambda: build_xcursor(c, th)))
            for alias in names[1:]:
                if not os.path.lexists(os.path.join(tdir, 'cursors', alias)):
                    os.symlink(main, os.path.join(tdir, 'cursors', alias))
        print('linux', name, 'ok', flush=True)
    p = os.path.join(out, 'Linux', 'install.sh')
    write(p, LINUX_INSTALL.replace('%COLORS%', ' '.join(COLORS)), 'w')
    os.chmod(p, 0o755)


# ------------------------------------------------------------ main
def make_windows(out):
    for tname in ALL_THEMES:
        folder = os.path.join(out, 'Windows', tname if tname in ORDER else os.path.join('Colors', tname))
        for c in CURS:
            if c.get('anim'):
                data = cached('w', tname, c, lambda: make_ani(
                    [build_cur(c, tname, f, c.get('ani_sizes', ANI_SIZES)) for f in range(c.get('nframes', NFRAMES))],
                    c['rate'], f'Halo {pretty(tname)} - {c["name"]}'))
                write(os.path.join(folder, c['file'] + '.ani'), data)
            else:
                write(os.path.join(folder, c['file'] + '.cur'), cached('w', tname, c, lambda: build_cur(c, tname)))
        write(os.path.join(folder, 'Install.inf'), inf_text(tname).replace('\n', '\r\n'), 'w')
        print('windows', tname, 'ok', flush=True)
    ps1 = PS1.replace('%ACCENTS%', ', '.join(f"'{c}'" for c in COLORS)).replace('%NACC%', str(len(COLORS) + 1))
    write(os.path.join(out, 'Windows', 'Install-Cursors.ps1'), '\ufeff' + ps1.replace('\n', '\r\n'), 'w')
    write(os.path.join(out, 'Windows', 'Install.bat'), BAT_INSTALL.replace('\n', '\r\n'), 'w')
    write(os.path.join(out, 'Windows', 'Restore.bat'), BAT_RESTORE.replace('\n', '\r\n'), 'w')


def make_colors(path):
    """README image: for every accent color, the three accented cursors (Working, Busy, Link) in Light and Dark."""
    n, T, pad, lab, rowh = 64, 72, 22, 150, 84
    pw = 3 * T + 2 * pad
    img = Image.new('RGBA', (lab + 2 * pw + 3 * 16, len(COLORS) * rowh + 2 * 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT, 26)
    except OSError:
        font = ImageFont.load_default()
    for r, cn in enumerate(COLORS):
        y = 16 + r * rowh
        d.rounded_rectangle([0, y, img.width, y + rowh - 8], radius=18, fill=(0, 0, 0, 0))
        d.text((8, y + 22), cn, font=font, fill=(120, 124, 132, 255))
        for k, (base, bg) in enumerate((('Light', (28, 29, 33, 255)), ('Dark', (242, 243, 245, 255)))):
            x0 = lab + 16 + k * (pw + 16)
            d.rounded_rectangle([x0, y, x0 + pw, y + rowh - 8], radius=18, fill=bg)
            for i, key in enumerate(ACC_KEYS):
                c = next(c for c in CURS if c['key'] == key)
                im = cursor_image(c, THEMES[f'{cn}-{base}'], n, 150 if key == 'busy' else 0)
                img.alpha_composite(im, (x0 + pad + i * T, y + (rowh - 8 - n) // 2))
    img.save(path)


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    make_windows(OUT)
    make_linux(OUT)
    write(os.path.join(OUT, 'README.md'), README, 'w')
    make_preview(os.path.join(OUT, 'preview.png'))
    make_colors(os.path.join(OUT, 'colors.png'))
    print('done')


if __name__ == '__main__':
    main()
