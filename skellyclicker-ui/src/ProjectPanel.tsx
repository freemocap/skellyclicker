import {useState} from 'react';
export interface ProjectView {
  root: string; manifest_path: string;
  project: {project_id: string; uuid: string};
  recordings: {recording_id: string; source: {path: string}; calibration_state: string; streams: {camera_id: string}[]}[];
  targets: {object_id: string; authored_units: string}[];
  issues: string[]; sample_state: string; playback: null;
}
const sourceRoot = 'C:/Users/jonma/AppData/Local/ZEDBenchy';
export function ProjectPanel({baseUrl, project, onProject}: {baseUrl: string; project: ProjectView | null; onProject: (p: ProjectView) => void}) {
  const [path, setPath] = useState(() => localStorage.getItem('skellyclicker.projectPath') ?? 'C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26');
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [svo, setSvo] = useState(sourceRoot + '/recordings/benchy-20261104-232220-208509/stereo.svo2');
  const [calibration, setCalibration] = useState(sourceRoot + '/recordings/benchy-20261104-232220-208509/SN23364999.conf');
  const [stl, setStl] = useState(sourceRoot + '/3DBenchy.stl');
  const [objectId, setObjectId] = useState('benchy');
  const [units, setUnits] = useState('mm');
  async function submit() {
    setBusy(true); setError('');
    try {
      const body = creating ? {project_path: path, source_svo: svo, calibration_source: calibration, source_stl: stl, object_id: objectId, authored_units: units} : {project_path: path};
      const response = await fetch(baseUrl + '/api/projects/' + (creating ? 'create' : 'open'), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
      onProject(result); localStorage.setItem('skellyclicker.projectPath', result.manifest_path); setPath(result.manifest_path); setCreating(false);
    } catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  return <section className="project-panel">
    <h2>Project</h2>
    <label>Project folder or manifest<input aria-label="Project path" value={path} onChange={e=>setPath(e.target.value)} disabled={busy}/></label>
    <label className="inline"><input type="checkbox" checked={creating} onChange={e=>setCreating(e.target.checked)} disabled={busy}/>Create a fresh project</label>
    {creating && <>
      <label>Original stereo SVO<input value={svo} onChange={e=>setSvo(e.target.value)}/></label>
      <label>Camera calibration source<input value={calibration} onChange={e=>setCalibration(e.target.value)}/></label>
      <label>Reference STL<input value={stl} onChange={e=>setStl(e.target.value)}/></label>
      <label>Object ID<input value={objectId} onChange={e=>setObjectId(e.target.value)}/></label>
      <label>STL units<select value={units} onChange={e=>setUnits(e.target.value)}><option value="mm">Millimetres</option><option value="m">Metres</option></select></label>
      <p>Original media stays linked. The reference STL is copied into the new project.</p>
    </>}
    <button disabled={busy} onClick={()=>void submit()}>{busy ? 'Verifying files…' : creating ? 'Create project' : 'Open project'}</button>
    {error && <p role="alert">{error}</p>}
    {project && <div className="project-summary"><h3>{project.project.project_id}</h3>
      {project.recordings.map(r=><section key={r.recording_id}><strong>{r.recording_id}</strong><p>{r.streams.map(s=>s.camera_id).join(' + ')} · linked original</p><p title={r.source.path}>{r.source.path}</p><p>Calibration: {r.calibration_state === 'ready' ? 'ready' : 'awaiting fresh replay'}</p></section>)}
      {project.targets.map(t=><p key={t.object_id}>Reference: {t.object_id} ({t.authored_units})</p>)}
      {project.issues.map(issue=><p role="alert" key={issue}>{issue}</p>)}
    </div>}
  </section>;
}
