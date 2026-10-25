"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "./Icon";

export function Footer() {
  const [open, setOpen] = useState(false);

  return (
    <footer className={`site-footer${open ? " is-open" : ""}`}>
      <div className="footer-expand" id="footer-expand" aria-hidden={!open}>
        <div className="footer-top">
          <div className="footer-brand">
            <Link className="footer-logo" href="/">
              <img src="/camxora-logo.svg" alt="" /> CAMXORA
            </Link>
            <p>
              The home of AI music. Listen to what creators are making, or make the
              next track everyone plays.
            </p>
            <form className="newsletter">
              <input type="email" placeholder="Your email" aria-label="Email" />
              <button className="btn btn-primary" type="submit">
                Subscribe
              </button>
            </form>
            <div className="footer-social">
              <a href="#">X</a>
              <a href="#">Instagram</a>
              <a href="#">YouTube</a>
              <a href="#">TikTok</a>
            </div>
          </div>

          <div className="footer-cols">
            <div>
              <h4>Product</h4>
              <Link href="/#why-switch">Why Camxora</Link>
              <Link href="/features">Features</Link>
              <Link href="/services">Who it&apos;s for</Link>
              <Link href="/pricing">Pricing</Link>
              <Link href="/download">Download</Link>
            </div>
            <div>
              <h4>Company</h4>
              <Link href="/about">About</Link>
              <Link href="/blog">Blog</Link>
              <Link href="/changelog">Changelog</Link>
              <Link href="/contact">Contact</Link>
            </div>
            <div>
              <h4>Support</h4>
              <Link href="/support">Help Center</Link>
              <Link href="/contact">Contact</Link>
              <Link href="/data-deletion">Data deletion</Link>
            </div>
            <div>
              <h4>Legal</h4>
              <Link href="/terms">Terms</Link>
              <Link href="/privacy">Privacy</Link>
              <Link href="/google-api">Google API policy</Link>
              <Link href="/cookies">Cookies</Link>
              <Link href="/copyright">Copyright</Link>
              <Link href="/acceptable-use">Acceptable use</Link>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bottom">
        <span>© 2026 CAMXORA</span>
        <button
          className="footer-toggle"
          type="button"
          aria-expanded={open}
          aria-controls="footer-expand"
          aria-label={open ? "Collapse footer" : "Expand footer"}
          title={open ? "Collapse footer" : "Expand footer"}
          onClick={() => setOpen((value) => !value)}
        >
          <Icon name={open ? "fa-chevron-down" : "fa-chevron-up"} />
        </button>
        <div>
          <a href="#">ខ្មែរ</a>
          <a href="#">English</a>
        </div>
      </div>
    </footer>
  );
}
