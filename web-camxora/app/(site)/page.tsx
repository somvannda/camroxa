import Link from "next/link";
import { Icon } from "@/components/Icon";
import { TrackCard } from "@/components/TrackCard";
import { ContinueCard } from "@/components/ContinueCard";

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <img className="hero-img" src="/hero.png" alt="Singer with headphones in neon light" />
        <div className="hero-copy">
          <div className="eyebrow">AI Music Platform</div>
          <h1>
            Create. Discover.
            <br />
            Enjoy <span>AI Music.</span>
          </h1>
          <p>
            Generate original songs, explore amazing AI music, and join a global
            community of creators.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" href="/discover">
              <Icon name="fa-play" /> Start listening
            </Link>
            <Link className="btn btn-ghost" href="/create">
              <Icon name="fa-plus" /> Create a song
            </Link>
          </div>
          <Link className="hero-listen" href="/playlists/after-hours">
            <span className="dot" /> Now trending: <b>After hours</b>
            <Icon name="fa-arrow-right" />
          </Link>
        </div>

        <div className="quick">
          <Link href="/create">
            <span className="q-icon">
              <Icon name="fa-file-lines" />
            </span>
            <span className="q-text">
              <strong>Text to Song</strong>
              <span>lyrics to music</span>
            </span>
            <Icon name="fa-arrow-right" className="arrow" />
          </Link>
          <Link href="/create">
            <span className="q-icon">
              <Icon name="fa-comment-dots" />
            </span>
            <span className="q-text">
              <strong>Lyrics to Song</strong>
              <span>turn your lyrics</span>
            </span>
            <Icon name="fa-arrow-right" className="arrow" />
          </Link>
          <Link href="/create">
            <span className="q-icon">
              <Icon name="fa-wand-magic-sparkles" />
            </span>
            <span className="q-text">
              <strong>Style Remix</strong>
              <span>reimagine songs</span>
            </span>
            <Icon name="fa-arrow-right" className="arrow" />
          </Link>
          <Link href="/create">
            <span className="q-icon">
              <Icon name="fa-microphone" />
            </span>
            <span className="q-text">
              <strong>Vocal Generate</strong>
              <span>AI vocal model</span>
            </span>
            <Icon name="fa-arrow-right" className="arrow" />
          </Link>
        </div>
      </section>

      <section className="home-section continue-list signed-in-only">
        <div className="sec-head">
          <h2>Continue listening</h2>
          <Link href="/library">Your library</Link>
        </div>
        <div className="continue-grid">
          <ContinueCard
            image="/hero.png"
            title="Bassac Moon"
            artist="Kanya"
            elapsed="2:07"
            duration="3:24"
            progress={62}
            position="50% 18%"
          />
          <ContinueCard
            image="https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=200&q=80"
            title="Golden Hour"
            artist="Malis"
            elapsed="1:38"
            duration="3:02"
            progress={54}
          />
          <ContinueCard
            image="https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?auto=format&fit=crop&w=200&q=80"
            title="Neon Lotus"
            artist="Rithy"
            elapsed="0:44"
            duration="2:58"
            progress={25}
          />
        </div>
      </section>

      <section>
        <div className="sec-head">
          <h2>Trending This Week</h2>
          <Link href="/charts">See All</Link>
        </div>
        <div className="cards">
          <TrackCard
            image="https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=600&q=80"
            title="Night in Phnom Penh"
            artist="Sochcat AI"
            plays="13K"
            time="4:12"
            filter="hue-rotate(205deg) saturate(1.55) brightness(.70)"
          />
          <TrackCard
            image="/hero.png"
            title="Khmer Love Story"
            artist="Mai AI"
            plays="98K"
            time="3:45"
            position="50% 18%"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=600&q=80"
            title="Bass Camp 2026"
            artist="Chmnaba Beats"
            plays="87K"
            time="4:30"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1528181304800-259b08848526?auto=format&fit=crop&w=600&q=80"
            title="Angkor Dreams"
            artist="Rithy AI"
            plays="79K"
            time="3:12"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?auto=format&fit=crop&w=600&q=80"
            title="Sunset Vibes"
            artist="Dara AI"
            plays="64K"
            time="4:01"
          />
        </div>
      </section>

      <section className="made">
        <div className="sec-head">
          <h2>Made for You</h2>
          <Link href="/discover">See All</Link>
        </div>
        <div className="cards">
          <TrackCard
            image="https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=600&q=80"
            title="Bassac Moon"
            artist="Kanya"
            plays="12K"
            time="3:24"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=600&q=80"
            title="Golden Hour"
            artist="Malis"
            plays="9.8K"
            time="3:02"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?auto=format&fit=crop&w=600&q=80"
            title="Neon Lotus"
            artist="Rithy"
            plays="8.7K"
            time="2:58"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=600&q=80"
            title="Midnight Tuk-Tuk"
            artist="Sokha"
            plays="7.1K"
            time="3:17"
          />
          <TrackCard
            image="https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=600&q=80"
            title="ស្រីមាស"
            artist="Vannak"
            plays="6.4K"
            time="4:11"
          />
        </div>
      </section>

      <section className="why-band" id="why-switch">
        <div className="why-band-copy">
          <div className="eyebrow">Why Camxora</div>
          <h2>No camera. No face. Your music, finished.</h2>
          <p>
            One account, one credit balance, and one workflow for lyrics, music,
            artwork, and video. Camxora keeps the tools out of your way so you can
            release more.
          </p>
          <div className="why-band-points">
            <span><Icon name="fa-check" /> Dual-channel ready</span>
            <span><Icon name="fa-check" /> Credits only — no subscription</span>
            <span><Icon name="fa-check" /> Export YouTube-ready MP4s</span>
          </div>
          <div className="page-actions" style={{ marginTop: 18 }}>
            <Link className="btn btn-primary" href="/features">See features</Link>
            <Link className="btn btn-ghost" href="/download">Download the app</Link>
          </div>
        </div>
        <div className="why-band-art">
          <img src="/hero.png" alt="Camxora creator" />
        </div>
      </section>

      <section className="home-cta">
        <img src="/hero.png" alt="" />
        <div className="copy">
          <div className="eyebrow">Start free</div>
          <h2>Your next song is one prompt away.</h2>
          <p>
            Listen to what Cambodia is making, then make something of your own. No
            subscription — buy credits only when you create.
          </p>
          <div className="page-actions">
            <Link className="btn btn-primary" href="/create">
              Create a song <Icon name="fa-arrow-right" />
            </Link>
            <Link className="btn btn-ghost" href="/pricing">
              See credits
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
