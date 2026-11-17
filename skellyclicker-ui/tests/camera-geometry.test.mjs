import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
await build({entryPoints:['src/labeling/labels.ts'],bundle:true,platform:'node',format:'esm',outfile:'../.test-artifacts/labels.mjs'});
const labels=await import('../../.test-artifacts/labels.mjs');
await build({entryPoints:['src/labeling/camera-geometry.ts'],bundle:true,platform:'node',format:'esm',outfile:'../.test-artifacts/camera-geometry.mjs'});
const {cameraModelFromCalibration,projectPoint,pixelRay,pointOnRay,triangulate,epipolarPolylines}=await import('../../.test-artifacts/camera-geometry.mjs');
const {frameEvidence,emptyDocument,withPointNames,withObservation,parsePointFile,parsePointNames}=labels;

/** Camera at `center` looking at the origin, z up; world_orientation columns are the camera axes. */
function calibrationCamera(id,center,k1){
  const z=center.map(v=>-v),zn=Math.hypot(...z);z.forEach((v,i)=>z[i]=v/zn);
  let x=[z[1],-z[0],0];const xn=Math.hypot(...x);x=x.map(v=>v/xn);
  const y=[z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0]];
  const orientation=[[x[0],y[0],z[0]],[x[1],y[1],z[1]],[x[2],y[2],z[2]]];
  const translation=[0,1,2].map(row=>-(orientation[0][row]*center[0]+orientation[1][row]*center[1]+orientation[2][row]*center[2]));
  return {id,index:0,image_size:[1920,1080],world_position:center,world_orientation:orientation,
    intrinsics:{fx:1400,fy:1400,cx:960,cy:540,k1,k2:0.02,p1:0.001,p2:-0.001},extrinsics:{quaternion_wxyz:[1,0,0,0],translation}};
}
const cameras=[calibrationCamera('cam_0',[2000,0,800],-0.2),calibrationCamera('cam_1',[0,2200,900],-0.15),calibrationCamera('cam_2',[-1800,-1500,1000],0.05)].map(cameraModelFromCalibration);
const target=[120,-80,300];
const pixels=cameras.map(camera=>projectPoint(camera,target));

test('a pixel ray passes through the world point that produced the pixel, despite distortion',()=>{
  const ray=pixelRay(cameras[0],pixels[0]);
  const depth=Math.hypot(...target.map((v,i)=>v-cameras[0].center[i]));
  const hit=pointOnRay(ray,depth);
  assert.ok(Math.hypot(...hit.map((v,i)=>v-target[i]))<1e-6);
});
test('two exact views triangulate the point and reproject with no error',()=>{
  const result=triangulate([{camera:cameras[0],pixel:pixels[0]},{camera:cameras[1],pixel:pixels[1]}]);
  assert.ok(Math.hypot(...result.position.map((v,i)=>v-target[i]))<1e-6);
  assert.ok(result.meanErrorPx<1e-6);
  assert.throws(()=>triangulate([{camera:cameras[0],pixel:pixels[0]}]));
});
test('the epipolar curve of a click passes through the matching pixel in another camera',()=>{
  const lines=epipolarPolylines(cameras[1],pixelRay(cameras[0],pixels[0]),50,20000,96);
  assert.equal(lines.length,1);
  let best=Infinity;
  for(const line of lines)for(let i=1;i<line.length;i++){
    const [a,b]=[line[i-1],line[i]],vx=b[0]-a[0],vy=b[1]-a[1];
    const t=Math.max(0,Math.min(1,((pixels[1][0]-a[0])*vx+(pixels[1][1]-a[1])*vy)/(vx*vx+vy*vy)));
    best=Math.min(best,Math.hypot(a[0]+t*vx-pixels[1][0],a[1]+t*vy-pixels[1][1]));
  }
  assert.ok(best<0.5,`closest approach ${best}px`);
});
test('barrel distortion cannot fold an off-camera ray back across the principal point',()=>{
  const camera={...cameras[0],rotation:[[1,0,0],[0,1,0],[0,0,1]],translation:[0,0,0],
    imageWidth:720,imageHeight:1280,fx:873.6987475759536,fy:873.6987475759536,
    cx:359.5,cy:639.5,k1:-0.28931531670319016,k2:0,p1:0,p2:0};
  const ray={origin:[2000,0,0],direction:[0,0,1]};
  const pixels=epipolarPolylines(camera,ray,100,20000,96).flat();
  assert.ok(pixels.length>1);
  assert.ok(pixels.every(([x])=>x>camera.cx));
});
test('an inconsistent calibration entry fails instead of drawing wrong geometry',()=>{
  const broken=calibrationCamera('bad',[1000,0,0],0);broken.world_position=[0,1000,0];
  assert.throws(()=>cameraModelFromCalibration(broken),/disagrees/);
});
test('two clicks project into the third camera; projections are derived, not stored',()=>{
  let document=withPointNames(emptyDocument('rec'),['toy_top','toy_nose']);
  document=withObservation(document,'toy_nose','cam_0',7,{x_px:pixels[0][0],y_px:pixels[0][1],origin:'click'});
  document=withObservation(document,'toy_nose','cam_1',7,{x_px:pixels[1][0],y_px:pixels[1][1],origin:'click'});
  const byId=new Map(cameras.map(camera=>[camera.id,camera]));
  const nose=frameEvidence(document,7,['cam_0','cam_1','cam_2'],byId).points[1];
  assert.deepEqual(nose.views.map(view=>view.kind),['click','click','projected']);
  assert.ok(Math.hypot(nose.views[2].pixel[0]-pixels[2][0],nose.views[2].pixel[1]-pixels[2][1])<1e-6);
  assert.equal(document.observations.length,2);
  assert.equal(frameEvidence(document,8,['cam_0','cam_1','cam_2'],byId).points[1].gap,'no_clicks');
  assert.equal(frameEvidence(document,7,['cam_0','cam_1','cam_2'],new Map()).points[1].gap,'no_calibration');
});
test('point lists keep order and reject duplicates or malformed files',()=>{
  assert.deepEqual(parsePointFile('{"tracked_point_names":["toy_top","toy_tail_base","toy_nose"]}'),['toy_top','toy_tail_base','toy_nose']);
  assert.throws(()=>parsePointNames('a\nb\na'),/more than once/);
  assert.throws(()=>parsePointFile('{"names":[]}'),/tracked_point_names/);
});
