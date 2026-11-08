import { cn } from "@/lib/utils";
import {
  formatCompact,
  formatCurrency,
  formatNumber,
  formatPercent,
  type AppLocale,
} from "@/lib/format";

type NumProps = {
  value: number;
  locale: AppLocale;
  format?: "number" | "currency" | "percent" | "compact";
  currency?: string;
  className?: string;
};

export function Num({
  value,
  locale,
  format = "number",
  currency = "USD",
  className,
}: NumProps) {
  const formattedValue = {
    number: () => formatNumber(value, locale),
    currency: () => formatCurrency(value, locale, currency),
    percent: () => formatPercent(value, locale),
    compact: () => formatCompact(value, locale),
  }[format]();

  return (
    <span dir="ltr" className={cn("tabular-nums", className)}>
      {formattedValue}
    </span>
  );
}
