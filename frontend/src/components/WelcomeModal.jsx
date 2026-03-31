import { useState, useEffect } from "react";
import { LATEST_UPDATES, ALL_FEATURES, UPCOMING, CURRENT_VERSION, CURRENT_DATE } from "../utils/announcements";
import "./WelcomeModal.css";

const STORAGE_KEY = "welcome_modal_dismissed_version";

export default function WelcomeModal() {
  const [open, setOpen] = useState(false);
  const [dontShowAgain, setDontShowAgain] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (dismissed !== CURRENT_VERSION) {
      const timer = setTimeout(() => setOpen(true), 800);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleClose = () => {
    if (dontShowAgain) {
      localStorage.setItem(STORAGE_KEY, CURRENT_VERSION);
    }
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div className="welcome-overlay" onClick={handleClose}>
      <div className="welcome-modal" onClick={(e) => e.stopPropagation()}>

        <div className="welcome-header">
          <h2>🌟 欢迎使用 AstroChat</h2>
          <div className="welcome-version-row">
            <span className="welcome-version-badge">v{CURRENT_VERSION}</span>
            <span className="welcome-version-date">{CURRENT_DATE}</span>
          </div>
        </div>

        <div className="welcome-body">

          <div className="welcome-section">
            <h3>🆕 本次更新</h3>
            <ul>
              {LATEST_UPDATES.map((item) => (
                <li key={item.label}>
                  <div className="welcome-item-header">
                    <span className="welcome-item-label">{item.label}</span>
                    <span className="welcome-badge welcome-badge-new">NEW</span>
                  </div>
                  <p className="welcome-item-desc">{item.description}</p>
                </li>
              ))}
            </ul>
          </div>

          <div className="welcome-section">
            <h3>✅ 已上线功能</h3>
            <ul>
              {ALL_FEATURES.map((item) => (
                <li key={item.label}>
                  <div className="welcome-item-header">
                    <span className="welcome-item-label">{item.label}</span>
                  </div>
                  <p className="welcome-item-desc">{item.description}</p>
                </li>
              ))}
            </ul>
          </div>

          <div className="welcome-section">
            <h3>🚧 即将上线</h3>
            <ul>
              {UPCOMING.map((item) => (
                <li key={item.label}>
                  <div className="welcome-item-header">
                    <span className="welcome-item-label">{item.label}</span>
                    <span className="welcome-badge welcome-badge-soon">即将</span>
                  </div>
                  <p className="welcome-item-desc">{item.description}</p>
                </li>
              ))}
            </ul>
          </div>

        </div>

        <div className="welcome-footer">
          <label className="welcome-checkbox-label">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            不再显示此版本公告
          </label>
          <button className="welcome-btn" onClick={handleClose}>
            开始使用
          </button>
        </div>
      </div>
    </div>
  );
}