'use strict';
const {chromium}=require('../visual/node_modules/playwright');
const fs=require('fs'),path=require('path'),os=require('os');
(async()=>{
 const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'cs-folder-browser-'));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('#workspace-menu');
  const downloading=page.waitForEvent('download');await page.click('a[href="/api/backup.zip"]');
  const download=await downloading,backup=path.join(temporary,'backup.zip');await download.saveAs(backup);
  const previous=await page.inputValue('#settings-form input[name="name"]');
  await page.fill('#settings-form input[name="name"]','After backup');await page.click('#settings-form button[type="submit"]');
  await page.waitForFunction(()=>!document.querySelector('#action-dialog').open && data.settings.profile.name==='After backup');
  await page.click('#workspace-menu');await page.setInputFiles('#restore-file',backup);await page.click('#restore-preview');
  await page.waitForFunction(()=>document.querySelector('#restore-report').textContent.includes('Dry run passed'));
  if(await page.inputValue('#settings-form input[name="name"]')!=='After backup')throw Error('Dry run altered current data');
  await page.click('#restore-apply');await page.waitForFunction(name=>!document.querySelector('#action-dialog').open && data.settings.profile.name===name,previous);
  await page.click('#workspace-menu');
  if(await page.inputValue('#settings-form input[name="name"]')!==previous)throw Error('Restore failed to recover original profile');
  await page.fill('#folder-form input[name="directory"]',path.join(temporary,'moved'));await page.click('#folder-form button');
  await page.waitForFunction(folder=>!document.querySelector('#action-dialog').open && data.settings.data_folder===folder,path.join(temporary,'moved'));
  await page.click('#workspace-menu');if(!await page.locator('code').filter({hasText:path.join(temporary,'moved')}).count())throw Error('Relocated folder missing');
  if(errors.length)throw Error(errors.join('; '));
  console.log('User menu: verified backup, unchanged dry run, restored profile, relocation: PASS');
 }finally{await browser.close();fs.rmSync(temporary,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
