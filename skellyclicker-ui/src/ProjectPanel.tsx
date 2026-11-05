import {useEffect, useRef, useState} from 'react';
import {RecordingBrowser, type BrowserEntry} from '@freemocap/ui';

export interface ProjectView {
  root: string; manifest_path: string;
  project: {project_id: string; uuid: string; created_at?: string};
  recordings: {recording_id: string; source: {path: string; bytes?: number}; calibration_state: string; streams: {camera_id: string}[]}[];
  targets: {object_id: string; authored_units: string}[];
  issues: string[]; sample_state: string; playback: {id:string;displayName?:string;pointCloudManifest?:string|null}|null;
}
interface RecentProject {id: string; name: string; path: string; timestamp?: number; recordings: number; targets: number}
const recentKey='skellyclicker.recentProjects';
const sourceRoot='C:/Users/jonma/AppData/Local/ZEDBenchy';
function loadRecent(): RecentProject[] {
  try {
    const value=JSON.parse(localStorage.getItem(recentKey) ?? '[]');
    return Array.isArray(value) ? value.filter((v):v is RecentProject=>v && typeof v.id==='string' && typeof v.name==='string' && typeof v.path==='string' && typeof v.recordings==='number' && typeof v.targets==='number').slice(0,30) : [];
  } catch {return [];}
}
export function ProjectPanel({baseUrl,project,onProject}:{baseUrl:string;project:ProjectView|null;onProject:(p:ProjectView)=>void}) {
  const [recent,setRecent]=useState(loadRecent);
  const [mode,setMode]=useState<'open'|'create'|null>(null);
  const dialog=useRef<HTMLDialogElement>(null);
  const [path,setPath]=useState(()=>localStorage.getItem('skellyclicker.projectPath') ?? '');
  const [busy,setBusy]=useState(false);
  const [busyId,setBusyId]=useState<string|null>(null);
  const [error,setError]=useState('');
  const [recordingId,setRecordingId]=useState<string|null>(null);
  const [svo,setSvo]=useState(sourceRoot+'/recordings/benchy-20261104-232220-208509/stereo.svo2');
  const [calibration,setCalibration]=useState(sourceRoot+'/recordings/benchy-20261104-232220-208509/SN23364999.conf');
  const [stl,setStl]=useState(sourceRoot+'/3DBenchy.stl');
  const [objectId,setObjectId]=useState('benchy');
  const [units,setUnits]=useState('mm');
  useEffect(()=>{
    if(!project)return;
    const timestamp=project.project.created_at ? Date.parse(project.project.created_at) : undefined;
    const entry:RecentProject={id:project.project.uuid,name:project.project.project_id,path:project.manifest_path,recordings:project.recordings.length,targets:project.targets.length,...(timestamp!==undefined&&Number.isFinite(timestamp)?{timestamp}:{})};
    setRecent(previous=>{const next=[entry,...previous.filter(p=>p.id!==entry.id)].slice(0,30);localStorage.setItem(recentKey,JSON.stringify(next));return next;});
    setRecordingId(project.recordings[0]?.recording_id ?? null);
  },[project]);
  useEffect(()=>{if(mode&&!dialog.current?.open)dialog.current?.showModal();else if(!mode&&dialog.current?.open)dialog.current.close();},[mode]);
  function show(next:'open'|'create') {
    setError('');setPath(next==='open' ? project?.manifest_path ?? localStorage.getItem('skellyclicker.projectPath') ?? '' : project ? project.root.replace(/[^/\\]+$/,'new-project') : '');setMode(next);
  }
  async function submit(action:'open'|'create',projectPath:string,id:string|null=null) {
    if(busy)return;setBusy(true);setBusyId(id);setError('');
    try {
      const body=action==='create'?{project_path:projectPath,source_svo:svo,calibration_source:calibration,source_stl:stl,object_id:objectId,authored_units:units}:{project_path:projectPath};
      const response=await fetch(baseUrl+'/api/projects/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail));
      onProject(result);localStorage.setItem('skellyclicker.projectPath',result.manifest_path);setPath(result.manifest_path);setMode(null);
    }catch(e){setError(String(e));}finally{setBusy(false);setBusyId(null);}
  }
  const projects:BrowserEntry[]=recent.map(item=>({id:item.id,name:item.name,path:item.path,timestamp:item.timestamp,subtitle:`${item.recordings} recording${item.recordings===1?'':'s'} · ${item.targets} reference${item.targets===1?'':'s'}`,status:item.id===project?.project.uuid?{label:'Open',tone:'success'}:undefined,details:[{label:'Manifest',value:item.path}]}));
  const recordings:BrowserEntry[]=(project?.recordings ?? []).map(recording=>({id:recording.recording_id,name:recording.recording_id,path:recording.source.path,cameraCount:recording.streams.length,sizeBytes:recording.source.bytes,subtitle:recording.streams.map(stream=>stream.camera_id).join(' + '),status:{label:'Linked original',tone:'neutral'},details:[{label:'Original',value:recording.source.path},{label:'Calibration',value:project?.playback?'Fresh replay calibration loaded':recording.calibration_state==='ready'?'Ready':'Awaiting fresh replay'},{label:'Reference',value:project!.targets.map(t=>`${t.object_id} (${t.authored_units})`).join(', ')}]}));
  return <div className="project-browser-stack">
    <RecordingBrowser title="Projects" entries={projects} selectedId={project?.project.uuid} busyId={busyId} loading={busy} error={!mode?error:null} onSelect={id=>{const entry=recent.find(p=>p.id===id);if(entry)void submit('open',entry.path,id);}} onBrowse={()=>show('open')} browseLabel="Open project" onCreate={()=>show('create')} createLabel="New project" emptyMessage="Open a project or create a new one to begin."/>
    {project&&<div className="project-child-recordings"><RecordingBrowser title="Recordings" entries={recordings} selectedId={recordingId} onSelect={setRecordingId} error={project.issues.join('\n')||null} emptyMessage="No recordings in this project."/></div>}
    <dialog ref={dialog} className="project-dialog" aria-labelledby="project-dialog-title" onCancel={event=>{event.preventDefault();if(!busy)setMode(null);}}>
      <form onSubmit={event=>{event.preventDefault();if(mode)void submit(mode,path);}}>
        <header><h2 id="project-dialog-title">{mode==='create'?'New project':'Open project'}</h2><button type="button" aria-label="Close project dialog" disabled={busy} onClick={()=>setMode(null)}>×</button></header>
        <div className="project-dialog-fields">
          <p>{mode==='create'?'Choose a new project folder. Original media stays linked; the STL is copied into the project.':'Choose a project folder or its named project manifest.'}</p>
          <label>{mode==='create'?'New project folder':'Project folder or manifest'}<input aria-label="Project path" autoFocus required value={path} onChange={event=>setPath(event.target.value)} disabled={busy}/></label>
          {mode==='create'&&<>
            <label>Original stereo SVO<input required value={svo} onChange={event=>setSvo(event.target.value)} disabled={busy}/></label>
            <label>Camera calibration source<input required value={calibration} onChange={event=>setCalibration(event.target.value)} disabled={busy}/></label>
            <label>Reference STL<input required value={stl} onChange={event=>setStl(event.target.value)} disabled={busy}/></label>
            <div className="project-dialog-pair"><label>Object ID<input required pattern="[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}" value={objectId} onChange={event=>setObjectId(event.target.value)} disabled={busy}/></label><label>STL units<select value={units} onChange={event=>setUnits(event.target.value)} disabled={busy}><option value="mm">Millimetres</option><option value="m">Metres</option></select></label></div>
          </>}
          {error&&<p role="alert">{error}</p>}
        </div>
        <footer><button type="button" disabled={busy} onClick={()=>setMode(null)}>Cancel</button><button type="submit" className="project-dialog-submit" disabled={busy}>{busy?'Verifying files…':mode==='create'?'Create project':'Open'}</button></footer>
      </form>
    </dialog>
  </div>;
}
