# -*- coding: utf-8 -*-
"""משחזר את קובץ הסידור: מחזיר את המילה הפותחת שהתנתקה לסוף הקטע.

התקלה במקור: בקטעים שבסידור מתחילים במילה מודגשת, המילה הפותחת
נותקה מהקטע והועברה לשורה שאחריו. שורות הגוף החסרות מזוהות
לפי רווח מוביל.
"""
import re
import sys

NIK = re.compile(r'[֑-ׇ]')
HEBL = re.compile(r'[א-ת]')


def nik_ratio(s):
    h = HEBL.findall(s)
    return len(NIK.findall(s)) / len(h) if h else 0.0


# רצף של 3+ אותיות עבריות רצופות בלי שום ניקוד ביניהן — כמעט תמיד
# הוראה הלכתית שנדבקה, שכן מילה מנוקדת אינה מכילה רצף כזה.
UNPOINTED_RUN = re.compile(r'[א-ת]{3,}(?![֑-ׇ])')
# ראשי תיבות דבוקים, כגון ע״כ או ג״פ
ABBREV = re.compile(r'[א-ת]["״׳\'][א-ת]')


def split_glued(s):
    """מפריד ליבה מנוקדת מהוראות לא-מנוקדות שנדבקו אליה.

    מחזיר (ליבה, הוראות). מטפל גם בהדבקה בלי רווח, לפני או אחרי.
    """
    instr = []

    def grab(m):
        run = m.group(0)
        start = m.start()
        # אם הרצף דבוק ישירות למילה מנוקדת (התו שלפניו הוא ניקוד),
        # האות הראשונה של הרצף היא סופה של אותה מילה — מחזירים אותה.
        give_back = ''
        if start > 0 and NIK.match(m.string[start - 1]):
            give_back, run = run[0], run[1:]
            if len(run) < 3:
                return give_back + run
        instr.append(run)
        return give_back + ' '

    core = ABBREV.sub(grab, s)
    core = UNPOINTED_RUN.sub(grab, core)
    # מה שנשאר ואין בו ניקוד כלל — גם הוא הוראה
    keep = []
    for w in core.split():
        if not HEBL.search(w):
            continue          # פיסוק יתום שנשאר אחרי החילוץ
        if not NIK.search(w):
            instr.append(w)
        else:
            keep.append(w)
    return ' '.join(keep).strip(), ' '.join(instr).strip()


def is_body(line):
    """שורה שאיבדה את מילתה הראשונה.

    הסימן הוא פתיחה ברווח או בסימן פיסוק, וטקסט מנוקד בהמשך.
    """
    return line[:1] in (' ', ',', '.', ';', ':', '־') and nik_ratio(line) > 0.3


# מקרים שבהם המילה הפותחת אבדה לגמרי מהמקור ולא נמצאת בשורה סמוכה.
# המפתח הוא תחילת שורת הגוף; הערך הוא המילה שיש להחזיר.
LOST = [
    ('אנחנו לך, שאתה הוא', 'מוֹדִים'),
    ('צבאות עמנו, משגב', 'יְיָ'),
    ('יי אורי וישעי', 'לְדָוִד'),
    ('ממעמקים קראתיך', 'שִׁיר הַמַּעֲלוֹת'),
    (', בכח גדלת ימינך', 'אָנָּא'),
]


def bare(s):
    """מסיר ניקוד וטעמים להשוואה."""
    return NIK.sub('', s).strip()


def patch_lost(line):
    body = line.strip()
    b = bare(body)
    for prefix, word in LOST:
        if b.startswith(prefix):
            return word + ' ' + body
    return None


def repair(lines):
    out, i, merged, left = [], 0, 0, []
    while i < len(lines):
        cur = lines[i]
        if is_body(cur):
            nxt = lines[i + 1] if i + 1 < len(lines) else ''
            if nxt and not nxt.startswith(' '):
                core, instr = split_glued(nxt)
            else:
                core, instr = '', ''
            # הליבה חייבת להיות מילה פותחת, לא קטע שלם
            if core and len(core) < 45 and len(core.split()) <= 4:
                if instr:
                    out.append(instr)
                joined = (core + ' ' + cur.strip()).strip()
                joined = re.sub(r'\s+([,.;:])', r'\1', joined)   # רווח יתום לפני פיסוק
                joined = re.sub(r'\s{2,}', ' ', joined)
                out.append(joined)
                merged += 1
                i += 2
                continue
            fixed = patch_lost(cur)
            if fixed:
                out.append(fixed)
                merged += 1
                i += 1
                continue
            left.append(i)
        out.append(cur)
        i += 1
    return out, merged, left


if __name__ == '__main__':
    raw = open(sys.argv[1], encoding='utf-8').read().replace('\r\n', '\n')
    lines = raw.split('\n')
    fixed, merged, left = repair(lines)
    print('אוחדו:', merged, '| נותרו:', len(left))
    open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(fixed))
    for i in left:
        print('  ?', i, lines[i][:65])
