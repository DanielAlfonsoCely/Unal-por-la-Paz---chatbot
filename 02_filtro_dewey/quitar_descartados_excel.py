"""Quita de la hoja Gráficas las áreas y códigos Dewey que el filtro descarta.
Solo reescribe las hojas ocultas Datos y DatosDewey, el rango del desplegable de Dewey
y la nota de esa sección. No toca nada más del archivo (formato, gráficas, cambios a mano).
Uso: python quitar_descartados.py candidatos.csv entrada.xlsx salida.xlsx
"""
import re, sys, zipfile, html
from collections import Counter, defaultdict
from xml.sax.saxutils import escape
import pandas as pd

CSV, ENTRADA, SALIDA = sys.argv[1:4]

# ---- reglas del filtro (scripts/filtro_dewey.py) ----
DESCARTA_PRIMER_DIGITO = set('01248')
NO_3XX = {'332', '395'}
SI_5XX = {'510', '519', '522', '526', '530', '542', '549', '552', '553', '558', '560', '577'}
SI_6XX = {'621', '622', '630', '633', '634', '635', '636', '637', '638', '639', '640', '643', '645',
          '649', '657', '668', '670', '677', '696', '610'}

def descartado(c):
    d = c[0]
    if d in DESCARTA_PRIMER_DIGITO:
        return True
    if c in NO_3XX:
        return True
    if d == '5' and c != '500' and c not in SI_5XX:
        return True
    if d == '6' and c != '600' and c not in SI_6XX:
        return True
    return False

# ---- datos (mismo tratamiento que armar_excel_filtrados.py) ----
df = pd.read_csv(CSV, dtype=str)
df.columns = [c.lstrip('﻿') for c in df.columns]
df['Tipo'] = df['Tipo'].replace({'Trabajo de grado – Maestría': 'Trabajo de grado - Maestría',
                                 'Otros': 'Otro', 'otros': 'Otro', 'Libro Completo': 'Libro completo'})

def limpio(v):
    if v is None or pd.isna(v):
        return None
    v = str(v).strip()
    return v or None

def norm_code(c):
    c = c.strip()
    return c + '00' if len(c) == 1 else c + '0' if len(c) == 2 else c[:3]

names = defaultdict(Counter)
for txt in df['Dewey'].dropna():
    for seg in re.split(r'::| / ', txt):
        m = re.match(r'^\s*(\d{1,3})\s*(?:-\s*)?(.+?)\s*$', seg)
        if m and re.search(r'[A-Za-zÁÉÍÓÚáéíóúñ]', m.group(2)):
            names[norm_code(m.group(1))][re.sub(r'\s+', ' ', m.group(2)).strip(' -;,')] += 1
DEWEY = {k: v.most_common(1)[0][0] for k, v in names.items()}
for k, v in {'300': 'Ciencias sociales', '500': 'Ciencias naturales y matemáticas',
             '600': 'Tecnología (ciencias aplicadas)', '700': 'Las artes', '900': 'Historia y geografía'}.items():
    DEWEY.setdefault(k, v)
etiqueta = lambda c: f'{c} – {DEWEY.get(c, "(sin nombre en el repositorio)")}'

def codigos(s):
    if not isinstance(s, str) or not s.strip():
        return []
    out = []
    for c in s.split('|'):
        c = norm_code(c)
        if c not in out:
            out.append(c)
    return out

todos = df['dewey_codigos'].apply(codigos)
utiles = todos.apply(lambda cs: [c for c in cs if not descartado(c)])
sin_dewey = int((todos.map(len) == 0).sum())
solo_desc = int(((todos.map(len) > 0) & (utiles.map(len) == 0)).sum())

TOP = 15
def bloque(serie, ordenar=False, top=TOP):
    s = serie.map(limpio)
    vac = int(s.isna().sum())
    vc = s.dropna().value_counts()
    if ordenar:
        vc = vc.sort_index()
    it = list(vc.items())
    if len(it) > top:
        it = it[:top] + [(f'Otros ({len(vc) - top} más)', sum(v for _, v in it[top:]))]
    if vac:
        it.append(('(vacío)', vac))
    return it

