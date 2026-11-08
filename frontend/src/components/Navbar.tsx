import { Link, useLocation } from "react-router-dom";
import { Sparkles, Mic, ArrowRight, User as UserIcon, LogOut } from "lucide-react";
import { useAuth } from "../auth";

export function Navbar() {
  const { token, user, logout } = useAuth();
  const location = useLocation();
  const isDesk = location.pathname === "/desk";

  return (
    <header className="startup-navbar">
      <div className="navbar-container">
        {/* Brand / Logo */}
        <Link to="/" className="brand-group">
          <div className="brand-logo-glow">
            <div className="brand-logo-inner">
              <Sparkles size={18} className="brand-sparkle-icon" />
            </div>
          </div>
          <div className="brand-text">
            <div className="brand-title">
              Sarkari Saathi
              <span className="brand-badge-alpha">v2.0</span>
            </div>
            <div className="brand-subtitle">बोलिए, योजना पाइए</div>
          </div>
        </Link>

        {/* Center Links (on landing / non-desk) */}
        {!isDesk && (
          <nav className="navbar-center-links">
            <a href="#how" className="nav-link">How it Works</a>
            <a href="#schemes-explorer" className="nav-link">Live Schemes</a>
            <a href="#tech" className="nav-link">Indic Voice AI</a>
            <a href="#faq" className="nav-link">FAQ</a>
          </nav>
        )}

        {/* Right side actions */}
        <div className="navbar-actions">
          {/* Status pill */}
          <div className="navbar-live-pill" title="Gnani Prisma v3.0 & myScheme active">
            <span className="live-pulse-dot" />
            <span className="live-status-text">Prisma v3.0 Live</span>
          </div>

          {token ? (
            <div className="user-action-group">
              {!isDesk && (
                <Link to="/desk" className="nav-btn-primary">
                  <Mic size={15} />
                  <span>Open Voice Desk</span>
                  <ArrowRight size={14} />
                </Link>
              )}
              {isDesk && (
                <div className="user-profile-badge">
                  <UserIcon size={14} />
                  <span>{user?.name || user?.username || "Citizen"}</span>
                  <button
                    type="button"
                    onClick={logout}
                    className="logout-icon-btn"
                    title="Log out"
                  >
                    <LogOut size={14} />
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="guest-action-group">
              <Link to="/login" className="nav-link-login">
                Log In
              </Link>
              <Link to="/register" className="nav-btn-primary">
                <span>Start Speaking</span>
                <ArrowRight size={14} />
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
