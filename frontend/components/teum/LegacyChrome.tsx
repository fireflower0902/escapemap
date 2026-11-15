"use client";
import {usePathname} from "next/navigation";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
export default function LegacyChrome({children}:{children:React.ReactNode}){const pathname=usePathname();return pathname.startsWith('/dev')||pathname==='/login'?<><Header/><main className="flex-1">{children}</main><Footer/></>:<>{children}</>;}
