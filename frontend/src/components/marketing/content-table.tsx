import type { ReactNode } from "react";

type ContentTableProps = {
  caption: string;
  headings: readonly string[];
  children: ReactNode;
};

export function ContentTable({
  caption,
  headings,
  children,
}: ContentTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-start text-sm">
        <caption className="mb-2 text-start font-semibold">{caption}</caption>
        <thead>
          <tr className="border-b border-border">
            {headings.map((heading) => (
              <th
                key={heading}
                scope="col"
                className="px-3 py-2 text-start font-medium"
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  );
}
