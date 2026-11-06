import {useEffect,useState} from 'react';
import {AnchoredInfo,AnnotationImage,ImagePreview,SettingSelectInput,ButtonSm} from '@freemocap/ui';
type Row={image_id:string;camera_id:string;source_frame:number;split:string};
type Result={epochs:number[];epoch:number|null;images:Row[]};
type Display={width:number;view:'crop'|'full';annotations:boolean};
const key='skellyclicker.checkpoint-image-display';
function initial():Display{const fallback:Display={width:240,view:'crop',annotations:true};try{const saved=JSON.parse(localStorage.getItem(key)??'null');return saved?{width:typeof saved.width==='number'&&Number.isFinite(saved.width)?Math.max(128,Math.min(480,saved.width)):240,view:saved.view==='full'?'full':'crop',annotations:typeof saved.annotations==='boolean'?saved.annotations:true}:fallback;}catch{return fallback;}}
export function CheckpointImages({baseUrl,projectPath,runId,latestStep=0,active=false}:{baseUrl:string;projectPath?:string;runId:string|null;latestStep?:number;active?:boolean}){
 const [selected,setSelected]=useState<number|null>(null),[result,setResult]=useState<Result|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[display,setDisplay]=useState(initial),[opened,setOpened]=useState<Row|null>(null);
 useEffect(()=>{setSelected(null);setResult(null);setOpened(null);},[runId,projectPath]);
 useEffect(()=>{try{localStorage.setItem(key,JSON.stringify(display));}catch{setError('Image display settings could not be saved.');}},[display]);
 useEffect(()=>{
  if(!projectPath||!runId)return;const abort=new AbortController();setLoading(true);setError('');
  const query=new URLSearchParams({project_path:projectPath,...(selected===null?{}:{epoch:String(selected)})});
  void fetch(`${baseUrl}/api/training/runs/${runId}/preview-images?${query}`,{signal:abort.signal}).then(async response=>{const value=await response.json();if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:'Checkpoint images could not be loaded.');if(!Array.isArray(value.epochs)||!Array.isArray(value.images))throw Error('Checkpoint image API unavailable. Restart the app after the backend update.');if(!abort.signal.aborted)setResult(value);}).catch(e=>{if(!abort.signal.aborted)setError(String(e));}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});return()=>abort.abort();
 },[baseUrl,projectPath,runId,selected,latestStep,active]);
 const epoch=result?.epoch??null,epochs=result?.epochs??[];
 const url=(row:Row,annotated:boolean,full=false)=>`${baseUrl}/api/training/runs/${runId}/preview-image?`+new URLSearchParams({project_path:projectPath??'',epoch:String(epoch),image_id:row.image_id,crop:String(!full&&display.view==='crop'),annotated:String(annotated),max_size:full?'0':'640'});
 const label=(row:Row)=>`${row.split} · ${row.camera_id} · frame ${row.source_frame} · epoch ${epoch}`;
 return <section className="checkpoint-browser" aria-label="Checkpoint images">
  <header><h2>Checkpoint images</h2><AnchoredInfo title="Checkpoint images" text="Magenta circles are frozen training labels; cyan crosses are this epoch’s predictions. The slider visits saved evaluation epochs only. Hover hides annotations; click opens the full image. Browsing does not change the next run’s starting model."/></header>
  <div className="checkpoint-epoch-controls"><label>Epoch <strong>{epoch??'—'}</strong><input aria-label="Checkpoint epoch" type="range" min={0} max={Math.max(0,epochs.length-1)} step={1} value={Math.max(0,epochs.indexOf(epoch??-1))} disabled={!epochs.length} onChange={e=>{setOpened(null);setSelected(epochs[Number(e.target.value)]);}} aria-valuetext={epoch===null?'No saved epochs':`Epoch ${epoch}`}/></label><ButtonSm text={selected===null?'Following latest':'Follow latest'} buttonType="secondary" ariaPressed={selected===null} onClick={()=>{setOpened(null);setSelected(null);}}/><span>{epochs.length} saved epochs</span></div>
  <div className="checkpoint-display-controls"><label>Image size <input aria-label="Checkpoint image size" type="range" min={128} max={480} step={16} value={display.width} onChange={e=>setDisplay({...display,width:Number(e.target.value)})}/><output>{display.width} px</output></label><SettingSelectInput label="Checkpoint image framing" value={display.view} options={[{value:'crop',label:'Target crop'},{value:'full',label:'Full image'}]} onChange={view=>setDisplay({...display,view:view as Display['view']})}/><label><input type="checkbox" checked={display.annotations} onChange={e=>setDisplay({...display,annotations:e.target.checked})}/>Annotations</label></div>
  {epoch!==null&&<a href={`${baseUrl}/api/training/runs/${runId}/artifact?`+new URLSearchParams({project_path:projectPath??'',path:`previews/epoch-${String(epoch).padStart(6,'0')}/predictions.json`})} target="_blank" rel="noreferrer">Epoch {epoch} predictions (JSON)</a>}
  {error&&<p role="alert">{error}</p>}{loading&&<p role="status">Loading checkpoint images…</p>}
  {!error&&!loading&&!result?.images.length&&<p role="status">{!runId?'Select a training run.':active?'Awaiting the first saved evaluation epoch…':'No saved checkpoint images for this run.'}</p>}
  <div className="checkpoint-image-grid" style={{gridTemplateColumns:`repeat(auto-fit,minmax(min(100%,${display.width}px),1fr))`}} aria-busy={loading}>
   {!loading&&!error&&result?.images.map(row=><figure key={row.image_id}><button type="button" className="checkpoint-image-open" aria-label={`Open ${label(row)}`} onClick={()=>setOpened(row)}><AnnotationImage annotatedUrl={url(row,true)} rawUrl={url(row,false)} label={label(row)} showAnnotations={display.annotations}/></button><figcaption>{row.split} · {row.camera_id} · frame {row.source_frame}</figcaption></figure>)}
  </div>
  {opened&&<ImagePreview key={opened.image_id+':'+epoch} label={label(opened)} annotatedUrl={url(opened,true,true)} rawUrl={url(opened,false,true)} showAnnotations={display.annotations} onClose={()=>setOpened(null)}/>}
 </section>;
}
