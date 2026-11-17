import {useState} from 'react';
import {isTauri} from '@tauri-apps/api/core';
import {open} from '@tauri-apps/plugin-dialog';
import type {ProjectView} from './ProjectPanel';

export type OpenRecording = NonNullable<ProjectView['playback']> & {root:string; issues:string[]; sourceSizes:Record<string,[number,number]>};

type RecordingFolder = OpenRecording | {candidates:{name:string;path:string}[]};

async function requestFolder(baseUrl:string, route:string, path:string) {
    const response = await fetch(baseUrl+route, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path}),
    });
    const body = await response.json();
    if (!response.ok) throw Error(body.detail ?? 'Could not open recording');
    return body;
}

export function readFolder(baseUrl:string, path:string):Promise<RecordingFolder> {
    return requestFolder(baseUrl,'/api/recordings/open',path);
}

export function useFolderPicker(baseUrl:string,onRecording:(value:OpenRecording)=>void,onProject:(value:ProjectView)=>void) {
    const [path,setPath] = useState('');
    const [choosing,setChoosing] = useState(false);
    const [busy,setBusy] = useState(false);
    const [error,setError] = useState('');
    const [candidates,setCandidates] = useState<{name:string;path:string}[]>([]);
    async function select(folder:string) {
        setBusy(true);setError('');
        try {
            const result: RecordingFolder | {project:ProjectView} = await requestFolder(baseUrl,'/api/projects/open-folder',folder);
            if ('candidates' in result) {setCandidates(result.candidates);setChoosing(true);}
            else {
                if ('project' in result) onProject(result.project);
                else onRecording(result);
                setChoosing(false);setCandidates([]);
            }
        } catch (e) {setError(String(e));setChoosing(true);}
        finally {setBusy(false);}
    }
    async function browse() {
        setError('');setCandidates([]);
        if (!isTauri()) {setChoosing(true);return;}
        try {
            const folder = await open({directory:true,multiple:false,title:'Open recording or project folder'});
            if (folder) {setPath(folder);await select(folder);}
        } catch (e) {setError(String(e));setChoosing(true);}
    }
    const dialog = choosing && <dialog open aria-label="Open recording or project folder" className="project-dialog">
            <form onSubmit={e=>{e.preventDefault();void select(path);}}>
                <label>Recording folder<input autoFocus required value={path} onChange={e=>setPath(e.target.value)}/></label>
                {candidates.map(r=><button type="button" key={r.path} disabled={busy} onClick={()=>void select(r.path)}>{r.name}</button>)}
                {error&&<p role="alert">{error}</p>}
                <footer><button type="button" onClick={()=>setChoosing(false)}>Cancel</button><button disabled={busy}>Open</button></footer>
            </form></dialog>;
    return {browse,busy,dialog};
}
