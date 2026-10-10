import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthProvider";
import { AppLayout } from "./components/AppLayout";
import { CookieConsent } from "./components/CookieConsent";
import { RouteMetadata } from "./components/RouteMetadata";
import { ConfigurationPage } from "./pages/ConfigurationPage";
import { LoginPage } from "./pages/LoginPage";

const OverviewPage = lazy(() => import("./pages/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const WatchlistPage = lazy(() => import("./pages/WatchlistPage").then((module) => ({ default: module.WatchlistPage })));
const GovernancePage = lazy(() => import("./pages/GovernancePage").then((module) => ({ default: module.GovernancePage })));
const DataSyncPage = lazy(() => import("./pages/DataSyncPage").then((module) => ({ default: module.DataSyncPage })));
const LiveReviewPage = lazy(() => import("./pages/LiveReviewPage").then((module) => ({ default: module.LiveReviewPage })));
const LegalPage = lazy(() => import("./pages/LegalPage").then((module) => ({ default: module.LegalPage })));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage").then((module) => ({ default: module.NotFoundPage })));

function RouteLoading() {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas" role="status" aria-live="polite">
      <div className="w-full max-w-sm px-6">
        <div className="h-2 w-24 animate-pulse bg-line" />
        <div className="mt-5 h-8 w-full animate-pulse bg-line" />
        <div className="mt-3 h-4 w-3/4 animate-pulse bg-line" />
        <span className="sr-only">Loading TalentGuard</span>
      </div>
    </div>
  );
}

function SessionGate() {
  const { configured, loading, session } = useAuth();
  if (!configured) return <ConfigurationPage />;
  if (loading) return <RouteLoading />;
  if (!session) return <LoginPage />;
  return <Outlet />;
}

export default function App() {
  return (
    <>
      <RouteMetadata />
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/privacy" element={<LegalPage kind="privacy" />} />
          <Route path="/terms" element={<LegalPage kind="terms" />} />
          <Route element={<SessionGate />}>
            <Route element={<AppLayout />}>
              <Route index element={<OverviewPage />} />
              <Route path="watchlist" element={<WatchlistPage />} />
              <Route path="live-review" element={<LiveReviewPage />} />
              <Route path="governance" element={<GovernancePage />} />
              <Route path="data-sync" element={<DataSyncPage />} />
            </Route>
          </Route>
          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
      <CookieConsent />
    </>
  );
}
