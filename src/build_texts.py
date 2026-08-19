# -*- coding: utf-8 -*-
"""מייצר את texts.js מתוך הסידור המשוחזר, לפי טבלת המיפוי.

שורות מנוקדות הופכות לפסקאות תפילה; הוראה הלכתית שקודמת לקטע
נשמרת כהערה בסימון § שהאפליקציה מציגה בזהב.
"""
import json
import re
import sys

sys.path.insert(0, 'src')
from map_shacharit import (SHACHARIT, MINCHA, MAARIV, KRIAT_SHMA,
                           COND_LINES, SHIR_YOM_LINES, OMER_LINES,
                           MINYAN, HINT_ONLY, HINT_DROP, BODY_FIX,
                           HINT_AFTER, BODY_TRIM, VIRTUAL, COND_HINT,
                           HINT_FORCE, TRIPLE, PRE_SPLIT)

NIK = re.compile(r'[֑-ׇ]')
HEBL = re.compile(r'[א-ת]')
SRC = 'src/siddur-fixed.txt'
OUT = 'app/texts.js'

# הוראות ארוכות מדי אינן מסייעות בתוך תפילה
MAX_HINT = 180


def nik_ratio(s):
    h = HEBL.findall(s)
    return len(NIK.findall(s)) / len(h) if h else 0.0


def is_text(line):
    return nik_ratio(line) > 0.3


def is_hint(line, headers):
    t = line.strip()
    return bool(t) and not is_text(line) and t not in headers


# שאריות שנוצרו מפיצול ראשי תיבות דבוקים במקור
HINT_FIX = [
    (r'^\s*י["״]ת\s*בעש\s*$', 'בעשרת ימי תשובה'),
    (r'^\s*בעש\s*י["״]ת\s*$', 'בעשרת ימי תשובה'),
    (r'^\s*בעשי["״]ת\s*$', 'בעשרת ימי תשובה'),
    (r'^\s*ב?קיץבחורף\s*$', 'בקיץ אומרים מוֹרִיד הַטָּל · בחורף מַשִּׁיב הָרוּחַ'),
    (r'^\s*י["״]ת\s*$', 'בעשרת ימי תשובה אומרים הַמֶּלֶךְ הַקָּדוֹשׁ'),
    (r'^בראש חודש ובחול המועד אומרים.*$', 'בראש חודש ובחול המועד — יעלה ויבוא'),
    (r'^בחנוכה ופורים אומרים.*$', 'בחנוכה ובפורים — ועל הנסים'),
    (r'^\s*ל(חנוכה|פורים)\s*[—-]\s*$', r'ל\1'),
    # ההוראה הזו התהפכה במקור בגלל הדבקת המילים
    (r'^בימים שאין אומרים תחנון.*מתחילים.*$',
     'ביום שאין בו תחנון אין אומרים תפילה לדוד, אלא מתחילים מבית יעקב'),
    (r'^\s*ע["״]כ\s*שמוסיפין\s*בשני\s*ובחמישי\s*מה\s*$',
     'עד כאן מה שמוסיפין בשני ובחמישי'),
    (r'אמן(אמן)+', ''),
    # שאריות סימון "ג״פ" ורשימות ראשי התיבות של אנא בכח
    (r'^\s*[א-ת]{0,4}(?:ג["״]פ\s*)+$', ''),
    (r'^\s*אנא(?:\s*[א-ת]{1,4}["״][א-ת]{1,4})+\s*$', ''),
    (r'^\s*נ["״]א\s*$', ''),
]

# סימוני "ג״פ" אינם חלק מהנוסח ולעולם אינם מופיעים בו כטקסט
BODY_GPP = re.compile(r'\s*(?:ג["״]פ\s*)+')


def clean_hint(line):
    # הוראות הלכתיות אינן מנוקדות; הסרת ניקוד מאפשרת זיהוי אמין של שאריות
    h = NIK.sub('', line.strip()).rstrip(':')
    for pat, rep in HINT_FIX:
        h = re.sub(pat, rep, h)
    h = re.sub(r'\s{2,}', ' ', h).strip(' :·')
    return '' if h in HINT_DROP else h


