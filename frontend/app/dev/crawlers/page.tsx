import { notFound } from "next/navigation";
import CrawlerDashboard from "./CrawlerDashboard";

export const metadata = { title: "크롤링 현황판 · 이스케이프맵", robots: { index: false, follow: false } };

export default function CrawlerDashboardPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <CrawlerDashboard />;
}
