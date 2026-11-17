import {createRoot} from 'react-dom/client';
import {KeypointTraining} from '../src/KeypointTraining';
import type {Labeling} from '../src/labeling/useLabeling';
import '@freemocap/ui/styles.css';

createRoot(document.getElementById('root')!).render(<KeypointTraining baseUrl="" id="recording" parent="/fixture"
  labeling={{document:null} as Labeling}/>);
