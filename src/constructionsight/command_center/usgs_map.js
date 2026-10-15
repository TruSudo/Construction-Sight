'use strict';
// Public USGS National Map cached Web Mercator basemaps. Imagery acquisition dates
// vary by location; a tile is geographic context, never proof of current activity.
const USGS_BASEMAPS=Object.freeze({
 'usgs-imagery':Object.freeze({label:'USGS aerial imagery',service:'USGSImageryOnly',attribution:'USDA / USGS The National Map · orthoimagery'}),
 'usgs-imagery-topo':Object.freeze({label:'USGS aerial + topographic labels',service:'USGSImageryTopo',attribution:'USGS The National Map · orthoimagery and US Topo'}),
 'usgs-topo':Object.freeze({label:'USGS topographic map',service:'USGSTopo',attribution:'USGS The National Map · topographic datasets'})
});
const USGS_HOST='https://basemap.nationalmap.gov/arcgis/rest/services/';
const MAP_CHOICES=Object.freeze(['auto','offline',...Object.keys(USGS_BASEMAPS)]);
function safeMapMode(value){return MAP_CHOICES.includes(value)?value:'auto';}
function usgsTileUrl(mode,z,x,y){
 const provider=USGS_BASEMAPS[mode];
 if(!provider||![z,x,y].every(Number.isInteger)||z<0||z>16||x<0||y<0||x>=2**z||y>=2**z)throw Error('Invalid USGS tile coordinates');
 // ArcGIS REST tile order is /tile/{level}/{row}/{column}, unlike XYZ.
 return USGS_HOST+provider.service+'/MapServer/tile/'+z+'/'+y+'/'+x;
}
function mapTileGrid(center,zoom,width,height,providerMaxZoom=18){
 // Cached tiles have integer levels, but the app's world() uses fractional
 // zoom. Scale tile origins AND tile sizes consistently with the markers.
 const level=Math.min(providerMaxZoom,Math.floor(zoom)),size=256*2**(zoom-level);
 const [cx,cy]=world(...center),left=cx-width/2,top=cy-height/2,tiles=[];
 const extent=2**level;
 for(let x=Math.floor(left/size);x<=Math.floor((left+width)/size);x++)
  for(let y=Math.floor(top/size);y<=Math.floor((top+height)/size);y++)
   if(x>=0&&y>=0&&x<extent&&y<extent)
    tiles.push({z:level,x,y,left:x*size-left,top:y*size-top,size});
 return tiles;
}
function mapScaleBar(lat,zoom){
 const latitude=Math.max(-85,Math.min(85,lat));
 const metersPerPixel=156543.03392804097*Math.cos(latitude*Math.PI/180)/2**zoom;
 const ideal=metersPerPixel*105,order=10**Math.floor(Math.log10(ideal));
 const length=[1,2,5,10].map(v=>v*order).filter(v=>v<=ideal).pop()||order;
 return {pixels:length/metersPerPixel,label:length>=1000?(length/1000)+' km':length+' m'};
}
