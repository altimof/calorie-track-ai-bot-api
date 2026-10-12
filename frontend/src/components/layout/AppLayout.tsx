import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Navigation } from "./Navigation";
import { ErrorBoundary } from "./ErrorBoundary";

function PageLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-tg-bg">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-tg-hint border-t-tg-button" />
    </div>
  );
}

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-tg-bg text-tg-text">
      {/* Bottom padding clears the fixed Navigation, which also pads for the safe area */}
      <main className="flex-1 pb-[calc(4rem+var(--safe-area-bottom,0px))] pt-[var(--safe-area-top,0px)]">
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
