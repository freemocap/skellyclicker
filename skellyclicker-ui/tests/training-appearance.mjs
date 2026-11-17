import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {chromium,expect} from '@playwright/test';
const [ui,backend,recording]=process.argv.slice(2);
const output=resolve('.test-artifacts/calibrated-viewport');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:process.env.CHROMIUM_CHANNEL||'msedge',headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  // Restore a recording independently of the user's active desktop session.
  await page.addInitScript(({backend,recording})=>{
    window.isTauri=true;
    window.__TAURI_INTERNALS__={invoke:async command=>{if(command==='backend_url')return backend;throw Error(command);}};
    localStorage.setItem('skellyclicker.manualRecording',recording);
  },{backend,recording});
  await page.goto(ui);
  await expect(page.locator('.clicker-header')).toContainText('freemocap_test_data');
  await page.getByRole('tab',{name:'Training',exact:true}).click();
  const panel=page.locator('.keypoint-training');
  await expect(panel.getByRole('heading',{name:'Training settings'})).toBeVisible();
  await expect(panel.getByRole('heading',{name:'Training runs'})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Start training'})).toBeEnabled();
  await expect(panel.getByLabel('Starting model').locator('option:checked')).toHaveText('New model · ResNet-50 GN (ImageNet-1K)');
  await expect(panel.getByLabel('Python executable for DeepLabCut')).toHaveCount(0);
  async function checkContrast(locator){
    const ratio=await locator.evaluate(el=>{
      const luminance=color=>{
        const rgb=color.match(/[\d.]+/g).slice(0,3).map(v=>Number(v)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
        return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
      };
      let surface=el;
      while(surface&&getComputedStyle(surface).backgroundColor==='rgba(0, 0, 0, 0)')surface=surface.parentElement;
      const values=[luminance(getComputedStyle(el).color),luminance(getComputedStyle(surface).backgroundColor)].sort((a,b)=>a-b);
      return (values[1]+.05)/(values[0]+.05);
    });
    assert.ok(ratio>=4.5,'Insufficient contrast '+ratio);
    return ratio.toFixed(1);
  }
  for(const selector of ['h2','h3','fieldset > label','input[type=number]','select','.keypoint-counts','.keypoint-history strong','.keypoint-actions .text']){
    console.log(selector,await checkContrast(panel.locator(selector).first()));
  }
  await page.screenshot({path:resolve(output,'training.png')});
  await page.setViewportSize({width:850,height:720});
  await expect(panel.getByRole('button',{name:'Start training'})).toBeVisible();
  assert.ok(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth));
}finally{await browser.close();}
