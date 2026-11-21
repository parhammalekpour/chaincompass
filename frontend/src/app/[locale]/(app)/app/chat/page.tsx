import { Suspense } from "react";
import { ChatPage } from "@/components/app/chat-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("chat", "/app/chat", locale);
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ChatPage />
    </Suspense>
  );
}
