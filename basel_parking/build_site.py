#!/usr/bin/env python3
"""Build static Netlify files and an autonomous HTML copy. No secrets required."""
import base64
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'basel-parking-netlify'

def build_site():
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    origin = config['site_url'].rstrip('/')
    if not re.fullmatch(r'https://[a-zA-Z0-9.-]+', origin):
        raise ValueError('site_url must be an HTTPS origin')
    OUT.mkdir(exist_ok=True)
    (OUT/'assets').mkdir(exist_ok=True)
    for name in ['styles.css','app.js','i18n.js','pages.js']:
        shutil.copyfile(ROOT/name,OUT/'assets'/name)
    for name in ['atkinson-400.woff2','atkinson-700.woff2','FONT-LICENSE.txt']:
        shutil.copyfile(ROOT/'assets'/name,OUT/'assets'/name)
    font_path = ROOT/'assets/atkinson-700.ttf'
    icon = Image.new('RGB',(512,512),'#193f35');d=ImageDraw.Draw(icon)
    font=ImageFont.truetype(str(font_path),390);box=d.textbbox((0,0),'P',font=font)
    d.text(((512-(box[2]-box[0]))/2,(512-(box[3]-box[1]))/2-box[1]),'P',font=font,fill='white')
    icon.save(OUT/'favicon.ico',sizes=[(16,16),(32,32),(48,48)])
    icon.resize((180,180)).save(OUT/'apple-touch-icon.png',optimize=True)
    icon.resize((192,192)).save(OUT/'assets/icon-192.png',optimize=True)
    icon.save(OUT/'assets/icon-512.png',optimize=True)
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="4" fill="#193f35"/><path fill="white" d="M19 13h15c11 0 17 6 17 15s-6 15-17 15h-6v10h-9zm9 8v14h6c5 0 8-2 8-7s-3-7-8-7z"/></svg>'
    (OUT/'favicon.svg').write_text(svg, encoding='utf-8')
    og=Image.new('RGB',(1200,630),'#f7f7f2');draw=ImageDraw.Draw(og)
    og.paste(icon.resize((80,80)),(70,60))
    bold=lambda n:ImageFont.truetype(str(font_path),n)
    regular=lambda n:ImageFont.truetype(str(ROOT/'assets/atkinson-400.ttf'),n)
    draw.text((174,79),'Basel Parking',font=bold(36),fill='#193f35')
    draw.text((70,223),'Parking spaces in Basel.',font=bold(70),fill='#193f35')
    draw.text((74,332),'Official availability now.',font=regular(40),fill='#53665d')
    draw.text((74,390),'Historical estimates for later.',font=regular(40),fill='#53665d')
    draw.text((74,531),'English / Deutsch / Français',font=regular(29),fill='#53665d')
    og.save(OUT/'assets/share.png',optimize=True)
    manifest={'name':'Basel Parking','short_name':'Basel Parking','start_url':'/','display':'standalone','background_color':'#f7f7f2','theme_color':'#193f35','icons':[{'src':f'/assets/icon-{n}.png','sizes':f'{n}x{n}','type':'image/png'} for n in [192,512]]}
    (OUT/'site.webmanifest').write_text(json.dumps(manifest), encoding='utf-8')
    def meta(title,description,path,notfound=False):
        esc=html.escape
        return f'''<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/favicon.ico"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
{('<meta name="robots" content="noindex">' if notfound else '<link rel="canonical" href="'+origin+path+'">')}
<meta property="og:type" content="website"><meta property="og:site_name" content="Basel Parking">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{origin}{path}"><meta property="og:image" content="{origin}/assets/share.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Basel Parking: official availability now and historical estimates for later.">
<meta name="twitter:card" content="summary_large_image">'''
    config_json=json.dumps(config,ensure_ascii=False).replace('</','<\\/')
    styles=(ROOT/'styles.css').read_text(encoding='utf-8');i18n=(ROOT/'i18n.js').read_text(encoding='utf-8');app=(ROOT/'app.js').read_text(encoding='utf-8')
    publisher=config.get('publisher',{})
    has_legal=all(publisher.get(k,'').strip() for k in ['name','email','address'])
    if has_legal and not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+',publisher['email']):raise ValueError('Invalid publisher email')
    replacements={'__CONFIG__':config_json,'__STYLES__':styles,'__I18N__':i18n,'__APP__':app,
      '__META__':meta('Basel Parking | Live spaces and arrival estimates','Current parking availability in Basel and historical estimates for your arrival.','/'),
      '__LEGAL_LINK__':'<a href="/legal.html">Legal / Impressum / Mentions légales</a>' if has_legal else ''}
    content=(ROOT/'dashboard.full.template.html').read_text(encoding='utf-8')
    for token,value in replacements.items():content=content.replace(token,value)
    deployed=content.replace('<style>'+styles+'</style>','<link rel="stylesheet" href="/assets/styles.css">').replace('<script>'+i18n+'</script>','<script src="/assets/i18n.js" defer></script>').replace('<script>'+app+'</script>','<script src="/assets/app.js" defer></script>')
    (OUT/'index.html').write_text(deployed, encoding='utf-8')
    # The optional autonomous copy embeds fonts, scripts and CSS.
    standalone=content
    for weight in [400,700]:
        encoded=base64.b64encode((ROOT/f'assets/atkinson-{weight}.woff2').read_bytes()).decode()
        standalone=standalone.replace(f'/assets/atkinson-{weight}.woff2','data:font/woff2;base64,'+encoded)
    standalone=standalone.replace('href="/favicon.svg"','href="data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()+'"')
    standalone=re.sub(r'<link rel="(?:alternate icon|apple-touch-icon|manifest)"[^>]*>','',standalone)
    standalone=standalone.replace('href="privacy.html"',f'href="{origin}/privacy.html"')
    standalone=standalone.replace('href="data-study.html"',f'href="{origin}/data-study.html"')
    standalone=standalone.replace("'privacy.html?lang='",repr(origin+'/privacy.html?lang='))
    (ROOT/'dashboard.html').write_text(standalone, encoding='utf-8')
    (ROOT.parent/'basel-parking-v4.html').write_text(standalone, encoding='utf-8')
    pages={
      'privacy.html':('privacy','Privacy and data | Basel Parking','How Basel Parking uses local storage and public parking data.',
      '<h1 data-i18n="privacyHeading">Privacy and data</h1><p data-i18n="privacyIntro">Basel Parking displays public parking information. No accounts or reservations.</p>'+''.join(f'<section><h2 data-i18n="{k}Heading">{heading}</h2><p data-i18n="{k}Text">{text}</p></section>' for k,heading,text in [
        ('storage','Storage on this device','Your storage choice is kept locally. Accepting also saves your language and public historical readings. You can refuse or change your choice on the home page.'),
        ('requests','Services contacted','Netlify hosts this site. Your browser contacts data.bs.ch for parking data. These services receive your connection information, including your IP address. No analytics script or advertising is included.'),
        ('links','External links','Directions opens Google Maps. Official details opens the Basel parking guidance website. Their own privacy policies apply.'),
        ('limits','Data limitations','Data can arrive late. Estimates are not reservations. Regular hours and height limits are maintained manually.')])),
      '404.html':('404','Page not found | Basel Parking','This address does not exist. Return to Basel Parking to check free spaces.',
        '<p class="error-code">404</p><h1 data-i18n="notFoundHeading">This page does not exist.</h1><p data-i18n="notFoundText">Check the address or return to the parking search.</p>')}
    for filename,(page,title,description,body) in pages.items():
        page_html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#193f35"><title>{title}</title><meta name="description" content="{description}">{meta(title,description,'/'+filename,page=='404')}<link rel="stylesheet" href="/assets/styles.css"><script src="/assets/i18n.js" defer></script><script src="/assets/pages.js" defer></script></head><body data-page="{page}"><header class="masthead"><a class="brand" href="/" data-home><span class="brand-icon" aria-hidden="true">P</span> Basel Parking</a><div class="header-controls"><label class="language-label" for="language" data-i18n="languageLabel">Language</label><select id="language" aria-label="Language"><option value="en">English</option><option value="de">Deutsch</option><option value="fr">Français</option></select></div></header><main class="text-page">{body}<a class="primary" href="/" data-home data-i18n="backHome">Back to parking spaces</a></main></body></html>'''
        (OUT/filename).write_text(page_html, encoding='utf-8')
    study = ROOT.parent/'analysis'/'report.html'
    urls=['/','/privacy.html']
    if study.exists():
        shutil.copyfile(study, OUT/'data-study.html')
        urls.append('/data-study.html')
    if has_legal:
        title='Legal / Impressum / Mentions légales | Basel Parking'
        body=''.join('<p>'+html.escape(publisher[k])+'</p>' for k in ['name','address','email'])
        (OUT/'legal.html').write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><meta name="description" content="Publisher and contact for Basel Parking.">{meta(title,"Publisher and contact for Basel Parking.","/legal.html")}<link rel="stylesheet" href="/assets/styles.css"></head><body><main class="text-page"><h1>Legal / Impressum / Mentions légales</h1>{body}<p>Hosting / Hébergement: Netlify, Inc. <a href="https://www.netlify.com/privacy/">Netlify privacy policy</a></p><a href="/">Basel Parking</a></main></body></html>', encoding='utf-8')
        urls.append('/legal.html')
    elif (OUT/'legal.html').exists():
        (OUT/'legal.html').unlink()
    (OUT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+origin+'/sitemap.xml\n', encoding='utf-8')
    (OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+origin+url+'</loc></url>' for url in urls)+'</urlset>\n', encoding='utf-8')
    config_hash=base64.b64encode(hashlib.sha256(config_json.encode()).digest()).decode()
    csp=f"default-src 'none'; script-src 'self' 'sha256-{config_hash}'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src https://data.bs.ch; manifest-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'; upgrade-insecure-requests"
    headers={'Content-Security-Policy':csp,'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=()','Strict-Transport-Security':'max-age=31536000; includeSubDomains','Cache-Control':'public, max-age=0, must-revalidate'}
    (OUT/'_headers').write_text('/*\n'+''.join('  '+k+': '+v+'\n' for k,v in headers.items()), encoding='utf-8')
    (ROOT/'tests/headers.json').write_text(json.dumps(headers,indent=2), encoding='utf-8')
    print('Built Netlify folder and standalone HTML. Publisher details complete:',has_legal)

if __name__=='__main__':build_site()
