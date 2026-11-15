import TeumApp from "@/components/teum/TeumApp";
export const metadata={title:"방탈출 찾기 · 방픽"};
export default async function Search({searchParams}:{searchParams:Promise<{date?:string;area?:string}>}){const params=await searchParams;return <TeumApp key={`${params.date||"today"}:${params.area||"all"}`} view="reservation" initialDate={params.date} initialArea={params.area}/>;}
