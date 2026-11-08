import { Link } from "react-router-dom";
import { Sparkles, ShieldCheck, Heart, Radio, ExternalLink } from "lucide-react";

export function Footer() {
  return (
    <footer className="startup-footer">
      <div className="footer-glow" />
      <div className="footer-container">
        <div className="footer-top-grid">
          <div className="footer-brand-col">
            <div className="footer-brand-header">
              <div className="footer-brand-icon">
                <Sparkles size={16} />
              </div>
              <h3>Sarkari Saathi</h3>
            </div>
            <p className="footer-tagline">
              Connecting 1.4 Billion Indian citizens to their rightful welfare schemes through the power of conversational Indic voice AI.
            </p>
            <div className="footer-badges">
              <span className="footer-badge">
                <ShieldCheck size={13} />
                Official Gov Links Only
              </span>
              <span className="footer-badge">
                <Radio size={13} />
                8 kHz Phone Noise Resilient
              </span>
            </div>
          </div>

          <div className="footer-links-col">
            <h4>Supported Languages</h4>
            <ul>
              <li>हिन्दी (Hindi & Hinglish)</li>
              <li>தமிழ் (Tamil)</li>
              <li>తెలుగు (Telugu)</li>
              <li>ಕನ್ನಡ (Kannada)</li>
              <li>മലയാളം (Malayalam)</li>
              <li>मराठी (Marathi)</li>
              <li>বাংলা (Bengali) · ગુજરાતી (Gujarati)</li>
            </ul>
          </div>

          <div className="footer-links-col">
            <h4>Technology & Data</h4>
            <ul>
              <li>
                <a href="https://myscheme.gov.in" target="_blank" rel="noreferrer">
                  myScheme.gov.in API
                  <ExternalLink size={11} />
                </a>
              </li>
              <li>
                <a href="https://gnani.ai" target="_blank" rel="noreferrer">
                  Gnani Prisma v3.0 STT
                  <ExternalLink size={11} />
                </a>
              </li>
              <li>Gnani Timbre Indic TTS</li>
              <li>Evon Hybrid Schemas</li>
              <li>CSC Digital Seva Optimized</li>
            </ul>
          </div>

          <div className="footer-links-col">
            <h4>Get Started</h4>
            <ul>
              <li>
                <Link to="/register">Create Account</Link>
              </li>
              <li>
                <Link to="/login">Sign In</Link>
              </li>
              <li>
                <Link to="/desk">Open Voice Desk</Link>
              </li>
              <li>
                <a href="#how">How it Works</a>
              </li>
              <li>
                <a href="#faq">Frequently Asked Questions</a>
              </li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom-bar">
          <div className="footer-copyright">
            © {new Date().getFullYear()} Sarkari Saathi Inc. Built with{" "}
            <Heart size={12} className="heart-icon" /> for the citizens of India.
          </div>
          <div className="footer-disclaimer">
            Sarkari Saathi is an independent civic-tech voice assistant. We never collect application fees or store citizen biometric data. All applications are submitted directly on official government portals (.gov.in / .nic.in).
          </div>
        </div>
      </div>
    </footer>
  );
}
