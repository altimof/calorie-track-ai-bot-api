import {
  describe,
  it,
  expect,
  beforeAll,
  afterEach,
  afterAll,
  vi,
} from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { handlers } from "@/test/handlers";
import { renderWithProviders } from "@/test/utils";
import GoalsPage from "../index";

const server = setupServer(...handlers);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("GoalsPage", () => {
  it("renders goals title", () => {
    renderWithProviders(<GoalsPage />);
    expect(screen.getByText("Goals")).toBeInTheDocument();
  });

  it("shows current goal after loading", async () => {
    renderWithProviders(<GoalsPage />);
    await waitFor(() => {
      const matches = screen.getAllByText(/2000/);
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it("has edit button", async () => {
    renderWithProviders(<GoalsPage />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    });
  });

  describe("closing confirmation", () => {
    const webapp = window.Telegram!.WebApp as Required<TelegramWebApp>;

    async function openEditor() {
      renderWithProviders(<GoalsPage />);
      await userEvent.click(
        await screen.findByRole("button", { name: /edit/i }),
      );
      return screen.getByRole("spinbutton");
    }

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it("warns only after the goal is changed, and not after changing it back", async () => {
      const enable = vi.spyOn(webapp, "enableClosingConfirmation");
      const disable = vi.spyOn(webapp, "disableClosingConfirmation");
      const input = await openEditor();
      expect(enable).not.toHaveBeenCalled();

      await userEvent.clear(input);
      await userEvent.type(input, "1800");
      expect(enable).toHaveBeenCalledTimes(1);

      await userEvent.clear(input);
      await userEvent.type(input, "2000");
      expect(disable).toHaveBeenCalledTimes(1);
    });

    it("stops warning when the edit is cancelled", async () => {
      const disable = vi.spyOn(webapp, "disableClosingConfirmation");
      const input = await openEditor();
      await userEvent.clear(input);
      await userEvent.type(input, "1800");

      await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
      expect(disable).toHaveBeenCalledTimes(1);
    });

    it("stops warning after the goal is saved", async () => {
      server.use(
        http.patch("http://localhost:8000/api/v1/goals", () =>
          HttpResponse.json({
            id: "1",
            user_id: "123",
            daily_kcal_target: 1800,
            created_at: "2026-01-01",
            updated_at: "2026-01-02",
          }),
        ),
      );
      const disable = vi.spyOn(webapp, "disableClosingConfirmation");
      const input = await openEditor();
      await userEvent.clear(input);
      await userEvent.type(input, "1800");

      await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
      await waitFor(() => expect(disable).toHaveBeenCalledTimes(1));
    });
  });
});
