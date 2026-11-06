export type Direction=readonly [number,number,number];
export type ViewRotation=readonly number[];
export function projectedHistograms(directions:readonly Direction[],rotation:ViewRotation,bins=24){
 if(rotation.length!==9||rotation.some(v=>!Number.isFinite(v))||!Number.isInteger(bins)||bins<1)throw new Error('Invalid view rotation or histogram bins');
 const horizontal=Array<number>(bins).fill(0),vertical=Array<number>(bins).fill(0);let horizontalUndefined=0,verticalUndefined=0,invalid=0;
 const index=(angle:number)=>Math.min(bins-1,Math.floor((((angle+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI))/(2*Math.PI)*bins));
 for(const d of directions){
  if(d.length!==3||d.some(v=>!Number.isFinite(v))||Math.hypot(...d)<1e-12){invalid++;continue;}
  const x=rotation[0]*d[0]+rotation[1]*d[1]+rotation[2]*d[2],y=rotation[3]*d[0]+rotation[4]*d[1]+rotation[5]*d[2],z=rotation[6]*d[0]+rotation[7]*d[1]+rotation[8]*d[2];
  if(Math.hypot(x,z)<1e-12)horizontalUndefined++;else horizontal[index(Math.atan2(x,z))]++;
  if(Math.hypot(y,z)<1e-12)verticalUndefined++;else vertical[index(Math.atan2(y,z))]++;
 }
 return {horizontal,vertical,horizontalUndefined,verticalUndefined,invalid};
}
