import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import '@freemocap/ui/styles.css';
import '../src/shell.css';
import {DatasetQualityPanel,type GenerationMode} from '../src/DatasetQualityPanel';
const images=Array.from({length:3038},(_,i)=>({image_id:'image-'+i,moment_id:'moment-'+Math.floor(i/2),camera_id:i%2?'right':'left',source_frame:Math.floor(i/2),timestamp_ns:String(Math.floor(i/2)*33333333),playback_frame:Math.floor(i/2)}));
const result={path:'/fixture',manifest_sha256:'labels-1',playback_id:'fixture',images,manifest:{moment_count:1519,image_count:3038,label_count:157976}};
function Harness(){const [selection,setSelection]=useState({sha256:'selection-1',selected_image_ids:images.slice(31).map(r=>r.image_id),review_state:'reviewed'});const [mode,setMode]=useState<GenerationMode>('selection');return <div style={{height:'100vh'}}><DatasetQualityPanel baseUrl="http://quality-fixture.invalid" projectPath="/fixture/project.json" result={result} selection={selection} onSelection={setSelection} onNavigate={()=>{}} mode={mode} onMode={setMode} recording={<div>Recording controls fixture</div>} model={<div>Model controls fixture</div>}/></div>}
createRoot(document.getElementById('root')!).render(<Harness/>);
