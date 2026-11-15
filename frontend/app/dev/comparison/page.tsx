import { notFound } from "next/navigation";
import Comparison from "./Comparison";
export const metadata = { title: "경쟁사 목록 비교 · 이스케이프맵", robots: { index: false, follow: false } };
export default function Page() { if (process.env.NODE_ENV !== "development") notFound(); return <Comparison />; }
