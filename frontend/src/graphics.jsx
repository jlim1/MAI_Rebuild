import React from 'react';

const glyphs = {
  box: <><path d="m3 7 9-5 9 5v10l-9 5-9-5z M3 7l9 5 9-5 M12 12v10 M7.5 4.5l9 5" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6"/>,
  stock: <><path d="M3 4v16m18-16v16M3 12h18M3 19h18M6 5h5v7H6zM13 7h5v5h-5zM7 15h6v4H7z"/></>,
  slip: <><path d="M5 3h14v18l-3-1.8-4 1.8-4-1.8L5 21zM8 8h8m-8 4h8m-8 4h4"/></>,
  refresh: <><path d="M20 5v5h-5M4 19v-5h5M5.4 8a7.4 7.4 0 0 1 12.4-3L20 9M4 15l2 3a7.5 7.5 0 0 0 12.5-2"/></>,
  check: <path d="m4.5 12.5 5 5 10-11"/>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
};
export function Icon({ name, size = 20 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{glyphs[name]}</svg>;
}

export function CaseDrawing() {
  return <figure className="plate" aria-hidden="true"><svg viewBox="0 0 330 145" fill="none" focusable="false">
    <g stroke="#8b9990" strokeWidth=".8" strokeDasharray="3 4"><path d="m45 101 136 37 110-47M92 42l88-34 77 20"/><path d="M90 109v12m115-14v21M244 41h51m-47 56h47"/></g>
    <g stroke="#35463e" strokeWidth="1.7" strokeLinejoin="round">
      <path d="m84 42 72-28 99 25-72 32z" fill="#dae0d3"/><path d="m84 42 99 29v59l-99-31z" fill="#c4cebf"/><path d="m183 71 72-32v57l-72 34z" fill="#abbba9"/>
      <path d="m84 53 99 29 72-32m-171 9 99 29 72-32m-171 36 99 31 72-33"/>
      <g fill="#f4f3df"><path d="m95 45 8 2 72-28-8-2zM164 65l8 2 72-31-8-2zM95 46l8 2v57l-8-2zM164 66l8 2v58l-8-3z"/></g>
      <path d="m209 74 20-9v8l-20 9z" fill="#6c7c6c"/><path d="m213 74 12-5v3l-12 5z" fill="#f4f3df"/>
      <path d="m108 58 7 2v14l-7-2zm44 13 7 2v13l-7-2z" fill="#f2c591"/>
      <path d="m117 79 31 9v16l-31-9z" fill="#f6f5e7"/>
      <g strokeWidth="1"><path d="m121 84 21 6m-21-2 12 3.5m-12 0 18 5"/></g>
    </g>
    <g stroke="#778c7f" strokeWidth="1"><path d="M286 39v55m-3-52 6-6m-6 61 6-6M63 113l103 32m-100-35-6 6"/><path d="M57 34h-8m4-4v8m215 71h-8m4-4v8"/></g>
  </svg><figcaption>FIG. 01 <span>/</span> TRANSIT CASE</figcaption></figure>;
}

export function PanelTitle({ icon, index, children, id, action }) {
  return <div className="panel-title"><span className="icon-tile"><Icon name={icon} size={23}/></span><div><div className="eyebrow">STATION {index}</div><h2 id={id} tabIndex={-1}>{children}</h2></div>{action}</div>;
}
