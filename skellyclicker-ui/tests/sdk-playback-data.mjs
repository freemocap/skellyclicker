import {readFile} from 'node:fs/promises';
import {PlaybackManifestSchema,decodePlaybackParquet,prepareRecordedModelFrame} from '@freemocap/client/recording';
const root='C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26';
const project=JSON.parse(await readFile(root+'/benchy-sfn26_project.json','utf8'));
const folder=root+'/'+project.playback_result;
const manifest=PlaybackManifestSchema.parse(JSON.parse(await readFile(folder+'/playback.json','utf8')));
const bytes=await readFile(folder+'/display.parquet');
const runs=await decodePlaybackParquet(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),manifest);
const run=manifest.runs[0],time=run.timelines[0].timestamps_s;
for(const model of run.models){const reader=prepareRecordedModelFrame(run,{channels:runs[0]},model,'stereo');for(const index of [0,1,14,29]){const frame=reader(time[index]);const finite=frame.segmentOrigins.data.every(Number.isFinite);const expected=model.model_id.endsWith('authored_reference')||(model.model_id.endsWith('candidate_pass')?index>=1&&index<=14:index===0||index===29);if(finite!==expected)throw Error('Wrong finite coverage '+model.model_id+' '+index);}}
console.log(JSON.stringify({models:run.models.map(m=>m.model_id),channels:runs[0].length,media:run.media.length,validatedSourceFrames:[0,1,14,29]}));
