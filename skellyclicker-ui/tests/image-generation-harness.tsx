import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import '@freemocap/ui/styles.css';
import '../src/shell.css';
import {TrainingSetPanel} from '../src/TrainingSetPanel';
import {trainingGraph} from '../src/training-workflow';
(window as any).fixtureGraph=trainingGraph;
const project={manifest_path:'/fixture/project.json',root:'/fixture',project:{project_id:'Whole recording',uuid:'whole-fixture'},recordings:[{recording_id:'stereo',source:{sha256:'source'}}],targets:[{object_id:'benchy',geometry:{path:'benchy.stl',sha256:'target'},authored_units:'mm',authored_geometry:{sha256:'definition'}}],issues:[],sample_state:'prepared',playback:null};
function Harness(){const [open,setOpen]=useState(true);return <><button onClick={()=>setOpen(true)}>Reopen generation</button><TrainingSetPanel open={open} baseUrl="http://images-fixture.invalid" project={project as any} snapshots={{}} onClose={()=>setOpen(false)} onReview={async()=>{(window as any).reviewOpened=true;setOpen(false);}}/></>;}
createRoot(document.getElementById('root')!).render(<Harness/>);
