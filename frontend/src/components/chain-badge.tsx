import { cn } from "@/lib/utils";

const chainColors = {
  BTC: "bg-orange-500/15 text-orange-300",
  ETH: "bg-indigo-500/15 text-indigo-300",
  SOL: "bg-violet-500/15 text-violet-300",
  BNB: "bg-amber-500/15 text-amber-300",
} as const;

export function ChainBadge({
  symbol,
  className,
}: {
  symbol: keyof typeof chainColors;
  className?: string;
}) {
  return (
    <span
      aria-label={symbol}
      className={cn(
        "inline-flex size-9 items-center justify-center rounded-full text-xs font-bold",
        chainColors[symbol],
        className,
      )}
    >
      {symbol.slice(0, 2)}
    </span>
  );
}
