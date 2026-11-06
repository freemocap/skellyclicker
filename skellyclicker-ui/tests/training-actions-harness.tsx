import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import '@freemocap/ui/styles.css';
import '../src/shell.css';
import {TrainingDashboard} from '../src/TrainingDashboard';
const fixture=(window as any).fixture;
function Harness(){const [snapshots,setSnapshots]=useState({});const [revision,setRevision]=useState('one');(window as any).setTrainingSnapshot=(value:any)=>setSnapshots({[value.run_id]:value});(window as any).setSelectionRevision=setRevision;return <TrainingDashboard baseUrl="http://training-fixture.invalid" project={fixture.project} snapshots={snapshots} rememberedRun={null} onRememberRun={()=>{}} selectionRevision={revision}/>;}
createRoot(document.getElementById('root')!).render(<Harness/>);
