import {NextRequest,NextResponse} from "next/server";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){
 if(process.env.NODE_ENV!=="development")return new NextResponse(null,{status:404});
 const handler=await import("@/lib/dev-crawlers-route");
 return handler.GET(request);
}
export async function POST(request:NextRequest){
 if(process.env.NODE_ENV!=="development")return new NextResponse(null,{status:404});
 const handler=await import("@/lib/dev-crawlers-route");
 return handler.POST(request);
}
