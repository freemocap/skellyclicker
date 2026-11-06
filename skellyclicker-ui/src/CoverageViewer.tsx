import {useId,useMemo,useState,type ReactNode} from 'react';
import {AnchoredInfo,WorkspaceTabs} from '@freemocap/ui';
import {projectedHistograms,type Direction} from './coverage-projection';
export interface CoveragePool{count:number;known_count:number;unknown_count:number;occupied_bins:number;counts:number[];samples:{image_id:string;direction:[number,number,number];bin:number}[]}
export interface Coverage{azimuth_bins:number;z_bins:number;cell_solid_angle_sr:number;center_stl_m:[number,number,number];radius_m:number;stl_scale_to_m:number;stl_url:string;frame:string;pools:Record<'current'|'eligible'|'proposed',CoveragePool>}
const identity=[1,0,0,0,1,0,0,0,1];
function AngularHistogram({counts,undefinedCount,label}:{counts:number[];undefinedCount:number;label:string}){
 const actualMax=Math.max(0,...counts),max=Math.max(1,actualMax),sum=counts.reduce((a,b)=>a+b,0),n=counts.length;
 function point(r:number,a:number){return [100+r*Math.sin(a),100-r*Math.cos(a)];}
 return <figure className="coverage-histogram"><figcaption>{label}</figcaption><svg viewBox="0 0 200 200" role="img" aria-label={`${label}: ${sum} projected, ${undefinedCount} axis-undefined`}>
  <circle cx="100" cy="100" r="88" fill="none" stroke="var(--gray-600)"/><circle cx="100" cy="100" r="28" fill="none" stroke="var(--gray-600)"/>
  {counts.map((count,i)=>{const a=-Math.PI+i*2*Math.PI/n,b=a+2*Math.PI/n-.025,r=28+60*count/max,p=point(28,a),q=point(r,a),t=point(r,b),u=point(28,b);return <path key={i} d={`M${p}L${q}A${r},${r} 0 0 1 ${t}L${u}A28,28 0 0 0 ${p}Z`} fill="var(--color-info,#50b9bf)"><title>{Math.round(a*180/Math.PI)}° to {Math.round((b+.025)*180/Math.PI)}°: {count} images</title></path>})}
  <text x="100" y="104" textAnchor="middle" fill="currentColor" fontSize="16">{actualMax}</text>
 </svg><span>{sum} projected · {undefinedCount} undefined</span></figure>;
}
export interface CoverageSphereProps{meshUrl:string;meshScale:number;meshCenter:[number,number,number];radius:number;azimuthBins:number;zBins:number;counts:number[];onViewRotation:(rotation:readonly number[])=>void}
/** APP supplies coverage semantics; rendering stays in the SDK. */
export function CoverageViewer({coverage,baseUrl,stale=false,renderSphere}:{coverage:Coverage|null;baseUrl:string;stale?:boolean;renderSphere:(props:CoverageSphereProps)=>ReactNode}){
 const panelId=useId();
 const [pool,setPool]=useState<'current'|'eligible'|'proposed'>('proposed'),[rotation,setRotation]=useState<readonly number[]>(identity);
 const data=coverage?.pools[pool];
 const hist=useMemo(()=>projectedHistograms(data?.samples.map(s=>s.direction as Direction)??[],rotation),[data,rotation]);
 return <section className="coverage-viewer" aria-label="Viewpoint coverage">
  <div className="quality-heading"><h2>Viewpoint coverage</h2><AnchoredInfo title="Viewpoint coverage" text="Camera directions are measured from the STL center in the original STL coordinate frame. Equal-area azimuth and z cells show image counts, not surface visibility or accuracy. Orbiting changes only the display. Side charts project the same directions into the current camera view: horizontal atan2(x,z), vertical atan2(y,z), preserving front and back. Each valid sample contributes once per chart; directions on a projection axis are reported as undefined. The center number is the outer-ring count. Proposed coverage belongs to the last preview; Apply changes membership separately."/></div>
  <WorkspaceTabs label="Coverage dataset" value={pool} onChange={value=>setPool(value as typeof pool)} tabs={[{id:'current',label:'Current',panelId},{id:'eligible',label:'Eligible',panelId},{id:'proposed',label:'Proposed',panelId}]}/>
  {coverage&&data?<><div className="coverage-counts" role="status">{data.count} images · {data.known_count} known · {data.unknown_count} unknown · {data.occupied_bins}/{coverage.azimuth_bins*coverage.z_bins} cells{stale?' · Preview out of date':''}</div><div className="coverage-legend"><span><i style={{background:'#40505b'}}/>0</span>{Math.max(...data.counts)>1&&<span><i style={{background:'#167e91'}}/>1</span>}{Math.max(...data.counts)>0&&<span><i style={{background:'#f3c85e'}}/>{Math.max(...data.counts)} images / cell</span>}</div>
   <div className="coverage-visuals" id={panelId} role="tabpanel" aria-label={pool}><AngularHistogram counts={hist.horizontal} undefinedCount={hist.horizontalUndefined} label="Horizontal projection"/>{renderSphere({meshUrl:new URL(coverage.stl_url,baseUrl).href,meshScale:coverage.stl_scale_to_m,meshCenter:coverage.center_stl_m,radius:coverage.radius_m,azimuthBins:coverage.azimuth_bins,zBins:coverage.z_bins,counts:data.counts,onViewRotation:setRotation})}<AngularHistogram counts={hist.vertical} undefinedCount={hist.verticalUndefined} label="Vertical projection"/></div>
  </>:<div className="coverage-empty" id={panelId} role="tabpanel" aria-label={pool}>No coverage preview</div>}
 </section>;
}
