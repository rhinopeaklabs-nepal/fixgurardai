import { Link } from "react-router-dom";

/**
 * Privacy policy and terms.
 *
 * Written from the code rather than from a template: every claim below
 * corresponds to something in this repository, and the specifics - scrypt,
 * SHA-256 session rows, cookie names without values, thirty-day share links -
 * are there because a policy that only says "we take security seriously"
 * tells a reader nothing they can check.
 *
 * They live in the app rather than on the marketing site because the app is
 * what holds the data. A privacy policy on a different host to the database
 * it describes is one deploy away from describing a system that has changed.
 */

// One address, used in both documents. Whoever operates this deployment has
// to make it deliverable; a policy naming a mailbox nobody reads is worse
// than one that names none.
const CONTACT = "privacy@fixguardai.online";
const UPDATED = "9 September 2026";

export function Privacy() {
  return (
    <Doc title="Privacy" updated={UPDATED}>
      <P>
        FixGuard AI audits a website you own and reports what it found. This
        page describes exactly what that involves storing, for how long, and
        how to get rid of it. It covers <B>app.fixguardai.online</B> and the
        API behind it.
      </P>

      <H>What is stored about you</H>
      <List>
        <LI t="Your account">
          Email address, a display name if you give one, and the date you
          signed up. Your password is never stored — only a scrypt hash of it,
          which cannot be turned back into the password.
        </LI>
        <LI t="Your session">
          Signing in sets one cookie. The database keeps a SHA-256 of the
          session token rather than the token, so a copy of the database does
          not hand over live sessions. Sessions expire after 30 days.
        </LI>
        <LI t="Your audits">
          The address you audited and everything the run found: console
          errors, the routes followed, form results, failed files,
          accessibility and performance measurements, DNS and certificate
          details. These are visible only to your account.
        </LI>
        <LI t="Prompts you generate">
          If you use the Prompt Studio, the text you typed and the prompt it
          produced.
        </LI>
        <LI t="Operational counts">
          Which API routes were called, how long they took as coarse buckets,
          and how many succeeded. These carry no account identity. A
          rate-limiting record keeps a truncated hash of your address for one
          hour so the hourly audit limit can be applied.
        </LI>
      </List>

      <H>What is deliberately not stored</H>
      <List>
        <LI t="Passwords for sites you audit">
          FixGuard never asks for them. To audit a page behind a login you
          sign in yourself and hand over the resulting session; signing out
          ends its access immediately.
        </LI>
        <LI t="Cookie and token values">
          When a run needs a session on your site, only the <em>names</em> of
          the cookies are recorded. The values are used for the run and never
          written down.
        </LI>
        <LI t="Anything a sensitive form would have sent">
          A form containing a password, card number, CVV, IBAN or national
          identity field is never submitted. Neither is a sign-out link or
          anything that looks like it deletes data.
        </LI>
        <LI t="Analytics and advertising">
          There are none. No tracking pixels, no advertising identifiers, no
          third-party analytics, and nothing is sold or shared for marketing.
        </LI>
      </List>

      <H>Cookies</H>
      <P>
        One: <Code>fixguard_session</Code>. It is httpOnly, so no script on the
        page can read it, and it exists only to keep you signed in. There are
        no analytics or advertising cookies, which is why there is no cookie
        banner asking you to accept any.
      </P>

      <H>Other companies involved</H>
      <List>
        <LI t="Hostinger">
          Hosts the server and the database. Your data sits on a virtual
          machine we rent from them.
        </LI>
        <LI t="Google Fonts">
          The pages load one typeface from <Code>fonts.googleapis.com</Code>.
          Your browser makes that request directly, so Google sees the request
          the way it sees any font request.
        </LI>
        <LI t="The site you audit">
          A run visits it from our server, so that site&rsquo;s own logs will
          show our address as a visitor.
        </LI>
      </List>
      <P>
        Nothing else. No data processor beyond these receives your account or
        audit data.
      </P>

      <H>Share links</H>
      <P>
        Creating a share link makes that one report readable by{" "}
        <B>anyone who has the link</B>, without signing in — that is what it is
        for. Links stop working after 30 days, and deleting the audit stops
        them immediately. Do not create one for a report you would not hand to
        a stranger.
      </P>

      <H>How long things are kept</H>
      <Table
        rows={[
          ["Audits and reports", "Until you delete them"],
          ["Account and email", "Until you delete the account"],
          ["Sessions", "30 days, then removed automatically"],
          ["Share links", "30 days from creation"],
          ["Rate-limit records", "24 hours"],
          ["Operational counts", "30 days"],
        ]}
      />

      <H>Getting rid of it</H>
      <P>Three controls, all in the app and all immediate:</P>
      <List>
        <LI t="Delete one audit">
          On the report page. Takes its share link with it, so a link already
          sent to a client stops resolving.
        </LI>
        <LI t="Delete all your data">
          Removes every audit and prompt on the account, keeping the account
          itself.
        </LI>
        <LI t="Delete the account">
          Removes the account, the data, and every session with it.
        </LI>
      </List>
      <P>
        Deletion removes the rows. It is not a flag that hides them. If you
        would rather ask than click, write to <Mail /> and say which.
      </P>

      <H>Security</H>
      <P>
        Passwords are hashed with scrypt. Session tokens are stored hashed.
        Everything travels over HTTPS. An audit belongs to the account that
        ran it, and asking for somebody else&rsquo;s audit answers the same
        &ldquo;not found&rdquo; as asking for one that never existed, so the
        identifiers cannot be walked.
      </P>
      <P>
        No system is beyond compromise. If something happens that affects your
        data, you will be told what happened rather than that &ldquo;an
        incident occurred&rdquo;.
      </P>

      <H>Children</H>
      <P>
        This is a developer tool and is not directed at children. Accounts are
        not knowingly created for anyone under 16.
      </P>

      <H>Changes</H>
      <P>
        If this page changes in a way that affects what is collected or how
        long it is kept, the date at the top changes with it.
      </P>

      <H>Contact</H>
      <P>
        <Mail /> — for a question, a correction, a copy of your data, or a
        deletion you would rather not do yourself.
      </P>
    </Doc>
  );
}

