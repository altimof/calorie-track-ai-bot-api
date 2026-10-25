import { describe, it, expect, afterEach } from "vitest";
import { act, screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { markNotRegistered, resetNotRegistered } from "@/api/registration";
import { AppLayout } from "../AppLayout";

describe("AppLayout", () => {
  afterEach(() => resetNotRegistered());

  it("prompts to start the bot when the user is not registered", () => {
    renderWithProviders(<AppLayout />);
    expect(screen.queryByText(/start the bot first/i)).not.toBeInTheDocument();

    act(() => markNotRegistered());

    expect(screen.getByText(/start the bot first/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /back to the chat/i }),
    ).toBeInTheDocument();
  });
});
