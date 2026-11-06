import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {AnchoredInfo,ButtonSm,ControlSection,ImageCatalog,NumberField,WorkspaceTabs,ResizablePanelGroup,ResizablePanel,ResizableHandle,SphericalCoverageViewer,SettingSelectInput,type DatasetImageItem} from '@freemocap/ui';
import {CoverageViewer,type Coverage} from './CoverageViewer';
import type {Result,Selection} from './CandidateReviewPanel';

export type GenerationMode='selection'|'recording'|'model';
type Factor='iou'|'mask_fraction'|'depth_coverage'|'depth_agreement'|'in_bounds_fraction';
type Policy={selection_mode:'quality_viewpoints'|'quality_only';azimuth_bins:number;z_bins:number;top_n:number;spacing_seconds:number;require_fit_passed:boolean;min_iou:number;min_mask_fraction:number;min_depth_coverage:number;min_common_depth_px:number;max_depth_error_mm:number;min_in_bounds_fraction:number;weights:Record<Factor,number>};
type QualityRow={image_id:string;score:number|null;factors:Record<string,number|null>;eligible:boolean;reasons:string[];selected:boolean;viewpoint?:{direction:[number,number,number];bin:number}|null};
type Preview={coverage?:Coverage;label_manifest_sha256:string;selection_sha256:string|null;policy:Policy;rows:QualityRow[];image_ids:string[];counts:{current:number;eligible:number;unknown:number;chosen:number;excluded:number};preview_id:string};
type Receipt={before_count:number;after_count:number;removed_count:number;added_count:number;removed_image_ids:string[]};
const defaults:Policy={selection_mode:'quality_viewpoints',azimuth_bins:12,z_bins:6,top_n:100,spacing_seconds:0,require_fit_passed:true,min_iou:.72,min_mask_fraction:.8,min_depth_coverage:.5,min_common_depth_px:100,max_depth_error_mm:5,min_in_bounds_fraction:.9,weights:{iou:1,mask_fraction:1,depth_coverage:1,depth_agreement:1,in_bounds_fraction:1}};
const factors:{key:Factor;label:string}[]=[{key:'iou',label:'Silhouette overlap'},{key:'mask_fraction',label:'Mask fraction'},{key:'depth_coverage',label:'Depth coverage'},{key:'depth_agreement',label:'Depth agreement'},{key:'in_bounds_fraction',label:'In-bounds keypoints'}];
const thresholds:{key:keyof Omit<Policy,'weights'|'require_fit_passed'|'selection_mode'>;label:string;max?:number;step:number;help:string}[]=[
 {key:'min_iou',label:'Minimum silhouette overlap',max:1,step:.01,help:'Camera silhouette intersection over union, from 0 to 1. Higher is better.'},
 {key:'min_mask_fraction',label:'Minimum mask fraction',max:1,step:.01,help:'Camera mask fraction from the saved pose-fit metrics, from 0 to 1.'},
 {key:'min_depth_coverage',label:'Minimum depth coverage',max:1,step:.01,help:'Shared stereo depth coverage from the saved pose fit, from 0 to 1.'},
 {key:'min_common_depth_px',label:'Minimum common depth pixels',step:1,help:'Minimum number of shared valid depth pixels supporting the fit.'},
 {key:'max_depth_error_mm',label:'Maximum depth error (mm)',step:.5,help:'Maximum median absolute depth error. Smaller is better. This threshold does not change the score scale.'},
 {key:'min_in_bounds_fraction',label:'Minimum in-bounds keypoints',max:1,step:.01,help:'Minimum fraction of valid projected keypoints inside the camera image.'},
];
function invalid(p:Policy){return !Number.isInteger(p.azimuth_bins)||p.azimuth_bins<4||p.azimuth_bins>36||!Number.isInteger(p.z_bins)||p.z_bins<2||p.z_bins>18||!Number.isInteger(p.top_n)||p.top_n<1||p.top_n>100000||!Number.isInteger(p.min_common_depth_px)||p.max_depth_error_mm<=0||!Number.isFinite(p.spacing_seconds)||p.spacing_seconds<0||p.spacing_seconds>3600||thresholds.some(t=>!Number.isFinite(p[t.key])||p[t.key]<0||(t.max!==undefined&&p[t.key]>t.max))||Object.values(p.weights).some(v=>!Number.isFinite(v)||v<0)||!Object.values(p.weights).some(v=>v>0);}

