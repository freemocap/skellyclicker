import React from 'react';
import {createRoot} from 'react-dom/client';
import '@freemocap/ui/styles.css';
import '../src/shell.css';
import {CheckpointImages} from '../src/CheckpointImages';
import {AppShell} from '../src/AppShell';
createRoot(document.getElementById('root')!).render(<AppShell view="training" onView={()=>{}} sidebar={null} training={<CheckpointImages baseUrl="http://epochs.invalid" projectPath="/project.json" runId="run1"/>}>{null}</AppShell>);
