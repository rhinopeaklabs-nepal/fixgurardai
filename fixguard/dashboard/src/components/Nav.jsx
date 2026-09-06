import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

const LINKS = [
  ["/", "Audit"],
  ["/prompts", "Prompt Studio"],
  ["/history", "History"],
  ["/architecture", "Architecture"],
];

export default function Nav() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuRef = useRef(null);
  const navigate = useNavigate();

  // A menu that only closes by clicking its own button is a menu people end
  // up trapped in; close on an outside click and on Escape.
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function handleSignOut() {
    setOpen(false);
    await signOut();
    navigate("/signin", { replace: true });
  }

  const label = user?.name || user?.email || "";
  const initial = (label[0] || "?").toUpperCase();

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-4xl items-center gap-1 px-5">
        <span className="mr-4 py-3 font-black tracking-tight text-brand">
          FixGuard AI
        </span>

        <div className="hidden items-center gap-1 sm:flex">
          {LINKS.map(([to, text]) => (
            <NavLink key={to} to={to} end={to === "/"} className={linkClass}>
              {text}
            </NavLink>
          ))}
        </div>

        <div className="relative ml-auto flex items-center gap-1" ref={menuRef}>
          <button
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Menu"
            aria-expanded={mobileOpen}
            className="rounded-lg px-2 py-1.5 text-slate-500 hover:bg-slate-100 sm:hidden"
          >
            <span aria-hidden className="block text-lg leading-none">≡</span>
          </button>

          {user && (
            <>
              <button
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                aria-haspopup="menu"
                className="flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-3 transition hover:bg-slate-100"
              >
                <span className="grid h-7 w-7 place-items-center rounded-full bg-brand text-xs font-bold text-white">
                  {initial}
                </span>
                <span className="hidden max-w-[11rem] truncate text-sm font-medium text-slate-700 md:block">
                  {label}
                </span>
              </button>

              {open && (
                <div
                  role="menu"
                  className="absolute right-0 top-full z-20 mt-1 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
                >
                  <div className="border-b border-slate-100 px-4 py-3">
                    {user.name && (
                      <p className="truncate font-semibold text-slate-900">
                        {user.name}
                      </p>
                    )}
                    <p className="truncate text-sm text-slate-500">{user.email}</p>
                  </div>
                  <button
                    role="menuitem"
                    onClick={handleSignOut}
                    className="w-full px-4 py-2.5 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {mobileOpen && (
        <div className="flex flex-col border-t border-slate-100 px-3 pb-2 sm:hidden">
          {LINKS.map(([to, text]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2.5 text-sm font-medium ${
                  isActive ? "bg-brand/10 text-brand" : "text-slate-600"
                }`
              }
            >
              {text}
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  );
}

const linkClass = ({ isActive }) =>
  `border-b-2 px-3 py-3 text-sm font-medium transition ${
    isActive
      ? "border-brand text-brand"
      : "border-transparent text-slate-500 hover:text-slate-800"
  }`;
