import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Booking Agent — Live Events & Tickets",
  description:
    "Book live events in one chat. A WeBook-inspired demo powered by the Booking-Agent (AI concierge for events in Saudi Arabia).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg text-white antialiased">{children}</body>
    </html>
  );
}
