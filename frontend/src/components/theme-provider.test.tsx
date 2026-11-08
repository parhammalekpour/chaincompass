import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeProvider, useTheme } from "./theme-provider";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.classList.remove("dark", "light");
  document.documentElement.style.colorScheme = "";
});

function ThemeDisplay() {
  const { theme, setTheme } = useTheme();

  return (
    <button type="button" onClick={() => setTheme("light")}>
      {theme}
    </button>
  );
}

describe("ThemeProvider", () => {
  it("renders without injecting an inline script", () => {
    const { container } = render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>,
    );

    expect(container.querySelector("script")).not.toBeInTheDocument();
  });

  it("applies and persists the selected theme", () => {
    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole("button"));

    expect(document.documentElement).toHaveClass("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(window.localStorage.getItem("theme")).toBe("light");
  });

  it("restores a saved theme", async () => {
    window.localStorage.setItem("theme", "light");

    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>,
    );

    expect(await screen.findByRole("button", { name: "light" })).toBeVisible();
    expect(document.documentElement).toHaveClass("light");
  });
});
