import { Route, Routes } from "react-router-dom";
import { GuestOnly, RequireAuth } from "./components/RouteGuards";
import { ScrollManager } from "./components/ScrollManager";
import { DeskPage } from "./pages/DeskPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SchemesPage } from "./pages/SchemesPage";

/**
 * Route map
 *   /            public    landing page
 *   /schemes     public    paginated scheme directory (?q=&page=)
 *   /login       guests    signed-in users are sent on to /desk (or where they were headed)
 *   /register    guests    same as /login
 *   /desk        auth      voice conversation (?session=ID opens a past one); signed-out users go to /login and return after
 *   /history     auth      paginated list of past conversations (?page=)
 *   *            public    404
 */
export function App() {
  return (
    <>
      <ScrollManager />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/schemes" element={<SchemesPage />} />

        <Route element={<GuestOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<RequireAuth />}>
          <Route path="/desk" element={<DeskPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}
