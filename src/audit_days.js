/* ביקורת ימים מיוחדים — מריץ את האפליקציה על כל ימות השנה
   ובודק שהמבנה, ההוראות המותנות והנוסח מתאימים ליום.
   סורק 400 יום רצופים כדי לכסות שנה עברית שלמה כולל מעוברת. */
const vm = require('vm'), fs = require('fs'), path = require('path');
const APP = process.argv[2] || 'app';
const DAYS = Number(process.argv[3] || 400);

const ctx = {console, Date, Intl, Math, JSON, setTimeout, clearTimeout,
             setInterval, clearInterval, URLSearchParams};
ctx.window = ctx;
ctx.addEventListener = () => {}; ctx.removeEventListener = () => {};
ctx.matchMedia = () => ({matches:false, addEventListener(){}});
ctx.localStorage = {getItem:()=>null, setItem(){}, removeItem(){}};
ctx.navigator = {}; ctx.location = {href:'', search:''};
const el = () => ({style:{}, classList:{add(){},remove(){},toggle(){},contains:()=>false},
  addEventListener(){}, appendChild(){}, querySelector:()=>el(), querySelectorAll:()=>[],
  setAttribute(){}, getAttribute:()=>null, focus(){}, scrollIntoView(){}, remove(){},
  set innerHTML(v){this._h=v}, get innerHTML(){return this._h||''}, dataset:{}});
ctx.document = {getElementById:()=>el(), querySelector:()=>el(), querySelectorAll:()=>[],
  createElement:()=>el(), body:el(), addEventListener(){}, documentElement:el()};
vm.createContext(ctx);

const html = fs.readFileSync(path.join(APP,'index.html'),'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/g).pop()
                   .replace(/^<script>/,'').replace(/<\/script>$/,'');
vm.runInContext(fs.readFileSync(path.join(APP,'texts.js'),'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(APP,'content.js'),'utf8'), ctx);
vm.runInContext(script + ';this.state=state;this.settings=settings;this.dayFlags=dayFlags;' +
                'this.buildStructure=buildStructure;this.textFor=textFor;this.hebDateHe=hebDateHe;', ctx);

const bare = s => s.replace(/[֑-ׇ]/g,'');
/* בודק רק פסקאות נוסח, לא הוראות (§) */
const has = (arr, sub) => (arr||[]).some(p => p.indexOf('§') !== 0 && bare(p).includes(sub));

const problems = new Map();          // הודעה -> דוגמת תאריך אחת
const seen = new Set();              // אילו סוגי ימים נבדקו בפועל
function flag(msg, when) { if (!problems.has(msg)) problems.set(msg, when); }

const start = new Date(2026, 7, 1);
for (let i = 0; i < DAYS; i++) {
  const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
  if (d.getDay() === 6) continue;                    // שבת — האפליקציה לימות החול
  const when = ctx.hebDateHe(d);

  for (const minyan of [false, true]) {
    ctx.settings.minyan = minyan;
    for (const tef of ['shacharit','mincha','maariv','kriatShma']) {
      const evening = (tef === 'maariv' || tef === 'kriatShma');
      let f, G;
      try {
        f = ctx.dayFlags(d, evening);
        ctx.state.flags = f;
        G = ctx.buildStructure(tef, f);
      } catch (e) {
        flag(`${tef}: קריסה — ${e.message}`, when); continue;
      }
      const miss = [];
      let w = 0, n = 0;
      G.forEach(g => g.subs.forEach(s => {
        n++; w += s.w;
        const t = ctx.textFor(s.id);
        if (!t || !t.length) miss.push(s.id);
      }));
      if (miss.length) flag(`${tef}${minyan?' (מניין)':''}: חסר נוסח — ${[...new Set(miss)].join(' ')}`, when);
      if (!n) flag(`${tef}: אין קטעים כלל`, when);
      if (!(w > 0)) flag(`${tef}: משקל כולל אינו תקין`, when);

      if (tef === 'shacharit' && minyan) {
        const ids = []; G.forEach(g => g.subs.forEach(s => ids.push(s.id)));
        const on = id => ids.includes(id);
        if (f.roshChodesh) { seen.add('ראש חודש');
          if (!on('hallel')) flag('ראש חודש: חסר הלל', when);
          if (!on('musaf'))  flag('ראש חודש: חסר מוסף', when);
          if (f.tachanun)    flag('ראש חודש: מופיע תחנון', when);
          if (!on('barchi')) flag('ראש חודש: חסר ברכי נפשי', when); }
        if (f.cholHamoed) { seen.add('חול המועד ' + f.cholHamoed);
          if (!on('hallel')) flag('חול המועד: חסר הלל', when);
          if (f.tachanun)    flag('חול המועד: מופיע תחנון', when); }
        if (f.chanukah) { seen.add('חנוכה');
          if (!on('hallel')) flag('חנוכה: חסר הלל', when);
          if (f.tachanun)    flag('חנוכה: מופיע תחנון', when);
          if (!has(ctx.textFor('amida3'),'ועל הנסים')) flag('חנוכה: חסר ועל הנסים', when); }
        if (f.purim) { seen.add('פורים');
          if (f.tachanun) flag('פורים: מופיע תחנון', when);
          if (!has(ctx.textFor('amida3'),'ועל הנסים')) flag('פורים: חסר ועל הנסים', when); }
        if (f.fast) { seen.add('תענית — ' + f.fast);
          if (!on('anenuSz')) flag(`תענית (${f.fast}): חסר עננו`, when);
          if (f.tachanun && !on('avinu')) flag(`תענית (${f.fast}): חסר אבינו מלכנו`, when);
          if (!on('trRead'))  flag(`תענית (${f.fast}): חסרה קריאת התורה`, when); }
        if (f.aseretYemeiTeshuva) { seen.add('עשרת ימי תשובה');
          if (!has(ctx.textFor('amida1'),'זכרנו לחיים')) flag('עשי״ת: חסר זכרנו לחיים', when);
          if (f.tachanun && !on('avinu')) flag('עשי״ת: חסר אבינו מלכנו', when); }
        if (f.omer) seen.add('ספירת העומר');
        if (!f.roshChodesh && !f.cholHamoed) {
          if (has(ctx.textFor('amida3'),'יעלה ויבא')) flag('יום רגיל: מופיע יעלה ויבוא', when);
        } else if (!has(ctx.textFor('amida3'),'יעלה ויבא')) {
          flag('ר״ח / חוה״מ: חסר יעלה ויבוא', when);
        }
        if (!f.chanukah && !f.purim && has(ctx.textFor('amida3'),'ועל הנסים'))
          flag('יום רגיל: מופיע ועל הנסים', when);
        if (!f.aseretYemeiTeshuva && has(ctx.textFor('amida1'),'זכרנו לחיים'))
          flag('יום רגיל: מופיע זכרנו לחיים', when);
        if (!(f.fast && String(f.fast).includes('תשעה באב')) &&
            has(ctx.textFor('chazaraMin'),'נחם'))
          flag('יום רגיל: מופיע נחם', when);
      }
    }
  }
}

console.log('סוגי ימים שנבדקו: ' + [...seen].sort().join(' · '));
console.log('='.repeat(60));
if (problems.size) {
  for (const [msg, when] of problems) console.log('✗ ' + msg + '   (' + when + ')');
} else {
  console.log('✓ לא נמצאו בעיות');
}
