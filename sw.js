/* מניין של אחד — service worker
   שומר את האפליקציה במכשיר כדי שתעבוד גם בלי אינטרנט. */
const CACHE = "mse-v27";
const FILES = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./content.js",
  "./texts.js",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-maskable-192.png",
  "./icon-maskable-512.png"
];

self.addEventListener("install", e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate", e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

/* קודם מהרשת (כדי לקבל עדכונים), ואם אין חיבור — מהמטמון */
self.addEventListener("fetch", e=>{
  if(e.request.method!=="GET") return;
  e.respondWith(
    fetch(e.request)
      .then(res=>{
        const copy = res.clone();
        caches.open(CACHE).then(c=>c.put(e.request, copy)).catch(()=>{});
        return res;
      })
      .catch(()=>caches.match(e.request).then(r=>r || caches.match("./index.html")))
  );
});
