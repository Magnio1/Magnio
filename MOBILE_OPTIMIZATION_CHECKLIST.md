# Mobile Optimization Checklist (Magnio)

This document captures the current mobile optimization audit so we can execute improvements in phases.

## Priority 1 - Highest Impact

1. Add a real mobile navigation menu
- File: `src/components/Navigation.jsx:14`
- Current issue: main nav links are hidden on phones, only CTA remains.
- Action: add hamburger + mobile sheet/menu with `Work`, `Contact`, and `Book a call`.

2. Fix admin controls layout for small screens
- File: `src/components/AdminLeadsSection.jsx:147`
- Current issue: token input, limit input, and refresh button are cramped in one row.
- Action: stack controls on mobile (`flex-col`), keep row layout from `sm`/`md` up.

3. Replace mobile admin table with card list
- File: `src/components/AdminLeadsSection.jsx:190`
- Current issue: horizontal table scrolling is poor UX on phones.
- Action: show card-based lead list below `md`; keep table for desktop.

4. Reduce heavy pointer-driven rendering in spotlight cards
- File: `src/components/SpotlightCard.jsx:39`
- Current issue: mousemove triggers React state updates repeatedly.
- Action: gate effect for fine pointers only and avoid work on touch devices.

5. Add reduced-motion behavior
- File: `src/components/RevealOnScroll.jsx:5`
- Current issue: all users get reveal animations.
- Action: respect `prefers-reduced-motion` and reduce/disable animations.

## Priority 2 - Layout and Performance

1. Reduce section spacing on small screens
- File: `src/index.css:45`
- Current issue: `py-24` is long-scroll heavy on phones.
- Action: lower mobile vertical padding (ex: `py-16 sm:py-24`).

2. Tone down global fixed noise overlay on phones
- File: `src/index.css:13`
- Current issue: fixed full-screen noise adds compositing cost.
- Action: reduce opacity or disable for mobile breakpoints.

3. Add reduced-motion global CSS fallback
- File: `src/index.css:5`
- Action: in `@media (prefers-reduced-motion: reduce)`, disable smooth scrolling and non-essential transitions.

4. Adjust hero type scale for narrow widths
- File: `src/components/HeroSection.jsx:23`
- Current issue: base `text-5xl` can feel crowded.
- Action: lower base size for mobile and preserve large desktop typography.

5. Reduce hero background blur intensity on mobile
- File: `src/components/HeroSection.jsx:9`
- Action: scale down/disable large blurred blobs on small screens.

## Priority 3 - UX and Accessibility

1. Use semantic button for services accordion trigger
- File: `src/components/ServicesSection.jsx:79`
- Current issue: clickable `div` for expand/collapse.
- Action: use `<button>` with `aria-expanded` and keyboard support.

2. Improve expanded service content spacing on mobile
- File: `src/components/ServicesSection.jsx:107`
- Action: use smaller left padding on phones (`pl-0 sm:pl-[3.25rem]`).

3. Improve contact form autofill and keyboard behavior
- File: `src/components/ContactSection.jsx:105`
- Action: add `autoComplete` attributes and mobile-friendly input hints (`inputMode`, `enterKeyHint` where useful).

4. Improve admin drawer mobile ergonomics
- File: `src/components/AdminLeadsSection.jsx:275`
- Action: add focus trap, `aria-modal`, and body scroll lock when drawer is open.

5. Make admin action buttons single column on phone
- File: `src/components/AdminLeadsSection.jsx:343`
- Action: change actions grid to `grid-cols-1 sm:grid-cols-2`.

## Priority 4 - Bundle and Loading Strategy

1. Lazy-load non-primary routes
- File: `src/App.jsx:10`
- Action: split `AdminLeadsSection` and `IntakeSection` with `React.lazy` + `Suspense` so main landing ships less JS.

2. Keep video loading minimal until real asset exists
- File: `src/components/ServicesSection.jsx:150`
- Action: keep conditional source rendering and use `preload="none"` to avoid unnecessary loading.

3. Re-measure production bundle after each phase
- Command: `npm run build`
- Baseline observed:
  - `dist/assets/index-*.js`: ~316 kB (98.6 kB gzip)
  - `dist/assets/index-*.css`: ~59.7 kB (9.7 kB gzip)

## Suggested Execution Phases

1. Phase A (fast wins)
- Mobile nav
- Admin controls layout
- Services accordion semantics
- Reduced section spacing

2. Phase B (UX + accessibility)
- Mobile admin cards
- Drawer focus/scroll handling
- Form autofill/input improvements
- Reduced-motion support

3. Phase C (performance)
- Spotlight effect gating
- Hero/background simplification on mobile
- Route-level lazy loading
- Bundle re-check and regression pass

## QA Checklist (Mobile)

1. Test devices/browsers
- iOS Safari (recent + one older version)
- Android Chrome
- Small viewport (320px), common (375/390px), larger (430px)

2. Interaction checks
- Navigation usable one-handed
- Tap targets >= 44px
- Forms fully usable with mobile keyboard
- Drawer/modal close and focus behavior reliable

3. Performance checks
- Lighthouse mobile pass
- Verify LCP/INP improvements after each phase
- Confirm no layout shift from async/lazy components