type ImageDisplay={width:number;view:'crop'|'full';annotations:boolean};
const imageDisplayKey='skellyclicker.image-display.v1';
function readImageDisplay():ImageDisplay {
 const fallback:ImageDisplay={width:176,view:'crop',annotations:true};
 try {const saved=JSON.parse(localStorage.getItem(imageDisplayKey)??'null');return saved?{width:typeof saved.width==='number'&&Number.isFinite(saved.width)?Math.max(128,Math.min(480,saved.width)):176,view:saved.view==='full'?'full':'crop',annotations:typeof saved.annotations==='boolean'?saved.annotations:true}:fallback;}catch{return fallback;}
}

/** APP-owned fit policy and membership. SDK owns controls, help and bounded gallery rendering. */
export function DatasetQualityPanel({baseUrl,projectPath,result,selection,onSelection,onNavigate,mode,onMode,recording,model,onRefresh}:{baseUrl:string;projectPath?:string;result:Result|null;selection:Selection;onSelection:(value:Selection)=>void;onNavigate:(id:string)=>void;mode:GenerationMode;onMode:(value:GenerationMode)=>void;recording:ReactNode;model:ReactNode;onRefresh?:()=>void}){
 const [policy,setPolicy]=useState<Policy>(defaults),[preview,setPreview]=useState<Preview|null>(null),[checked,setChecked]=useState<string[]>([]),[receipt,setReceipt]=useState<Receipt|null>(null);
 const [busy,setBusy]=useState<'preview'|'apply'|'remove'|'restore'|null>(null),[error,setError]=useState(''),[onlyChosen,setOnlyChosen]=useState(false);
 const [display,setDisplay]=useState<ImageDisplay>(readImageDisplay);
 const [displaySaveError,setDisplaySaveError]=useState('');
 function changeDisplay(patch:Partial<ImageDisplay>){setDisplay(current=>({...current,...patch}));}
 useEffect(()=>{try{localStorage.setItem(imageDisplayKey,JSON.stringify(display));setDisplaySaveError('');}catch{setDisplaySaveError('Image display settings could not be saved.');}},[display]);
 const [undo,setUndo]=useState<{ids:string[];revision:string|null}|null>(null);
 const [baseline,setBaseline]=useState<{binding:string;ids:string[]}>({binding:'',ids:[]});
 const binding=projectPath+':'+result?.manifest_sha256;
 const request=useRef(0),admission=useRef(false);
 const currentBinding=useRef(binding);currentBinding.current=binding;
 useEffect(()=>{request.current++;admission.current=false;setBusy(null);setPreview(null);setChecked([]);setReceipt(null);setUndo(null);setError('');setBaseline({binding,ids:selection.selected_image_ids});},[binding]);
 const included=useMemo(()=>new Set(selection.selected_image_ids),[selection.selected_image_ids]);
 const chosen=useMemo(()=>new Set(preview?.image_ids??[]),[preview]);
 const scoreById=useMemo(()=>new Map(preview?.rows.map(row=>[row.image_id,row])??[]),[preview]);
 const order=useMemo(()=>preview?.rows.map(row=>row.image_id)??(baseline.binding===binding?[...new Set([...baseline.ids,...selection.selected_image_ids])]:selection.selected_image_ids),[preview,baseline,binding,selection.selected_image_ids]);
 const rowsById=useMemo(()=>new Map(result?.images.map(row=>[row.image_id,row])??[]),[result]);
 const stale=!!preview&&(preview.label_manifest_sha256!==result?.manifest_sha256||preview.selection_sha256!==selection.sha256||JSON.stringify(preview.policy)!==JSON.stringify(policy));
 const items=useMemo(()=>order.filter(id=>!onlyChosen||chosen.has(id)).flatMap(id=>{
  const row=rowsById.get(id);if(!row||!result||!projectPath)return [];
  const quality=scoreById.get(id);
  const identity={project_path:projectPath,label_manifest_sha256:result.manifest_sha256,image_id:id};
  const thumb=(annotated:boolean)=>baseUrl+'/api/labels/thumbnail?'+new URLSearchParams({...identity,crop:String(display.view==='crop'),annotated:String(annotated),max_size:'640'});
  const full=(annotated:boolean)=>baseUrl+'/api/labels/image?'+new URLSearchParams({...identity,annotated:String(annotated)});
  const scoreText=quality?.score!=null?`Score ${quality.score.toFixed(1)}`:busy==='preview'?'Scoring…':quality?'Score unknown':'Not scored';
  const scoreHelp=quality?'':busy==='preview'?'Quality scoring is running.':'Use Preview best images to compute quality scores.';
  const factorText=quality?Object.entries(quality.factors).map(([key,value])=>`${key.replaceAll('_',' ')}: ${value===null?'unknown':Number(value).toFixed(3)}`).join('; '):'';
  return [{id,groupId:row.moment_id,groupLabel:'Frame '+row.source_frame,camera:row.camera_id,label:`${row.camera_id} camera · frame ${row.source_frame}`,sourceFrameNumber:row.source_frame,
   thumbnailUrl:thumb(true),rawThumbnailUrl:thumb(false),fullImageUrl:full(true),rawFullImageUrl:full(false),removed:!included.has(id),
   facts:<div className="quality-card-facts"><strong>{scoreText}</strong>{!quality&&<AnchoredInfo title="Image score" text={scoreHelp}/>} {quality&&<><span>{chosen.has(id)?'Best N':quality.eligible?'Eligible':quality.score===null?'Unknown':'Filtered out'}</span><AnchoredInfo title={`Quality · ${row.camera_id} frame ${row.source_frame}`} text={factorText+(quality.viewpoint?`; View cell ${quality.viewpoint.bin}; STL-frame direction: ${quality.viewpoint.direction.map(v=>v.toFixed(3)).join(', ')}`:'; Viewpoint unknown')+(quality.reasons.length?'. '+quality.reasons.join('; '):'')}/></>}</div>} satisfies DatasetImageItem];
 }),[order,onlyChosen,chosen,rowsById,result,projectPath,baseUrl,included,scoreById,display.view,busy]);
 const checkedCurrent=checked.filter(id=>included.has(id));
 function change<K extends keyof Policy>(key:K,value:Policy[K]){setPolicy(p=>({...p,[key]:value}));setReceipt(null);}
 async function previewBest(){
  if(!projectPath||!result||admission.current||invalid(policy))return;
  admission.current=true;const token=++request.current,started=binding;setBusy('preview');setError('');setReceipt(null);
  try{const response=await fetch(baseUrl+'/api/labels/quality/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:projectPath,expected_label_manifest_sha256:result.manifest_sha256,expected_selection_sha256:selection.sha256,...policy})});const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));if(request.current!==token||currentBinding.current!==started)return;setPreview(value);setChecked([]);setOnlyChosen(true);
  }catch(e){if(request.current===token)setError(String(e));}finally{if(request.current===token){admission.current=false;setBusy(null);}}
 }
 async function mutate(operation:'keep'|'remove'|'restore',ids:string[]){
  if(!projectPath||!result||admission.current||!ids.length||(operation==='keep'&&(!preview||stale)))return;
  admission.current=true;const token=++request.current,started=binding;setBusy(operation==='keep'?'apply':operation);setError('');
  try{const response=await fetch(baseUrl+'/api/labels/selection/bulk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:projectPath,expected_label_manifest_sha256:result.manifest_sha256,expected_selection_sha256:selection.sha256,operation,image_ids:ids,...(operation==='keep'?{preview_id:preview!.preview_id}:{})})});const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));if(request.current!==token||currentBinding.current!==started)return;onSelection(value);setReceipt(value.receipt);setChecked([]);setUndo(operation==='restore'||!value.receipt.removed_image_ids?.length?null:{ids:value.receipt.removed_image_ids,revision:value.sha256});
  }catch(e){if(request.current===token)setError(String(e));}finally{if(request.current===token){admission.current=false;setBusy(null);}}
 }
 return <ResizablePanelGroup id="generation-columns" direction="horizontal" autoSaveId="skellyclicker-generation-columns" className="generation-split">
  <ResizablePanel id="generation-controls-panel" order={1} defaultSize={42} minSize={20} maxSize={75}><div className="generation-controls">
   <WorkspaceTabs label="Generation method" value={mode} onChange={value=>onMode(value as GenerationMode)} tabs={[{id:'selection',label:'Select best images',panelId:'generation-selection'},{id:'recording',label:'Recording images',panelId:'generation-recording'},{id:'model',label:'Find more examples',panelId:'generation-model'}]}/>
   <section id="generation-selection" role="tabpanel" aria-label="Select best images" hidden={mode!=='selection'} className="quality-selection"><ResizablePanelGroup id="generation-quality-rows" direction="vertical" autoSaveId="skellyclicker-quality-layout"><ResizablePanel id="generation-coverage-panel" order={1} defaultSize={50} minSize={20}><CoverageViewer coverage={preview?.coverage??null} baseUrl={baseUrl} stale={stale} renderSphere={props=><SphericalCoverageViewer {...props}/>}/></ResizablePanel><ResizableHandle aria-label="Resize coverage viewer"/><ResizablePanel id="generation-filter-panel" order={2} defaultSize={50} minSize={25}><div className="quality-controls">
    <div className="quality-heading"><h2>Best images</h2><AnchoredInfo title="Quality ranking" text="Preview ranks current training-set members only; previously removed images stay excluded. Apply keeps the chosen camera images and removes the rest from membership without deleting image files. Scores are heuristic pose-fit quality, not calibrated accuracy or human approval. Score = 100 × weighted mean of silhouette overlap, mask fraction, stereo depth coverage, exp(−median absolute depth error / 5 mm), and valid in-bounds keypoint fraction. Missing enabled factors are unknown and excluded. Temporal spacing is applied per camera."/></div>
    <div className="quality-mode"><label>Selection method</label><SettingSelectInput label="Selection method" value={policy.selection_mode} disabled={!!busy} options={[{value:'quality_viewpoints',label:'Quality + viewpoint diversity'},{value:'quality_only',label:'Quality only'}]} onChange={v=>change('selection_mode',v as Policy['selection_mode'])}/><AnchoredInfo title="Viewpoint-balanced selection" text="Quality thresholds determine eligible images. Viewpoint diversity then fills the least represented equal-area spherical cell, preferring the highest quality available image within each cell. Missing or invalid poses are excluded in diversity mode. The grid stays in the STL frame when you orbit the display."/></div>
    <NumberField label="Best N images" value={policy.top_n} min={1} step={1} disabled={!!busy} onChange={v=>change('top_n',Number(v))} description="Counts individual camera images, not stereo pairs. Fewer may qualify after thresholds and spacing."/>
    <NumberField label="Minimum spacing per camera (s)" value={policy.spacing_seconds} min={0} step={.1} disabled={!!busy} onChange={v=>change('spacing_seconds',Number(v))} description="Zero allows adjacent frames. Each selected image reserves a temporal neighborhood per camera. Viewpoint balancing can prefer a sparse viewing cell before a higher-scoring image in another cell."/>
    <label className="quality-toggle"><input type="checkbox" checked={policy.require_fit_passed} disabled={!!busy} onChange={e=>change('require_fit_passed',e.target.checked)}/>Require original fit gates<AnchoredInfo title="Original fit gates" text="Requires the saved pose fit to have passed its original thresholds. Turn this off to use the individual thresholds independently; relaxing a threshold below will not override the original gate."/></label>
    <ControlSection title="Quality thresholds" collapsible defaultOpen description="Defaults come from the existing pose-fit pilot gates. They are adjustable heuristics; no new pose fitting runs during preview.">{thresholds.map(t=><NumberField key={t.key} label={t.label} value={policy[t.key]} min={0} max={t.max} step={t.step} disabled={!!busy} onChange={v=>change(t.key,Number(v))} description={t.help}/>)}</ControlSection>
    <ControlSection title="Coverage grid" collapsible description="Equal-area z bands and azimuth sectors around the original STL. A finer grid requests finer viewpoint distribution; it does not create missing views."><NumberField label="Azimuth sectors" value={policy.azimuth_bins} min={4} max={36} step={1} disabled={!!busy} onChange={v=>change('azimuth_bins',Number(v))}/><NumberField label="Z bands" value={policy.z_bins} min={2} max={18} step={1} disabled={!!busy} onChange={v=>change('z_bins',Number(v))}/></ControlSection>
    <ControlSection title="Score weights" collapsible description="Zero disables a factor in the ranking. At least one weight must be positive. Thresholds still apply independently.">{factors.map(f=><NumberField key={f.key} label={`${f.label} weight`} value={policy.weights[f.key]} min={0} step={.25} disabled={!!busy} onChange={v=>change('weights',{...policy.weights,[f.key]:Number(v)})}/>)}</ControlSection>
    <div className="quality-apply-bar"><ButtonSm text={busy==='preview'?'Ranking images…':`Preview best ${policy.top_n}`} buttonType="primary accent" textColor="" disabled={!!busy||!result||!selection.selected_image_ids.length||invalid(policy)} onClick={()=>void previewBest()}/>
     {preview&&<><div role="status">{preview.counts.chosen} chosen · {preview.counts.eligible} eligible · {preview.counts.unknown} unknown</div><ButtonSm text={busy==='apply'?'Applying…':`Apply: keep ${preview.image_ids.length} images`} buttonType="primary accent" textColor="" disabled={!!busy||stale||!preview.image_ids.length} onClick={()=>void mutate('keep',preview.image_ids)}/><span>{stale?'Preview out of date':`${selection.selected_image_ids.length-preview.image_ids.length} images will be removed`}</span></>}
     {invalid(policy)&&<span role="alert">Enter valid counts and thresholds; use at least one positive weight.</span>}
    </div>
   </div></ResizablePanel></ResizablePanelGroup></section>
   <section id="generation-recording" role="tabpanel" aria-label="Recording images" hidden={mode!=='recording'} className="generation-recording-pane">{recording}</section>
   <section id="generation-model" role="tabpanel" aria-label="Find more examples" hidden={mode!=='model'}>{model}</section>
  </div></ResizablePanel>
  <ResizableHandle aria-label="Resize generation controls and image gallery"/>
  <ResizablePanel id="generation-gallery-panel" order={2} defaultSize={58} minSize={25}><div className="quality-gallery">
   <div className="quality-gallery-heading"><h2>Generated images</h2><span>{selection.selected_image_ids.length} included / {result?.images.length??0} generated</span></div>
   <div className="quality-gallery-actions">{onRefresh&&<ButtonSm text="Refresh images" buttonType="secondary" textColor="" disabled={!!busy} onClick={()=>{setPreview(null);setChecked([]);setReceipt(null);setUndo(null);setError('');setBaseline({binding,ids:[]});onRefresh();}}/>}<ButtonSm text={busy==='preview'?'Ranking images…':'Select best images'} buttonType="secondary" textColor="" disabled={!!busy} onClick={()=>{onMode('selection');if(!projectPath||!result){setError('Load generated images before selecting the best images.');return;}if(!selection.selected_image_ids.length){setError('There are no included images to rank.');return;}if(invalid(policy)){setError('Enter valid counts and thresholds; use at least one positive weight.');return;}void previewBest();}}/>{preview&&<ButtonSm text={onlyChosen?'Show all ranked':'Show best N'} buttonType="secondary" textColor="" onClick={()=>setOnlyChosen(v=>!v)}/>}<ButtonSm text={`Remove ${checkedCurrent.length} selected`} buttonType="secondary btn-danger" textColor="" disabled={!!busy||!checkedCurrent.length} onClick={()=>void mutate('remove',checkedCurrent)}/><ButtonSm text="Clear selection" buttonType="secondary" textColor="" disabled={!!busy||!checked.length} onClick={()=>setChecked([])}/>{undo&&<><ButtonSm text={busy==='restore'?'Restoring…':'Undo last selection change'} buttonType="secondary" textColor="" disabled={!!busy||undo.revision!==selection.sha256} onClick={()=>void mutate('restore',undo.ids)}/><AnchoredInfo title="Undo selection change" text="Restores only the exact images removed by your most recent successful selection change. Earlier exclusions stay excluded. Undo is unavailable if the dataset changed again; refresh and review its current membership."/>{undo.revision!==selection.sha256&&<span role="status">Undo unavailable: dataset changed</span>}</>}</div>
   <div className="quality-image-display" role="group" aria-label="Image display">
    <label className="quality-image-size">Image size <input type="range" aria-label="Image size" min={128} max={480} step={16} value={display.width} onChange={e=>changeDisplay({width:Number(e.target.value)})}/><output>{display.width} px</output></label>
    <SettingSelectInput label="Image framing" value={display.view} options={[{value:'crop',label:'Target crop'},{value:'full',label:'Full image'}]} onChange={v=>changeDisplay({view:v as ImageDisplay['view']})}/>
    <label className="quality-toggle"><input type="checkbox" checked={display.annotations} onChange={e=>changeDisplay({annotations:e.target.checked})}/>Annotations</label>
    <AnchoredInfo title="Inspect images" text="Hover over an image to hide annotations temporarily. Click an image to open the full-resolution source frame. Image size and framing affect only this gallery."/>
   </div>
   {displaySaveError&&<div role="status">{displaySaveError}</div>}
   {receipt&&<div className="quality-receipt" role="status">{receipt.before_count} → {receipt.after_count} images · Removed {receipt.removed_count}{receipt.added_count?` · Restored ${receipt.added_count}`:''}</div>}
   {error&&<div role="alert" className="quality-error">{error}</div>}
   {!result?<div role="status">No generated images</div>:<ImageCatalog mode="members" cardWidth={display.width} showAnnotations={display.annotations} items={items} selectedIds={checked} onSelectionChange={setChecked} onNavigate={onNavigate} onRemove={id=>void mutate('remove',[id])} pending={!!busy}/>}
  </div></ResizablePanel>
 </ResizablePanelGroup>;
}