def clean_body(text):
    """מנקה שאריות ראשי תיבות שנדבקו לתוך גוף הקטע."""
    for pat, rep in BODY_FIX:
        text = re.sub(pat, rep, text)
    text = BODY_GPP.sub(' ', text)
    text = re.sub(r'\s+([,.;:])', r'\1', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def expand(spec):
    out = []
    for it in spec:
        if isinstance(it, tuple):
            out.extend(range(it[0], it[1] + 1))
        else:
            out.append(it)
    return out


def make_virtual(lines):
    """יוצר שורות וירטואליות מקטעים שנדחסו יחד במקור."""
    lines = list(lines)
    top = max(VIRTUAL) + 1
    lines.extend([''] * (top - len(lines)))
    for idx, spec in VIRTUAL.items():
        kind = spec[0]
        if kind == 'join':
            lines[idx] = ' '.join(lines[n].strip() for n in spec[1])
        else:
            src, mark = spec[1], spec[2]
            raw = lines[src]
            if kind == 'before':
                pos = raw.find(mark)
                lines[idx] = raw[:pos] if pos > 0 else raw
            else:
                pos = raw.rfind(mark)
                lines[idx] = raw[pos + len(mark):] if pos >= 0 else ''
    return lines


def build(lines, mapping):
    lines = make_virtual(lines)
    headers = {l.strip() for l in lines if l.startswith(' ') and nik_ratio(l) < 0.05 and l.strip()}
    texts, used_hints = {}, set()
    for key, spec in mapping.items():
        paras = []
        for n in expand(spec):
            # שורה קצרה ולא מנוקדת בתוך טווח היא הוראה, לא נוסח.
            # קטעים ארוכים מודפסים בסידור לעיתים בלי ניקוד — הם כן נוסח.
            if not is_text(lines[n]) and len(lines[n].strip()) < 120:
                h = clean_hint(lines[n])
                if h and n not in used_hints and len(h) <= MAX_HINT:
                    paras.append('§ ' + h)
                    used_hints.add(n)
                continue
            tag = COND_LINES.get(n)
            # בקטעים מותנים ההוראה יושבת אחרי הקטע; אחרת לפניו
            after = tag or n in HINT_AFTER
            order = (n + 1, n - 1) if after else (n - 1,)
            hint = ''
            for cand in order:
                if 0 <= cand < len(lines) and is_hint(lines[cand], headers) \
                        and cand not in used_hints:
                    h = clean_hint(lines[cand])
                    if h and len(h) <= MAX_HINT:
                        hint = h
                        used_hints.add(cand)
                    break
            if n in HINT_FORCE:
                hint = HINT_FORCE[n]
            if tag:
                label = COND_HINT.get(n) or hint or 'נאמר רק בימים אלה'
                paras.append('§@%s %s' % (tag, label))
            elif hint:
                paras.append('§ ' + hint)
            body = clean_body(lines[n])
            if n in BODY_TRIM:
                pat, pre = BODY_TRIM[n]
                body = pre + re.sub(pat, '', body)
            if body:
                paras.append(body)
        texts[key] = paras
    return texts


def emit(texts):
    parts = ['/* נוסח התפילה — סידור תהלת ה\', נוסח האר"י.',
             '   נוצר אוטומטית מקובץ המקור; אין לערוך ידנית. */',
             'const TEXTS = {']
    for i, (k, v) in enumerate(texts.items()):
        body = ',\n'.join('  ' + json.dumps(p, ensure_ascii=False) for p in v)
        comma = ',' if i < len(texts) - 1 else ''
        parts.append(f'{k}: [\n{body}\n]{comma}\n')
    parts.append('};')
    return '\n'.join(parts)


def split_verses(para):
    """מפצל פסקה לפסוקים לפי נקודתיים. פסוק קצר מדי אינו עומד
    בפני עצמו — הוא שריד של סימון שהוסר, ומצורף לפסוק שאחריו."""
    raw = [v.strip() for v in para.split(':') if v.strip()]
    out = []
    for v in raw:
        if out and len([w for w in out[-1].split() if HEBL.search(w)]) < 3:
            out[-1] = out[-1] + ' ' + v
        else:
            out.append(v)
    return [v + ':' for v in out]


def insert_break(para, marker):
    """מוסיף סימן פסוק לפני מילות המפתח, גם כשיש ניקוד ביניהן.
    המיקום נמצא על הטקסט בלי ניקוד ומומר חזרה למקור."""
    idx, bare = [], []
    for i, ch in enumerate(para):
        if NIK.match(ch):
            continue
        bare.append(ch)
        idx.append(i)
    flat = ''.join(bare)
    at = flat.find(marker)
    if at <= 0:
        return para
    cut = idx[at]
    return para[:cut].rstrip() + ': ' + para[cut:]


def expand_triples(texts):
    """כותב במפורש שלוש פעמים כל פסוק שנאמר שלוש פעמים.
    הפסוקים מזוהים לפי פתיחתם, כדי שהחזרה תיפול על הפסוק הנכון."""
    for key, marks in TRIPLE.items():
        paras = texts.get(key)
        if not paras:
            continue
        bare = [NIK.sub('', m) for m in marks]
        pre = PRE_SPLIT.get(key, [])
        out = []
        for p in paras:
            if p.startswith('§'):
                out.append(p)
                continue
            for m in pre:                      # מפרידים פסוק שנדבק לקודמו
                p = insert_break(p, m)
            for v in split_verses(p):
                vb = NIK.sub('', v).replace('־', ' ')
                out.append(' '.join([v] * 3)
                           if any(vb.startswith(m) for m in bare) else v)
        texts[key] = out
    return texts


def count_words(paras):
    """מספר מילות הנוסח בקטע. הוראות (§) אינן נספרות.
    קטע שמסומן לאמירה שלוש פעמים נספר שלוש פעמים."""
    total = 0
    for p in paras:
        if p.startswith('§'):
            continue
        total += len([w for w in p.split() if HEBL.search(w)])
    return total


def emit_weights(texts, days):
    w = {k: count_words(v) for k, v in texts.items()}
    # שיר של יום — ממוצע הימים, שכן הקטע מתחלף
    if days:
        w['shirshelyom'] = round(sum(count_words(d) for d in days) / len(days))
    body = ',\n'.join('  %s: %d' % (k, n) for k, n in sorted(w.items()) if n)
    return ('\n/* משקל כל קטע — מספר המילים בנוסח שלו.\n'
            '   ממנו נגזר הזמן שכל קטע מקבל מתוך משך התפילה. */\n'
            'const WORDS = {\n%s\n};\n' % body)


def emit_shir(days):
    body = ',\n'.join(json.dumps(d, ensure_ascii=False) for d in days)
    return ('\n/* שיר של יום — מזמור לכל יום בשבוע */\n'
            'const SHIR_YOM_TEXTS = [\n%s\n];\n'
            'TEXTS.shirshelyom = SHIR_YOM_TEXTS[0];\n' % body)


if __name__ == '__main__':
    lines = open(SRC, encoding='utf-8').read().split('\n')
    mapping = {}
    for part in (SHACHARIT, MINCHA, MAARIV, KRIAT_SHMA, MINYAN):
        mapping.update(part)
    texts = build(lines, mapping)
    texts = expand_triples(texts)
    for k, hint in HINT_ONLY.items():
        texts[k] = ['§ ' + hint]
    days = [[lines[n].strip() for n in day if lines[n].strip()]
            for day in SHIR_YOM_LINES]
    omer = [lines[n].strip() for n in OMER_LINES]
    out = (emit(texts) + '\n' + emit_weights(texts, days) + emit_shir(days) +
           '\n/* ספירת העומר — מ״ט הימים */\nconst OMER_DAYS = ' +
           json.dumps(omer, ensure_ascii=False) + ';\n' +
           '\nif (typeof window !== "undefined") {\n'
           '  window.TEXTS = TEXTS;\n'
           '  window.SHIR_YOM_TEXTS = SHIR_YOM_TEXTS;\n'
           '  window.OMER_DAYS = OMER_DAYS;\n'
           '  window.WORDS = WORDS;\n}\n')
    open(OUT, 'w', encoding='utf-8').write(out)
    n_par = sum(len(v) for v in texts.values())
    n_hint = sum(1 for v in texts.values() for p in v if p.startswith('§'))
    print('קטעים:', len(texts))
    print('פסקאות:', n_par, '| מתוכן הוראות:', n_hint)
    print('שיר של יום:', [len(d) for d in days])
