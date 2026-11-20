"use client";

import type { ReactNode } from "react";

export function ChartDirectionWrapper({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div dir="ltr" className={className}>
      {children}
    </div>
  );
}