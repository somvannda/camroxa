# Creator UI system — build rules

**Why this exists.** The global `.panel` class has **no padding**. Building a form directly inside it put inputs against the panel edge. The fix is not a one-off style; it is a small set of primitives that make the correct spacing the default.

---

## 1. The rules

1. **Never put content directly in `className="panel"`.** Use `CreatorPanel`; it always applies 24px padding and a header slot.
2. **Never use raw `<button className="btn ...">` or `<input className="auth-input">` in creator screens.** Use `CreatorButton`, `CreatorButtonLink`, and `CreatorField` + `styles.input` / `styles.textarea` / `styles.select`.
3. **Every page starts with `CreatorPage` and `CreatorHeader`.** The page owns the max width and 32px padding; the header owns the 32px bottom gap and action row.
4. **One primary action per screen.** Primary is the off-white button. Everything else is `secondary` or `ghost`.
5. **No gradients, glows, colored shadows, emoji labels, uppercase tracked labels, or `transition-all`.**
6. **Every form field is a `CreatorField`.** Label, control, optional hint. Fields are 20px apart; label is 8px above the control.
7. **Controls are 44px tall.** Inputs, selects, and buttons share the same height and 10px radius.
8. **Every list row uses `styles.row`.** 18px vertical padding, hairline separator, title/meta on the left, actions on the right.
9. **Empty states use `styles.empty`.** A title, one sentence, one action. No icon tile unless the icon is the action.
10. **Check the screen at 1440px and 320px before calling it done.**

## 2. Primitives

| Primitive | Use | What it enforces |
|---|---|---|
| `CreatorPage` | Page wrapper | `max-width: 1240`, 32px padding, 80px bottom |
| `CreatorHeader` | Page title block | meta, title, description, actions; 32px bottom gap |
| `CreatorPanel` | Any content card | 24px padding, hairline border, 14px radius, header row |
| `CreatorField` | Label + control | 8px label gap, 12px label type |
| `CreatorButton` | Button | 44px height, 18px horizontal padding, variants |
| `CreatorButtonLink` | Navigation action | Same sizing as a button |
| `CreatorMetrics` | Stat strip | Hairline rules, tabular figures, 28px value |
| `styles.form` | Form container | 20px gap between fields |
| `styles.input` / `.textarea` / `.select` | Controls | 44px, 10px radius, focus ring |
| `styles.checkRow` / `.check` | Consent row | 10px gap, aligned checkbox |
| `styles.row` | Release / list row | 18px padding, hairline, title/meta + actions |
| `styles.empty` | Empty state | Title, body, action; no filler |

## 3. Tokens

| Token | Value |
|---|---|
| Page max width | 1240px |
| Page padding | 32px (20px under 720px) |
| Panel padding | 24px |
| Form gap | 20px |
| Field gap | 8px |
| Control height | 44px |
| Control radius | 10px |
| Panel radius | 14px |
| Section gap | 24px |
| Text primary | `#f2f1ed` |
| Text secondary | `#9a9da8` |
| Text muted | `#7d818b` |
| Surface | `#101119` |
| Input surface | `#0b0c10` |
| Hairline | `rgba(255,255,255,0.08)` |
| Accent | `#8b7cf6` (small use only) |
| Amber status | `#d9a55a` |
| Live status | `#74c69d` |
| Primary button | `#efede6` on `#0b0c10` text |

## 4. New screen skeleton

```tsx
<CreatorPage>
  <CreatorHeader
    meta="Creator Studio"
    title="Releases"
    description="Move a finished generation from draft to live."
    actions={<CreatorButtonLink href="/creator" variant="ghost">Back to Studio</CreatorButtonLink>}
  />
  <CreatorMetrics items={[{ label: "Drafts", value: 0 }]} />
  <CreatorPanel title="New release">
    <form className={styles.form}>
      <CreatorField label="Title" htmlFor="title">
        <input id="title" className={styles.input} />
      </CreatorField>
      <CreatorButton type="submit">Create draft</CreatorButton>
    </form>
  </CreatorPanel>
</CreatorPage>
```

## 5. Before-you-ship checklist

- [ ] Page uses `CreatorPage` and `CreatorHeader`.
- [ ] Every card uses `CreatorPanel`; no content touches a card edge.
- [ ] Every form uses `styles.form` and `CreatorField`.
- [ ] Every control is 44px tall; labels sit 8px above.
- [ ] One primary button; all other actions are secondary/ghost.
- [ ] No bare `.panel`, `.btn`, `.auth-input`, or `.auth-field` in creator screens.
- [ ] No uppercase tracked labels, emoji, gradients, glows, or looping motion.
- [ ] Empty states have a title, one sentence, and one action.
- [ ] Screenshot at 1440px and 320px; check padding, alignment, and dead space.
- [ ] `npx tsc --noEmit` passes.
- [ ] Browser console has no errors.

## 6. Why this prevents the original bug

The original page used:

```tsx
<section className="panel">
  <form>...</form>
</section>
```

`.panel` has `padding: 0`, so the form touched the edges. Now:

```tsx
<CreatorPanel title="New release">
  <form className={styles.form}>...</form>
</CreatorPanel>
```

`CreatorPanel` owns padding. `styles.form` owns the gaps. No page has to remember either.
