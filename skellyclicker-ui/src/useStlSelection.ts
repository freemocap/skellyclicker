import {useEffect,useRef,useState} from 'react';
import {open} from '@tauri-apps/plugin-dialog';
import type {ProjectView} from './ProjectPanel';

type Units='mm'|'m';
interface Selection {path:string;authored_units:Units;sha256:string;compatible:boolean}

/** A browser-local draft. Validation never changes the project's target or results. */
export function useStlSelection(baseUrl:string,project:ProjectView,binding:string) {
  const target=project.targets[0];
  const initialPath=target?.geometry?.path ? project.root.replace(/[\\/]+$/,'')+'/'+target.geometry.path : null;
  const [path,setPath]=useState<string|null>(initialPath);
  const [units,setUnits]=useState<Units>(target?.authored_units==='m'?'m':'mm');
  const [selection,setSelection]=useState<Selection|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const sequence=useRef(0);
  const key='skellyclicker.training-stl.v1:'+project.project.uuid;
  async function validate(nextPath:string|null,nextUnits:Units,persist:boolean) {
    const request=++sequence.current;setBusy(true);setSelection(null);setError('');
    setPath(nextPath);setUnits(nextUnits);
    try {
      const response=await fetch(baseUrl+'/api/projects/validate-stl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:project.manifest_path,path:nextPath,authored_units:nextUnits})});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'STL validation failed.');
      if(request!==sequence.current)return;
      setSelection(result);setPath(result.path);
      if(persist)localStorage.setItem(key,JSON.stringify({binding,path:result.path,units:nextUnits}));
    }catch(e){if(request===sequence.current)setError(String(e));}
    finally {if(request===sequence.current)setBusy(false);}
  }
  useEffect(()=>{
    let nextPath=initialPath,nextUnits:Units=target?.authored_units==='m'?'m':'mm';
    try {const stored=JSON.parse(localStorage.getItem(key)??'null');if(stored?.binding===binding&&typeof stored.path==='string'&&(stored.units==='mm'||stored.units==='m')){nextPath=stored.path;nextUnits=stored.units;}}catch{/* Validate current target if no readable draft exists. */}
    void validate(nextPath,nextUnits,false);
    return()=>{sequence.current++;};
  },[baseUrl,project.manifest_path,binding]);
  async function browse() {
    setError('');
    try {
      // Native dialog registration and permissions follow [@tauriDialog2026].
      const chosen=await open({multiple:false,directory:false,filters:[{name:'STL geometry',extensions:['stl']}],...(path?{defaultPath:path}:{})});
      if(typeof chosen==='string')await validate(chosen,units,true);
    }catch(e){setError(String(e));}
  }
  return {path,units,busy,error,compatible:selection?.compatible===true,validated:selection!==null,
    browse,changeUnits:(next:string)=>{if(next==='mm'||next==='m')void validate(path,next,true);}};
}
