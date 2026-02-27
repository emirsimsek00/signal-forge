import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import AlertToast from "@/components/AlertToast";
import PageTransition from "@/components/PageTransition";
import { AuthProvider } from "@/components/AuthProvider";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "SignalForge — AI Operations Platform",
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
      <body className={inter.className} suppressHydrationWarning>
        <AuthProvider>
          <Sidebar />
          <main className="ml-64 min-h-screen p-8">
            <PageTransition>{children}</PageTransition>
          </main>
          <AlertToast />
        </AuthProvider>
      </body>
    </html>
  );
}
