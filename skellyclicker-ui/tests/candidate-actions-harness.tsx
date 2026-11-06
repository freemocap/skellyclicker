import React from 'react';
import {createRoot} from 'react-dom/client';
import '@freemocap/ui/styles.css';
import {TrainingSetPanel} from '../src/TrainingSetPanel';
const project={root:'/fixture',manifest_path:'/fixture/project.json',project:{project_id:'fixture',uuid:'fixture'},recordings:[{recording_id:'recording',source:{path:'/fixture/source.svo2',sha256:'source'},calibration_state:'ready',streams:[{camera_id:'left'},{camera_id:'right'}]}],targets:[{object_id:'part',authored_units:'mm',geometry:{path:'recordings/recording/skellyclicker/inputs/targets/part/r001/part.stl',sha256:'mesh'}}],issues:[],sample_state:'prepared',playback:null};
createRoot(document.getElementById('root')!).render(<TrainingSetPanel baseUrl="http://candidate-fixture.invalid" project={project} snapshots={{}} onClose={()=>{}}/>);
