"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createPublicQueryClient } from "@/lib/public-api/query-client";

export function PublicQueryProvider({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [queryClient] = useState(createPublicQueryClient);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
