import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Navigation } from "./Navigation";
import { ErrorBoundary } from "./ErrorBoundary";
import { NotRegistered } from "./NotRegistered";
import { useNotRegistered } from "@/api/registration";

function PageLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-tg-bg">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-tg-hint border-t-tg-button" />
    </div>
  );
}

export function AppLayout() {
  const notRegistered = useNotRegistered();
  if (notRegistered) return <NotRegistered />;

  return (
    <div className="flex min-h-screen flex-col bg-tg-bg text-tg-text">
      <main className="flex-1 pb-16 pt-[var(--safe-area-top,0px)]">
        <ErrorBoundary>
          <Suspense fallback={<PageLoading />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </main>
      <Navigation />
    </div>
  );
}
