import { NavLink } from "react-router-dom";

const LINKS = [
  ["/", "Audit"],
  ["/prompts", "Prompt Studio"],
  ["/history", "History"],
  ["/architecture", "Architecture"],
];

export default function Nav() {
  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-3xl items-center gap-1 px-5">
        <span className="mr-4 py-3 font-black tracking-tight text-brand">FixGuard AI</span>
        {LINKS.map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `border-b-2 px-3 py-3 text-sm font-medium transition ${
                isActive
                  ? "border-brand text-brand"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