def doble(serie, completa=False, **kw):
    g = bloque(serie, **kw)
    return (bloque(serie, top=10**6, **kw) if completa else g), g

cent_cnt, code_cnt = Counter(), defaultdict(Counter)
for cs in utiles:
    for ce in {c[0] for c in cs}:
        cent_cnt[ce] += 1
    for c in cs:
        code_cnt[c[0]][c] += 1
cent_items = [(etiqueta(ce + '00'), n) for ce, n in sorted(cent_cnt.items())]
cent_items.append(('(sin Dewey)', sin_dewey))
if solo_desc:
    cent_items.append(('(solo códigos descartados; entró por palabra clave)', solo_desc))

anio = df['anio'].map(lambda x: str(int(float(x))) if limpio(x) else None)
VARS = [('Año',) + doble(anio, ordenar=True), ('Tipo',) + doble(df['Tipo']),
        ('Dewey por centena', cent_items, cent_items),
        ('Sede o comunidad',) + doble(df['comm_2']),
        ('Facultad o colección',) + doble(df['comm_1'], completa=True),
        ('Programa',) + doble(df['collection']),
        ('Tipo de colección (comm_3)',) + doble(df['comm_3']),
        ('Modalidad',) + doble(df['Modalidad']),
        ('Área curricular',) + doble(df['Área curricular'])]

