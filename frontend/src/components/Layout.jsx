import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/replay", label: "Replay" },
  { to: "/journal", label: "Journal" },
  { to: "/levels", label: "Levels" },
  { to: "/settings", label: "Settings" },
  { to: "/ops", label: "Ops" }
];

export default function Layout() {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className={`layout ${navOpen ? "nav-open" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="sidebar-title">Futures Alert Bot</span>
          <button className="btn btn-small" type="button" onClick={() => setNavOpen(false)}>
            Close
          </button>
        </div>
        <nav className="nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              onClick={() => setNavOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="layout-body">
        <header className="topbar">
          <button className="btn btn-small" type="button" onClick={() => setNavOpen(true)}>
            Menu
          </button>
          <div className="topbar-links">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                {item.label}
              </NavLink>
            ))}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
