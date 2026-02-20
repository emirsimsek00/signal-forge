import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import AlertToast from "@/components/AlertToast";

export const metadata: Metadata = {
  title: "SignalForge — AI Operations Copilot",
  description:
    "Multimodal AI intelligence platform for cross-signal risk assessments, incident detection, and executive briefings.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body suppressHydrationWarning>
        <Sidebar />
        <main className="ml-64 min-h-screen p-8">{children}</main>
        <AlertToast />
      </body>
    </html>
  );
}
