import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Changelog",
};

const releases = [
  {
    date: "October 25, 2026",
    title: "Packs-only pricing",
    items: [
      "Five-card pricing page with Free, Small, Medium, Pro, and Large packs.",
      "Pack credits are valid for 30 days and reset the clock when you buy again.",
      "ChmabaPay checkout is available as the active KHQR provider.",
    ],
  },
  {
    date: "October 24, 2026",
    title: "Account and email polish",
    items: [
      "Split reset-password flow: confirm the code, then choose a new password.",
      "Branded password-reset and verification emails.",
      "Search and charts pages wired to the public catalog.",
    ],
  },
  {
    date: "October 23, 2026",
    title: "Community and rewards",
    items: [
      "Invite friends dashboard with referral link and rewards.",
      "Redeem credit codes with recent-redemption history.",
      "Community landing page and weekly challenge.",
    ],
  },
];

export default function ChangelogPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Changelog</div>
          <h1>What changed.</h1>
          <p>Product updates, fixes, and the work behind the Camxora platform.</p>
        </div>
      </div>

      <div className="release-list">
        {releases.map((release) => (
          <article className="release-row panel" key={release.title}>
            <span className="release-date">{release.date}</span>
            <div>
              <h2>{release.title}</h2>
              <ul>
                {release.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
