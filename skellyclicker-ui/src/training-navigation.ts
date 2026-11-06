export interface TrainingNavigationImage {image_id:string;camera_id:string;source_frame:number;playback_frame:number|null}
/** Membership is camera-specific; navigation deduplicates included, seekable moments. */
export function trainingNavigation<T extends TrainingNavigationImage>(images:readonly T[],selected:ReadonlySet<string>,camera:string|null,currentSource:number|undefined){
 const included=images.filter(row=>selected.has(row.image_id)&&row.playback_frame!==null&&(!camera||row.camera_id===camera));
 const moments=[...new Map(included.map(row=>[row.source_frame,row])).values()].sort((a,b)=>a.source_frame-b.source_frame);
 return {moments,previous:currentSource===undefined?undefined:[...moments].reverse().find(row=>row.source_frame<currentSource),next:moments.find(row=>currentSource===undefined||row.source_frame>currentSource)};
}
