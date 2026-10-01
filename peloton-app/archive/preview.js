// Local preview harness: renders app.html in Chromium, once without the Omni runtime (sample data)
// and once with a stub `omni` object that feeds rows in the wired-query shape, then screenshots both.
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'app.html'), 'utf8');
const stub = `
<script>
(function(){
  const rows = { peloton_products: [], peloton_monthly_sales: [], peloton_engagement: [] };
  // products rows keyed like a SQL tab would return ("peloton_products.product")
  rows.peloton_products = [{'peloton_products.product':'Bike','peloton_products.family':'Bike','peloton_products.modality':'Cycling','peloton_products.list_price_usd':'1445','peloton_products.membership_usd_per_month':'44','peloton_products.footprint':'4 ft x 2 ft','peloton_products.weight_lb':'135','peloton_products.max_user_weight_lb':'297','peloton_products.screen_inches':'21.5','peloton_products.screen_movement':'Tilt','peloton_products.signature_feature':'Manual resistance knob','peloton_products.best_for':'Entry-level studio cycling at home','peloton_products.launch_year':'2014','peloton_products.training_focus':'Cardio'},
    {'peloton_products.product':'Row','peloton_products.family':'Row','peloton_products.modality':'Rowing','peloton_products.list_price_usd':'2995','peloton_products.membership_usd_per_month':'44','peloton_products.footprint':'8 ft x 2 ft','peloton_products.weight_lb':'156','peloton_products.max_user_weight_lb':'300','peloton_products.screen_inches':'23.8','peloton_products.screen_movement':'Swivel + tilt','peloton_products.signature_feature':'Form Assist','peloton_products.best_for':'Full-body low-impact cardio','peloton_products.launch_year':'2022','peloton_products.training_focus':'Cardio + Strength'}];
  rows.peloton_engagement = [{'peloton_engagement.product':'Bike','peloton_engagement.avg_workouts_per_week':'4.6','peloton_engagement.avg_minutes_per_workout':'31','peloton_engagement.retention_12m_pct':'92','peloton_engagement.nps':'71','peloton_engagement.cross_training_pct':'38'},{'peloton_engagement.product':'Row','peloton_engagement.avg_workouts_per_week':'4.4','peloton_engagement.avg_minutes_per_workout':'28','peloton_engagement.retention_12m_pct':'91','peloton_engagement.nps':'74','peloton_engagement.cross_training_pct':'52'}];
  for (const p of ['Bike','Row']) for (let i=0;i<24;i++) for (const r of ['United States','UK & Ireland']) rows.peloton_monthly_sales.push({'peloton_monthly_sales.product':p,'peloton_monthly_sales.month':new Date(Date.UTC(2026,9-i,1)).toISOString().slice(0,10),'peloton_monthly_sales.region':r,'peloton_monthly_sales.units_sold':String(1000+i*30+(p==='Row'?200:0)),'peloton_monthly_sales.hardware_revenue_usd':String((1000+i*30)*1445),'peloton_monthly_sales.new_memberships':String(900+i*25),'peloton_monthly_sales.returns':'30'});
  const listeners = {};
  window.omni = {
    ready: Promise.resolve(),
    runQueries(names){ window.__ran = names; },
    query(name){ if(!rows[name]) throw new Error('No query named '+name);
      return { data: null, onData(cb){ setTimeout(()=>cb({status:'running'}),50); setTimeout(()=>cb({status:'complete', rows: rows[name]}),300); } }; }
  };
})();
</script>`;
(async () => {
  const browser = await chromium.launch();
  const out = path.join(__dirname);
  for (const [label, content, dark] of [['sample-light', html, false], ['sample-dark', html, true], ['live-stub', html.replace('<script>', stub + '\n<script>'), false]]) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: dark ? 'dark' : 'light' });
    const page = await ctx.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.setContent(content, { waitUntil: 'load' });
    await page.waitForTimeout(800);
    const pill = await page.textContent('#data-pill-text');
    const chips = await page.$$eval('.chip', els => els.length);
    const cards = await page.$$eval('.card', els => els.length);
    const specRows = await page.$$eval('#spec-table tbody tr', els => els.length);
    const paths = await page.$$eval('#trend path', els => els.length);
    // interact: toggle Tread+ chip, switch metric, hover chart, run fit finder
    await page.click('.chip[data-p="Guide"]').catch(()=>{});
    await page.click('#metric-seg button[data-m="hardware_revenue_usd"]');
    const box = await page.$('#trend-hit').then(h => h && h.boundingBox());
    if (box) await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5);
    await page.click('#q-goal .opt[data-v="Strength"]');
    await page.waitForTimeout(200);
    const tip = await page.textContent('#trend-tip');
    const reco = await page.$$eval('#reco .rec .nm', els => els.map(e => e.textContent.trim()));
    await page.screenshot({ path: path.join(out, `shot-${label}.png`), fullPage: true });
    console.log(JSON.stringify({ label, pill, chips, cards, specRows, paths, tip: (tip||'').slice(0,80), reco, ran: await page.evaluate(() => window.__ran || null), errors }, null, 0));
    await ctx.close();
  }
  // mobile width check
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage(); await page.setContent(html, { waitUntil: 'load' }); await page.waitForTimeout(500);
  const sw = await page.evaluate(() => document.documentElement.scrollWidth); console.log('mobile scrollWidth', sw);
  await page.screenshot({ path: path.join(out, 'shot-mobile.png'), fullPage: true });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
