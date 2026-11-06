import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');const evidence={};
try{
 const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 const catalog=page.getByRole('region',{name:'Generated images'});await expect(catalog.locator('.sdk-image-catalog-counts')).toContainText('0 included');
 const response=page.waitForResponse(r=>r.url().endsWith('/api/labels/selection')&&r.request().method()==='POST');await catalog.getByRole('button',{name:'Include all generated images in this batch',exact:true}).click();const result=await response;expect(result.status()).toBe(200);const value=await result.json();expect(value.selected_image_ids).toHaveLength(52);evidence.includeAllRevision=value.sha256;
 await page.reload();await expect(catalog.locator('.sdk-image-catalog-counts')).toContainText('52 included',{timeout:30000});evidence.reopenedIncluded=52;
 const ids=await catalog.locator('.sdk-image-card').evaluateAll(cards=>cards.map(c=>c.dataset.imageId));expect(ids).toHaveLength(52);
 let remaining=52;
 for(const id of ids){const target=catalog.locator('.sdk-image-card').locator('xpath=self::*[@data-image-id="'+id+'"]');const pending=page.waitForResponse(r=>r.url().endsWith('/api/labels/selection')&&r.request().method()==='POST');await target.locator('.sdk-image-selection button').click();const r=await pending;expect(r.status()).toBe(200);const selected=await r.json();expect(selected.selected_image_ids).toHaveLength(--remaining);}
 await page.reload();await expect(catalog.locator('.sdk-image-catalog-counts')).toContainText('0 included',{timeout:30000});evidence.restoredOriginalExcluded=52;evidence.reopenedRestored=true;await writeFile('../.test-artifacts/include-all-native.json',JSON.stringify(evidence,null,2));console.log('PASS',evidence);
}finally{await browser.close();}
