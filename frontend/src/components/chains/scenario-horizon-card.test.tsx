import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";
import en from "../../../messages/en.json";
import scenariosFixture from "@/test/fixtures/btc-scenarios.json";
import {
  scenariosResponseSchema,
  type ScenarioHorizon,
} from "@/lib/public-api/contracts";
import { ScenarioHorizonCard } from "./scenario-horizon-card";

afterEach(cleanup);

function renderCard(horizon: ScenarioHorizon) {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <ScenarioHorizonCard horizon={horizon} />
    </NextIntlClientProvider>,
  );
}

describe("ScenarioHorizonCard", () => {
  const horizons = scenariosResponseSchema.parse(scenariosFixture).horizons;

  it("shows signed percentages, independent sample context, and low-sample status neutrally", () => {
    renderCard(horizons[2]!);

    expect(screen.getByText("Low sample")).toBeVisible();
    expect(screen.getByText("-47.37%")).toBeVisible();
    expect(screen.getByText("Independent windows").parentElement).toHaveTextContent(
      "8",
    );
    expect(screen.getByText("-47.37%")).not.toHaveClass("text-danger");
    expect(screen.getByText("-47.37%")).not.toHaveClass("text-success");
  });

  it("explains an unavailable horizon and retains its independent sample count", () => {
    const unavailable: ScenarioHorizon = {
      ...horizons[0]!,
      available: false,
      reason: "insufficient_history",
      n_independent: 0,
      scenarios: [],
    };
    renderCard(unavailable);

    expect(
      screen.getByText("Not enough history for this horizon."),
    ).toBeVisible();
    expect(
      screen.getByText("Independent windows").parentElement,
    ).toHaveTextContent("0");
  });
});