# ---- construir celdas de las hojas ocultas ----
def col_letter(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def hoja_xml(celdas):
    """celdas: dict (fila, col) -> valor. Devuelve <sheetData> con texto en línea."""
    filas = defaultdict(list)
    for (r, c), v in celdas.items():
        filas[r].append((c, v))
    out = ['<sheetData>']
    for r in sorted(filas):
        out.append(f'<row r="{r}">')
        for c, v in sorted(filas[r]):
            ref = f'{col_letter(c)}{r}'
            if isinstance(v, (int, float)):
                out.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                out.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
        out.append('</row>')
    out.append('</sheetData>')
    maxr = max(r for r, _ in celdas); maxc = max(c for _, c in celdas)
    return ''.join(out), f'A1:{col_letter(maxc)}{maxr}'

def escribir(cel, k, nombre, tabla, graf, lista=None):
    ca = 5 * k + 1
    cel[(1, ca)] = nombre
    for off, h in enumerate([' (n)', ' (g)', ' (gn)', ' (lista)'], 1):
        cel[(1, ca + off)] = nombre + h
    for i, (l, n) in enumerate(tabla):
        cel[(i + 2, ca)] = str(l); cel[(i + 2, ca + 1)] = int(n)
    for i, (l, n) in enumerate(graf):
        cel[(i + 2, ca + 2)] = str(l); cel[(i + 2, ca + 3)] = int(n)
    for i, l in enumerate(lista or []):
        cel[(i + 2, ca + 4)] = l

datos = {}
for k, (n, t, gr) in enumerate(VARS):
    escribir(datos, k, n, t, gr)
listcol = 5 * len(VARS) + 2
for i, (n, _, _) in enumerate(VARS):
    datos[(i + 1, listcol)] = n

TOPB = 20
dd, cent_labels = {}, []
for k, ce in enumerate(sorted(code_cnt)):
    lab = etiqueta(ce + '00'); cent_labels.append(lab)
    it = [(etiqueta(c), n) for c, n in code_cnt[ce].most_common()]
    if len(it) > TOPB:
        it = it[:TOPB] + [(f'Otros códigos ({len(it) - TOPB} más)', sum(n for _, n in it[TOPB:]))]
    escribir(dd, k, lab, it, it, [etiqueta(c) for c in sorted(code_cnt[ce])])
listb = 5 * len(cent_labels) + 2
for i, l in enumerate(cent_labels):
    dd[(i + 1, listb)] = l
print('centenas que quedan:', cent_labels)
print('sin dewey:', sin_dewey, '| solo códigos descartados:', solo_desc)

# ---- parchar el archivo ----
zin = zipfile.ZipFile(ENTRADA)
files = {n: zin.read(n) for n in zin.namelist()}
wb = files['xl/workbook.xml'].decode('utf8')
rels = files['xl/_rels/workbook.xml.rels'].decode('utf8')

def ruta_hoja(nombre):
    m = re.search(r'<sheet\b[^>]*name="' + re.escape(nombre) + r'"[^>]*/>', wb)
    rid = re.search(r'r:id="([^"]+)"', m.group(0)).group(1)
    t = re.search(r'<Relationship\b[^>]*Id="' + rid + r'"[^>]*/?>', rels) or \
        re.search(r'<Relationship\b[^>]*Target="[^"]*"[^>]*Id="' + rid + '"', rels)
    tgt = re.search(r'Target="([^"]+)"', t.group(0)).group(1).lstrip('/')
    return tgt if tgt.startswith('xl/') else 'xl/' + tgt

def reemplazar_datos(nombre, celdas):
    p = ruta_hoja(nombre)
    x = files[p].decode('utf8')
    sd, dim = hoja_xml(celdas)
    x = re.sub(r'<sheetData\s*/>|<sheetData>.*?</sheetData>', lambda _: sd, x, flags=re.S)
    x = re.sub(r'<dimension ref="[^"]*"\s*/>', f'<dimension ref="{dim}"/>', x)
    files[p] = x.encode('utf8')

reemplazar_datos('Datos', datos)
reemplazar_datos('DatosDewey', dd)

# desplegable de Dewey -> nuevo rango
pg = ruta_hoja('Gráficas')
g = files[pg].decode('utf8')
L = col_letter(listb)
g, n1 = re.subn(r"(&#39;|')?DatosDewey(&#39;|')?!\$[A-Z]+\$1:\$[A-Z]+\$\d+", f'DatosDewey!${L}$1:${L}${len(cent_labels)}', g)
print('desplegables actualizados:', n1)

# si el selector de Dewey quedó en un área quitada, ponerlo en la primera que queda
m = re.search(r'<dataValidation\b[^>]*sqref="([A-Z]+\d+)"[^>]*>(?:(?!</dataValidation>).)*DatosDewey', g, flags=re.S) \
    or re.search(r'DatosDewey!\$[A-Z]+\$1:[^<]*</xm:f></x14:formula1>\s*<xm:sqref>([A-Z]+\d+)</xm:sqref>', g)
if m:
    ref = m.group(1)
    def fijar(mc):
        attrs = re.sub(r'\s*t="[^"]*"', '', mc.group(1))
        return f'<c{attrs} t="inlineStr"><is><t>{escape(cent_labels[0])}</t></is></c>'
    g, n2 = re.subn(r'<c( r="' + ref + r'"[^>]*?)(?:/>|>.*?</c>)', fijar, g, count=1, flags=re.S)
    print('selector', ref, 'reiniciado:', n2)
files[pg] = g.encode('utf8')

# nota de la sección Dewey (puede estar en la hoja o en sharedStrings)
VIEJA = 'Las áreas descartadas (000, 100, 200, 400, 800) aparecen porque esos documentos también traen otro código que sí pasó.'
NUEVA = 'Solo se muestran áreas y códigos que pasan el filtro: los descartados (ej. 200 religión, 332, 650) se quitaron aunque algún documento los traiga junto a otro código.'
hecho = 0
for p in [pg, 'xl/sharedStrings.xml']:
    if p in files:
        t = files[p].decode('utf8')
        t, n = re.subn(r'(<t\b[^>]*>)[^<]*descartadas \(000[^<]*(</t>)', lambda m: m.group(1) + escape(NUEVA) + m.group(2), t)
        hecho += n
        files[p] = t.encode('utf8')
print('nota actualizada:', hecho)

# recalcular al abrir
wb2 = re.sub(r'<calcPr\b[^>]*/>', lambda m: m.group(0) if 'fullCalcOnLoad' in m.group(0)
             else m.group(0).replace('/>', ' fullCalcOnLoad="1"/>'), wb)
if '<calcPr' not in wb2:
    wb2 = wb2.replace('</workbook>', '<calcPr fullCalcOnLoad="1"/></workbook>')
files['xl/workbook.xml'] = wb2.encode('utf8')

with zipfile.ZipFile(SALIDA, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in zin.namelist():
        z.writestr(zin.getinfo(n), files[n], compress_type=zipfile.ZIP_DEFLATED)
print('ok', SALIDA)
