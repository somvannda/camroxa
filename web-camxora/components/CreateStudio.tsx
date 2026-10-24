"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";

const tabs = [
  { id: "text", label: "Text to Song" },
  { id: "lyrics", label: "Lyrics to Song" },
  { id: "remix", label: "Style Remix" },
  { id: "vocal", label: "Vocal Generate" },
];

export function CreateStudio() {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState("text");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login?next=/create";
    }
  }, [loading, user]);

  if (loading || !user) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Studio</div>
            <h1>Create a song</h1>
            <p>{loading ? "Checking your session…" : "Redirecting to sign in…"}</p>
          </div>
        </div>
      </div>
    );
  }

  const generate = () => {
    if (busy) return;
    setBusy(true);
    setStatus("Composing melody, vocal and mix…");
    window.setTimeout(() => {
      setBusy(false);
      setStatus("2 versions ready — preview them below.");
    }, 2400);
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Studio</div>
          <h1>Create a song</h1>
          <p>
            Describe a feeling. Camxora writes the lyric, composes the track and
            sings it in Khmer, English or Chinese.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/library">
            Save draft
          </Link>
          <span className="credit-chip">
            <Icon name="fa-microphone" /> 8,420 credits
          </span>
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label="Creation mode">
        {tabs.map((item) => (
          <button
            key={item.id}
            className={`tab${tab === item.id ? " on" : ""}`}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="studio-grid">
        <div className="panel studio-panel">
          {tab === "text" && (
            <>
              <div className="field">
                <label htmlFor="prompt">Describe your song</label>
                <textarea
                  id="prompt"
                  className="textarea"
                  defaultValue="A warm Khmer ballad about the Mekong at sunset. Female vocal, acoustic guitar, soft strings, 72 BPM. Sing in Khmer with an English chorus."
                />
              </div>
              <div className="chip-row">
                <button className="chip2 on" type="button">Khmer pop</button>
                <button className="chip2 on" type="button">Ballad</button>
                <button className="chip2" type="button">Female vocal</button>
                <button className="chip2" type="button">Acoustic</button>
                <button className="chip2" type="button">72 BPM</button>
              </div>
              <div className="field">
                <label htmlFor="lyrics">Lyrics (optional)</label>
                <textarea
                  id="lyrics"
                  className="textarea"
                  style={{ minHeight: 86 }}
                  defaultValue="[Verse] ពន្លឺថ្ងៃលិចលើទន្លេមេគង្គ / ខ្យល់រំភើបបបូរមាត់អ្នក..."
                />
              </div>
              <div className="row2">
                <div className="field">
                  <label htmlFor="vocal">Vocal</label>
                  <select id="vocal" className="select" defaultValue="Female">
                    <option>Female</option>
                    <option>Male</option>
                    <option>Both</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="weight">Style weight</label>
                  <input id="weight" className="input" defaultValue="0.65" />
                </div>
              </div>
            </>
          )}

          {tab === "lyrics" && (
            <>
              <div className="field">
                <label htmlFor="full-lyrics">Your lyrics</label>
                <textarea
                  id="full-lyrics"
                  className="textarea"
                  style={{ minHeight: 170 }}
                  defaultValue={"[Verse 1]\nពន្លឺថ្ងៃលិចលើទន្លេមេគង្គ\nខ្យល់រំភើបបបូរមាត់អ្នក\n\n[Chorus]\nHold me like the river holds the light"}
                />
              </div>
              <div className="field">
                <label htmlFor="style">Style prompt</label>
                <input
                  id="style"
                  className="input"
                  defaultValue="Khmer ballad, acoustic guitar, soft strings, 72 BPM"
                />
              </div>
            </>
          )}

          {tab === "remix" && (
            <>
              <div className="field">
                <label htmlFor="source">Source track</label>
                <select id="source" className="select" defaultValue="Bassac Moon · Take 1">
                  <option>Bassac Moon · Take 1</option>
                  <option>Golden Hour</option>
                  <option>Upload a track…</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="remix-style">New style</label>
                <textarea
                  id="remix-style"
                  className="textarea"
                  defaultValue="Reimagine as a late-night R&B track with warm keys, a slower groove and a female vocal."
                />
              </div>
              <div className="row2">
                <div className="field">
                  <label htmlFor="strength">Remix strength</label>
                  <input id="strength" className="input" defaultValue="0.55" />
                </div>
                <div className="field">
                  <label htmlFor="keep-vocal">Keep vocal</label>
                  <select id="keep-vocal" className="select" defaultValue="Yes">
                    <option>Yes</option>
                    <option>No, instrumental</option>
                  </select>
                </div>
              </div>
            </>
          )}

          {tab === "vocal" && (
            <>
              <div className="row2">
                <div className="field">
                  <label htmlFor="voice">Voice model</label>
                  <select id="voice" className="select" defaultValue="Camxora Female 01">
                    <option>Camxora Female 01</option>
                    <option>Camxora Male 01</option>
                    <option>My voice</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="language">Language</label>
                  <select id="language" className="select" defaultValue="Khmer">
                    <option>Khmer</option>
                    <option>English</option>
                    <option>Chinese</option>
                  </select>
                </div>
              </div>
              <div className="field">
                <label>Reference audio</label>
                <div className="upload">
                  <b>Drop a vocal reference</b>
                  <span>MP3 or WAV · 10–60 seconds</span>
                </div>
              </div>
              <div className="field">
                <label htmlFor="vocal-lyrics">Lyrics</label>
                <textarea
                  id="vocal-lyrics"
                  className="textarea"
                  style={{ minHeight: 90 }}
                  defaultValue="[Verse] ស្តាប់សំឡេងខ្ញុំនៅក្នុងខ្យល់..."
                />
              </div>
            </>
          )}
        </div>

        <aside className="panel studio-panel studio-side">
          <div className="field">
            <label htmlFor="model">Model</label>
            <select id="model" className="select" defaultValue="V6 · best quality">
              <option>V6 · best quality</option>
              <option>V6 Mini · lower cost</option>
              <option>V5 · legacy</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="side-language">Language</label>
            <select id="side-language" className="select" defaultValue="Khmer">
              <option>Khmer</option>
              <option>English</option>
              <option>Chinese</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="versions">Versions</label>
            <select id="versions" className="select" defaultValue="2 versions">
              <option>2 versions</option>
              <option>1 version</option>
            </select>
          </div>

          <div className="blueprint">
            <div className="bp-head">
              <span>Song blueprint</span>
              <span className="bp-live"><i /> ready</span>
            </div>
            <div className="bp-wave" aria-hidden="true">
              {Array.from({ length: 32 }).map((_, index) => (
                <i key={index} />
              ))}
            </div>
            <div className="bp-meta">
              <span>V6</span>
              <span>Khmer</span>
              <span>Female</span>
              <span>72 BPM</span>
              <span>2 takes</span>
            </div>
          </div>

          <p className="fine" style={{ textAlign: "left", marginTop: 6 }}>
            Private by default. Nothing is published until you say so.
          </p>
          <div className="cost">
            <span>Cost this run</span>
            <b>10 credits</b>
          </div>
        </aside>
      </div>

      <div className="create-dock">
        <div className="dock-copy">
          <span>Ready to generate</span>
          <strong>2 versions · Khmer · V6</strong>
          <small className={status.startsWith("2 versions") ? "is-ready" : ""}>
            {status}
          </small>
        </div>
        <div className="dock-cost">
          <span>Cost</span>
          <b>10 credits</b>
        </div>
        <button
          className={`btn btn-primary${busy ? " is-busy" : ""}`}
          type="button"
          onClick={generate}
          disabled={busy}
        >
          {busy ? "Generating 2 versions…" : <>Generate 2 versions <Icon name="fa-arrow-right" /></>}
        </button>
      </div>

      <div className="sec-head" style={{ marginTop: 30 }}>
        <h2>Recent generations</h2>
        <Link href="/library">Open library</Link>
      </div>
      <div className="gen-list">
        <div className="gen-row">
          <img src="/hero.png" alt="" style={{ objectPosition: "50% 18%" }} />
          <div><strong>Bassac Moon</strong><span>Take 1 · 3:24 · just now</span></div>
          <span className="pill priv">Private</span>
          <Link className="mini-act" href="/publish">Publish</Link>
        </div>
        <div className="gen-row">
          <img src="https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=200&q=80" alt="" />
          <div><strong>Bassac Moon</strong><span>Take 2 · 3:31 · just now</span></div>
          <span className="pill priv">Private</span>
          <Link className="mini-act" href="/publish">Publish</Link>
        </div>
        <div className="gen-row">
          <img src="https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?auto=format&fit=crop&w=200&q=80" alt="" />
          <div><strong>Golden Hour</strong><span>Published · 1.2M plays</span></div>
          <span className="pill pub">Published</span>
          <Link className="mini-act" href="/artist">Open</Link>
        </div>
      </div>
    </div>
  );
}
