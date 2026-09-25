const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const core=require('../app.js');
const root=path.resolve(__dirname,'../../basel-parking-netlify');
const artifacts=path.join(__dirname,'artifacts-v4');fs.mkdirSync(artifacts,{recursive:true});
const headers=JSON.parse(fs.readFileSync(path.join(__dirname,'headers.json')));
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css','.woff2':'font/woff2','.png':'image/png','.svg':'image/svg+xml','.ico':'image/x-icon','.xml':'application/xml','.txt':'text/plain','.webmanifest':'application/manifest+json'};
(async()=>{
const server=http.createServer((req,res)=>{
 const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 let file=path.join(root,pathname==='/'?'index.html':pathname);
 if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
 let status=200;
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()){file=path.join(root,'404.html');status=404;}
 res.writeHead(status,{...headers,'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(fs.readFileSync(file));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const url=`http://127.0.0.1:${server.address().port}/`;
let browser;
try {
browser=await chromium.launch({executablePath:process.env.BASEL_CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'],headless:true,...(process.env.HTTPS_PROXY?{proxy:{server:process.env.HTTPS_PROXY,bypass:'127.0.0.1,localhost'}}:{})});
const context=await browser.newContext({viewport:{width:375,height:667},isMobile:true,hasTouch:true});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{window.violations=[];document.addEventListener('securitypolicyviolation',e=>window.violations.push(e.violatedDirective));});
let current=Date.parse('2032-09-25T21:59:50Z'),free=30,offline=false,liveCalls=0,historyFree=40,lastHistory='',historyCalls=0,closed=false;
await page.clock.install({time:new Date(current)});
await page.route('https://data.bs.ch/**',async route=>{
 if(offline)return route.abort('internetdisconnected');
 const u=new URL(route.request().url());let rows;
 if(u.pathname.includes('/100088/')){
  liveCalls++;assert(u.searchParams.get('select').includes('free'));assert(!u.searchParams.get('select').includes('contact'));
  rows=[['city','City',free,100],['postbasel','Post Basel',77,null],['bahnhofsued','Bahnhof Süd',20,100],['badbahnhof','Bad. Bahnhof',189,750],['anfos','Anfos',20,165],['clarahuus','Clarahuus',10,52],['storchen','Storchen',0,142],['unknown','<img src=x onerror=alert(1)>',4,null]].map(([id2,name,f,total])=>({id2,name,address:'Basel',status:closed&&id2==='city'?'geschlossen':'offen',free:f,total,published:new Date(current).toISOString(),geo_point_2d:{lat:47.55,lon:7.59}}));
 } else {
  historyCalls++;lastHistory=u.searchParams.get('where');
  const day=Number(lastHistory.match(/= '(\d)'/)[1])-1,hour=Number(lastHistory.match(/hour\(published\) = (\d+)/)[1]);let date=core.localParts(current).date;
  while(core.weekday(date)!==day)date=core.addDays(date,-1);
  if(Date.parse(date+`T${String(hour).padStart(2,'0')}:00:00+02:00`)>=current)date=core.addDays(date,-7);
  rows=Array.from({length:20},(_,i)=>({id2:'city',free:historyFree,total:100,published:core.addDays(date,-i*7)+`T${String(hour).padStart(2,'0')}:00:00+02:00`}));
 }
 await route.fulfill({json:rows});
});
await page.goto(url);await page.waitForSelector('.card');await page.evaluate(()=>document.fonts.ready);assert(await page.evaluate(()=>document.fonts.check('16px Atkinson')), 'Local font failed to load');
assert.equal(await page.locator('.card').count(),4);
assert.equal(await page.locator('html').getAttribute('lang'),'en');
assert.equal(await page.locator('.search select').count(),4);
assert.equal(await page.locator('#day').inputValue(),'2032-09-25');
assert.equal(await page.locator('#day option').count(),14);
let box=await page.locator('#view-results').boundingBox();assert(box.y+box.height<=667,JSON.stringify(box));
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
await page.click('#show-more');
assert.equal(await page.locator('.card').count(),8);
assert.equal(await page.locator('[data-parking="postbasel"] .number').innerText(),'77');
assert.equal(await page.locator('[data-parking="postbasel"] meter').count(),0);
assert.equal(await page.locator('[data-parking="bahnhofsued"] .number').innerText(),'20');
assert((await page.locator('[data-parking="bahnhofsued"] .data-warning').innerText()).includes('outside'));
assert.equal(await page.locator('[data-parking="badbahnhof"] meter').count(),0);
assert.equal(await page.locator('[data-parking="unknown"] img').count(),0);
assert((await page.locator('[data-parking="unknown"] h3').innerText()).includes('<img'));
await page.click('[data-parking="city"] summary');
await page.locator('[data-parking="city"] summary').focus();
current+=20000;await page.clock.runFor(20000);
assert.equal(await page.locator('#day').inputValue(),'2032-09-26');
assert.equal(await page.locator('#day option').last().getAttribute('value'),'2032-10-09');
assert(await page.locator('[data-parking="city"] details').getAttribute('open')!==null);
assert(await page.locator('[data-parking="city"] summary').evaluate(el=>el===document.activeElement));
free=2;current+=60000;await page.clock.fastForward(60000);
await page.waitForFunction(()=>document.querySelector('[data-parking="city"] .number')?.textContent==='2');assert(liveCalls>=2);
closed=true;await page.click('#refresh');await page.waitForFunction(()=>document.querySelector('[data-parking="city"] .badge')?.textContent==='Reported closed');
assert.equal(await page.locator('[data-parking="city"] .number').innerText(),'n/a');
closed=false;await page.click('#refresh');
await page.selectOption('#day','2032-09-27');await page.selectOption('#hour','16');
await page.waitForFunction(()=>document.querySelector('[data-parking="city"] .number')?.textContent==='40');
assert(lastHistory.includes('2032'));assert(!lastHistory.includes('2026'));
assert((await page.locator('[data-parking="badbahnhof"] .measure').innerText()).includes('paused'));
const before=historyCalls;historyFree=60;current+=6*3600000+60000;await page.clock.fastForward(6*3600000+60000);
await page.waitForFunction(()=>document.querySelector('[data-parking="city"] .number')?.textContent==='60');assert(historyCalls>before);
await page.selectOption('#day','2032-09-26');await page.selectOption('#hour','now');
offline=true;current+=60000;await page.clock.fastForward(60000);
await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('unavailable'));
assert.equal(await page.locator('.number:not(.unknown)').count(),0);
offline=false;free=73;await page.evaluate(()=>window.dispatchEvent(new Event('online')));
await page.waitForFunction(()=>document.querySelector('[data-parking="city"] .number')?.textContent==='73');
assert.equal(await page.evaluate(()=>localStorage.getItem('basel-parking-language')),null);
assert.equal(await page.evaluate(()=>localStorage.getItem('basel-parking-v2-history')),null);
await page.click('#consent-accept');await page.selectOption('#language','de');
await page.reload();await page.waitForSelector('.card');assert.equal(await page.locator('#language').inputValue(),'de');
await page.click('#privacy-settings');await page.click('#consent-reject');
assert.equal(await page.evaluate(()=>localStorage.getItem('basel-parking-language')),null);
for(const lang of ['de','fr','en']){
 await page.selectOption('#language',lang);await page.evaluate(()=>window.scrollTo(0,0));
 assert.equal(await page.locator('html').getAttribute('lang'),lang);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 box=await page.locator('#view-results').boundingBox();assert(box.y+box.height<=667,lang+JSON.stringify(box));
 await page.screenshot({path:path.join(artifacts,`375-${lang}-simulated.png`),fullPage:true});
}
assert.deepEqual(await page.evaluate(()=>window.violations),[]);
const response=await page.goto(url+'this-page-does-not-exist');assert.equal(response.status(),404);await page.waitForSelector('h1');
await page.selectOption('#language','fr');assert((await page.locator('h1').innerText()).includes('n’existe'));
await page.goto(url+'privacy.html?lang=de');await page.waitForFunction(()=>document.documentElement.lang==='de');
assert((await page.locator('h1').innerText()).includes('Datenschutz'));
assert.deepEqual(errors,[]);
await context.close();
console.log('PASS: 375px EN/DE/FR, CTA, CSP, XSS escaping, incomplete capacity, conflicting hours, explicit closure, 2032 midnight, refresh, history expiry, offline/reconnect, consent, keyboard focus, 404 and privacy.');
if(!process.env.BASEL_SKIP_LIVE){
 const real=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}});const p=await real.newPage();const realErrors=[];p.on('pageerror',e=>realErrors.push(e.message));
 await p.goto(url);await p.waitForSelector('.card',{timeout:45000});await p.evaluate(()=>document.fonts.ready);
 assert((await p.locator('.number:not(.unknown)').count())>0);
 await p.screenshot({path:path.join(artifacts,'desktop-live.png'),fullPage:true});
 await p.setViewportSize({width:375,height:667});await p.screenshot({path:path.join(artifacts,'375-live.png'),fullPage:true});
 assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await p.click('#show-more');
 console.log('LIVE:',await p.locator('.card').count(),'car parks; Post Basel:',await p.locator('[data-parking="postbasel"] .number').innerText());
 const tomorrow=await p.locator('#day option').nth(1).getAttribute('value');await p.selectOption('#day',tomorrow);await p.selectOption('#hour','16');
 await p.waitForFunction(()=>document.querySelector('#cards').getAttribute('aria-busy')==='false',{},{timeout:45000});
 console.log('HISTORY: estimates displayed:',await p.locator('.number:not(.unknown)').count());
 assert((await p.locator('.number:not(.unknown)').count())>0);
 await p.screenshot({path:path.join(artifacts,'375-history.png'),fullPage:true});assert.deepEqual(realErrors,[]);await real.close();
}
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exit(1);});
