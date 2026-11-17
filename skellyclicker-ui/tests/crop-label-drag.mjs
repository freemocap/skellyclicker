import {build} from 'esbuild';
import {chromium, expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

// Exercise browser hit testing with the SDK's crop positioning and drag surface.
const {outputFiles} = await build({stdin:{resolveDir:process.cwd(),loader:'tsx',contents:`
import React from 'react';
import {createRoot} from 'react-dom/client';
import {LabelImageOverlay} from './src/labeling/LabelImageOverlay';
const frame={sourceFrameNumber:121,recording:{id:'test'},presentationEpoch:'test'};
const context={videoId:'Cam1',filename:'Cam1.mp4',imageWidth:360,imageHeight:640,pause(){},getPresentedFrame:()=>frame};
const view={cameraId:'Cam1',pixel:[360,640],kind:'click',errorPx:6};
const point={point:'nose',index:0,color:'yellow',views:[view],rays:new Map()};
const root=createRoot(document.getElementById('viewer-view'));
window.renderLayers=(layers)=>root.render(<><div className="recording-layers"/><div className="video-feed-tile">
  <div style={{position:'relative',height:100}}><LabelImageOverlay context={context} sourceSize={[720,1280]}
    cameras={new Map()} cameraColors={new Map()} activePoint="nose" evidence={{points:[point]}}
    crop={{x:168,y:308,width:24,height:24}} layers={layers} onRegisterView={()=>{}}
    onPlace={(camera,pixel,frame,name)=>window.saved={camera,pixel,frame:frame.sourceFrameNumber,name}}/></div>
  <figure className="playback-target-closeup" style={{width:240,height:240}}><canvas/>
    <button className="playback-closeup-drag" title="Drag image to move"/></figure></div></>);
window.renderLayers({labels:true,guides:true,errors:true});
`},bundle:true,write:false,jsx:'automatic'});

const browser=await chromium.launch({channel:'msedge',headless:true});
try {
    const page=await browser.newPage();
    await page.setContent('<section id="viewer-view"></section>');
    for(const path of ['node_modules/@freemocap/ui/src/styles/playback.css','src/shell.css']){
        await page.addStyleTag({content:await readFile(path,'utf8')});
    }
    await page.addScriptTag({content:outputFiles[0].text});
    const crop=page.locator('.label-crop-overlay');
    await expect(crop.locator('circle')).toBeVisible();
    await expect(page.locator('.playback-closeup-drag')).toBeHidden();
    const box=await crop.boundingBox();
    const x=box.x+box.width/2,y=box.y+box.height/2;
    await page.mouse.move(x,y);
    await page.mouse.down();
    await page.mouse.move(x+box.width/4,y-box.height/4,{steps:4});
    await page.mouse.up();
    const saved=await page.evaluate(()=>window.saved);
    expect(saved.name).toBe('nose');
    expect(saved.frame).toBe(121);
    expect(saved.pixel[0]).toBeCloseTo(372,0);
    expect(saved.pixel[1]).toBeCloseTo(628,0);
    expect(await crop.boundingBox()).toEqual(box);
    await page.evaluate(()=>window.renderLayers({labels:false,guides:true,errors:true}));
    await expect(crop.locator('circle')).toHaveCount(0);
    await expect(crop).toContainText('6.0 px reprojection');
    await page.evaluate(()=>window.renderLayers({labels:true,guides:true,errors:false}));
    await expect(crop.locator('circle')).toBeVisible();
    await expect(crop).not.toContainText('reprojection');
    console.log('PASS crop marker drag, fixed crop position and independent label/error visibility');
} finally { await browser.close(); }
