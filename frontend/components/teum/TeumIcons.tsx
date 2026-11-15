export type MenuIcon="reservation"|"quiz"|"store"|"community"|"my"|"bell";
const paths:Record<MenuIcon,React.ReactNode>={
 reservation:<><rect x="4" y="5" width="16" height="16" rx="3"/><path d="M4 10h16M8 3v4m8-4v4m-8 7h3m2 0h3"/></>,
 quiz:<path d="M9 4h6v4h4v6h-4v6H9v-4H5v-6h4z"/>,
 store:<path d="M4 8h16l-2-5H6L4 8zm1 0v12h14V8M9 20v-7h6v7"/>,
 community:<path d="M4 4h16v12H10l-6 4zM8 8h8m-8 4h5"/>,
 my:<><circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/></>,
 bell:<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM9 20a3 3 0 0 0 6 0M12 1v1"/>,
};
export function MenuGlyph({name}:{name:MenuIcon}){return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;}
export function CatGlyph(){return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 11 3 3l7 4h4l7-4-1 8c3 9-2 11-8 11S1 20 4 11Z" fill="white"/><path d="m6 7 1 3 2-1m9-2-1 3-2-1" stroke="#d29bb5"/><path d="M7 14q1-2 2 0m6 0q1-2 2 0m-7 4q2 2 4 0m-3-2 1 1 1-1M3 16H1m20 0h2"/></svg>;}
