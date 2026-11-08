import { fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { Activity } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import { EmptyState } from "./empty-state";
import { ErrorState } from "./error-state";

function renderWithMessages(children: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      {children}
    </NextIntlClientProvider>,
  );
}

describe("page states", () => {
  it("renders an empty state and invokes its action", () => {
    const onClick = vi.fn();
    renderWithMessages(
      <EmptyState
        icon={Activity}
        title="No chains"
        description="Add a chain to begin."
        action={{ label: "Add chain", onClick }}
      />,
    );

    expect(screen.getByRole("heading", { name: "No chains" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Add chain" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("renders an error state and retries", () => {
    const onRetry = vi.fn();
    renderWithMessages(<ErrorState onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
