import {useCallback,useEffect,useState} from 'react';
import type {TargetCropBounds,TargetCropRequest} from '@freemocap/ui';
interface CropMetadata {recording_id:string;width:number;height:number;filenames:Record<string,string>;cameras:Record<string,Record<string,TargetCropBounds|null>>}
export function useTargetCrop(baseUrl:string,url:string|undefined|null) {
 const [loaded,setLoaded]=useState<{url:string;data:CropMetadata}|null>(null);
 useEffect(()=>{
  if(!url)return;
  const abort=new AbortController();
  void fetch(baseUrl+url,{signal:abort.signal}).then(async response=>{
   if(!response.ok)throw new Error('Target close-up metadata unavailable');
   const data:CropMetadata=await response.json();if(!abort.signal.aborted)setLoaded({url,data});
  }).catch(()=>{/* The crop renderer displays unavailable; never reuse another target. */});
  return()=>abort.abort();
 },[baseUrl,url]);
 return useCallback((request:TargetCropRequest):TargetCropBounds|null=>{
  if(!loaded||loaded.url!==url)return null;
  const data=loaded.data,camera=data.filenames[request.filename];
  if(request.recording.id!==data.recording_id||request.imageWidth!==data.width||request.imageHeight!==data.height||!camera)return null;
  return data.cameras[camera]?.[String(request.sourceFrameNumber)]??null;
 },[loaded,url]);
}
