'use strict';
const ICON_PATHS={
 grid:'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
 chart:'<path d="M4 20V11h3v9m4 0V6h3v14m4 0V3h3v17"/>',
 pin:'<path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
 network:'<circle cx="6" cy="5" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="6" cy="19" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8 7 8 10m-8 0 8-10"/>',
 file:'<path d="M5 3h9l5 5v13H5Z M14 3v6h5 M8 13h8 M8 17h8"/>',
 target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4"/>',
 send:'<path d="m3 10 18-7-7 18-3-7Zm8 4L21 3"/>',
 database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 10c0 4 16 4 16 0M4 15c0 4 16 4 16 0"/>',
 dollar:'<path d="M12 2v20m5-15c0-5-10-5-10 0s10 3 10 9-10 5-10 0"/>',
 star:'<path d="m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/>',
 layers:'<path d="m12 2 10 6-10 6L2 8Zm-10 11 10 6 10-6M2 18l10 6 10-6"/>',
 person:'<circle cx="12" cy="6" r="4"/><path d="M5 17c0-8 14-8 14 0v3H5Z"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18M7 15h2m3 0h2m3 0h1M7 18h2m3 0h2"/>',
 search:'<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
 bell:'<path d="M5 17h14l-2-3V8a5 5 0 0 0-10 0v6ZM9 21h6"/>',
 chevron:'<path d="m8 4 8 8-8 8"/>',
};
function icon(name){return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON_PATHS[name]||ICON_PATHS.file}</svg>`;}
