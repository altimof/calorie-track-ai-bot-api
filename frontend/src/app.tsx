import { lazy } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { TelegramProvider } from "@/providers/telegram";
import { AppLayout } from "@/components/layout/AppLayout";
import {
  isNotRegisteredError,
  markNotRegistered,
  shouldRetry,
} from "@/api/registration";

const Meals = lazy(() => import("@/pages/meals"));
const Stats = lazy(() => import("@/pages/stats"));
const Goals = lazy(() => import("@/pages/goals"));
const Feedback = lazy(() => import("@/pages/feedback"));

function onApiError(error: unknown) {
  if (isNotRegisteredError(error)) markNotRegistered();
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onApiError }),
  mutationCache: new MutationCache({ onError: onApiError }),
  defaultOptions: {
    queries: {
      staleTime: 50 * 60_000,
      retry: shouldRetry,
      refetchOnWindowFocus: false,
    },
  },
});

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <Meals /> },
      { path: "/stats", element: <Stats /> },
      { path: "/goals", element: <Goals /> },
      { path: "/feedback", element: <Feedback /> },
    ],
  },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TelegramProvider>
        <RouterProvider router={router} />
      </TelegramProvider>
    </QueryClientProvider>
  );
}
