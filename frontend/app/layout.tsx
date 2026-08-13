import "../styles/tokens.css";
import "../styles/globals.css";
import type { Metadata } from "next";
import { QueryProvider } from "@/shared/providers/QueryProvider";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AutoBOQ",
  description: "Construction takeoff and BOQ workspace"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><QueryProvider>{children}</QueryProvider></body>
    </html>
  );
}