export function Terms() {
  return (
    <Doc title="Terms" updated={UPDATED}>
      <P>
        Plain terms for a small tool. Using FixGuard AI means agreeing to
        these.
      </P>

      <H>The one rule that matters</H>
      <P>
        <B>
          Only audit a site you own or have permission to test.
        </B>{" "}
        This is not a formality. An audit is not a passive scan: it fills your
        forms in with clearly-labelled test data and presses submit, which can
        create records, send notifications and reach real inboxes. Pointing it
        at somebody else&rsquo;s site is both a breach of these terms and,
        depending on where you are, potentially unlawful. Every run asks you to
        confirm this, and that confirmation is the basis on which it proceeds.
      </P>

      <H>What FixGuard does, and what it does not claim</H>
      <List>
        <LI t="Forms">
          A form check confirms a submission left the browser and was accepted
          by the receiving server.{" "}
          <B>Delivery to a particular mailbox is not verified</B>, because your
          site&rsquo;s mail never passes through FixGuard.
        </LI>
        <LI t="Reachability">
          Measured from one region, not from everywhere. A site reachable here
          may still be blocked elsewhere.
        </LI>
        <LI t="Scores">
          A health score describes what this run observed. It is evidence to
          argue with, not a certification, and a perfect score is not a promise
          that nothing is wrong.
        </LI>
      </List>

      <H>Your account</H>
      <P>
        Keep your password to yourself; anything done through your account is
        treated as done by you. Tell us at <Mail /> if you think somebody else
        has access. You can delete the account at any time, from the app.
      </P>

      <H>Fair use</H>
      <P>
        Audits are limited per hour, because each one drives a real browser on
        a shared machine. Do not try to work around that limit, and do not use
        the service to attack, overload or probe anything. Accounts doing so
        can be stopped without notice.
      </P>

      <H>Availability</H>
      <P>
        This is a single small server. There is no uptime guarantee, no support
        commitment, and it may be taken down for maintenance or permanently. If
        it is going away for good, you will be given time to export what you
        want to keep.
      </P>

      <H>Your reports</H>
      <P>
        Your audits and their contents are yours. They are not used to train
        anything, published, or shown to anyone else unless you create a share
        link. Any link you create is readable by whoever holds it.
      </P>

      <H>No warranty</H>
      <P>
        The service is provided as it is. FixGuard finds a specific set of
        problems and will miss others; a clean report is not a guarantee that a
        site works. To the extent the law allows, we are not liable for losses
        arising from using it or from relying on a report — including anything
        a submitted test form set in motion on a site you told us you owned.
      </P>

      <H>Changes</H>
      <P>
        These terms may change. The date at the top says when they last did.
        Continuing to use the service after that is acceptance of the change.
      </P>

      <H>Contact</H>
      <P>
        <Mail />
      </P>
    </Doc>
  );
}

/* -------------------------------------------------------------------- shell */

function Doc({ title, updated, children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-2xl px-5 py-10 lg:py-16">
        <header className="mb-8 border-b border-slate-200 pb-6">
          <Link
            to="/"
            className="font-display text-base font-extrabold tracking-tight text-brand"
          >
            FixGuard AI
          </Link>
          <h1 className="mt-4 font-display text-3xl font-extrabold tracking-tight text-slate-900">
            {title}
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">Last updated {updated}</p>
        </header>

        {children}

        <footer className="mt-12 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-200 pt-5 text-sm">
          <Link to="/privacy" className="font-medium text-brand hover:underline">
            Privacy
          </Link>
          <Link to="/terms" className="font-medium text-brand hover:underline">
            Terms
          </Link>
          <Link to="/" className="text-slate-500 hover:underline">
            Back to FixGuard
          </Link>
        </footer>
      </div>
    </div>
  );
}

function H({ children }) {
  return (
    <h2 className="mb-2.5 mt-9 font-display text-lg font-extrabold tracking-tight text-slate-900">
      {children}
    </h2>
  );
}

function P({ children }) {
  return <p className="mb-3.5 leading-relaxed text-slate-700">{children}</p>;
}

function B({ children }) {
  return <strong className="font-semibold text-slate-900">{children}</strong>;
}

function Code({ children }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-slate-700">
      {children}
    </code>
  );
}

function Mail() {
  return (
    <a href={`mailto:${CONTACT}`} className="font-medium text-brand hover:underline">
      {CONTACT}
    </a>
  );
}

function List({ children }) {
  return <dl className="mb-4 space-y-3.5">{children}</dl>;
}

/**
 * A definition list rather than bullets. Each item here answers "what is this
 * one thing", and a reader scanning for the one that concerns them is looking
 * for its name, not for the third dot down.
 */
function LI({ t, children }) {
  return (
    <div className="border-l-2 border-slate-200 pl-4">
      <dt className="font-semibold text-slate-900">{t}</dt>
      <dd className="mt-0.5 leading-relaxed text-slate-700">{children}</dd>
    </div>
  );
}

function Table({ rows }) {
  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <tbody className="divide-y divide-slate-100">
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th
                scope="row"
                className="px-4 py-2.5 text-left font-medium text-slate-700"
              >
                {k}
              </th>
              <td className="px-4 py-2.5 text-right text-slate-600">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
