# DESPERATE RENDER™ — GUI Style Guide

**Version:** 1.0  
**Date:** 2026-09-29  
**Status:** Canonical design direction

> **DESPERATE RENDER™**  
> *Generate. Compare. Regret. Repeat.*  
> by **Desperate Engineering Industries™**

## 1. Brand Identity

### Product
**DESPERATE RENDER™**

A local, reproducible generative image experimentation workbench.

### Parent Brand
**DESPERATE ENGINEERING INDUSTRIES™**

### Design Philosophy
The GUI should feel like:
- a futuristic engineering workstation
- a serious creative tool
- a controlled experiment environment
- polished and visually exciting
- slightly playful and irreverent

It must **not** feel like:
- a generic enterprise application
- a flat web dashboard
- an RGB gaming keyboard
- an overdecorated cyberpunk interface

> **Sci-Fi Engineering Interface — not Gaming RGB.**

## 2. Visual Language

Derived directly from the DESPERATE RENDER™ logo:
- deep-space background
- cyan glass highlights
- electric blue
- violet
- magenta
- occasional warm sunset accents
- crisp white typography
- subtle pixel-dissolve motifs

Use **dark surfaces with restrained neon accents**.

Neon communicates state and hierarchy, not decoration everywhere.

## 3. Core Color Palette

| Token | Value | Usage |
|---|---|---|
| `space-950` | `#050817` | Main application background |
| `space-900` | `#080D20` | Panels / major surfaces |
| `space-850` | `#0C1228` | Secondary surfaces |
| `space-800` | `#111936` | Inputs / cards |
| `cyan-500` | `#00D9FF` | Primary action / focus |
| `cyan-400` | `#35E4FF` | Hover / highlights |
| `cyan-300` | `#7CEEFF` | Soft highlight |
| `blue-500` | `#1769FF` | Secondary actions |
| `blue-400` | `#3B82FF` | Information |
| `blue-300` | `#72A7FF` | Secondary highlight |
| `violet-500` | `#7040FF` | Experiment / style |
| `violet-400` | `#925FFF` | Hover / highlight |
| `violet-300` | `#B89CFF` | Soft highlight |
| `magenta-500` | `#D62BFF` | Highlights |
| `magenta-400` | `#F044FF` | Hover / special state |
| `magenta-300` | `#FF8CFF` | Soft highlight |
| `success` | `#35E58A` | Connected / completed |
| `warning` | `#FFC857` | Warning / attention |
| `error` | `#FF4D67` | Error / failed |
| `text-primary` | `#F4F7FF` | Primary text |
| `text-secondary` | `#AAB4D0` | Secondary text |
| `text-muted` | `#697493` | Disabled / tertiary text |

## 4. Color Semantics

| Color | Meaning |
|---|---|
| Cyan | Action / active / focus |
| Blue | Information / neutral technical state |
| Violet | Experiment / style |
| Magenta | Highlight / special state |
| Green | Connected / success |
| Amber | Warning |
| Red | Error |
| White | Primary content |
| Grey-blue | Secondary content |

Do not randomly assign colors to controls.

## 5. Gradients

Signature gradient:

**Cyan → Blue → Violet → Magenta**

Use sparingly for:
- Generate button
- active navigation indicator
- selected experiment
- important progress indicator
- logo treatments
- subtle focus borders
- special result states

Avoid full-screen gradients, gradients on every button, and large glowing panels.

> **The gradient should feel engineered, not decorative.**

## 6. Glow

Use restrained glow for:
- 1–2 px focus borders
- subtle button glow
- active queue item
- selected matrix cell
- important status indicator

Avoid permanent glow around every control, huge bloom, glowing text everywhere, or strong outer glow on ordinary labels.

> **If everything glows, nothing is important.**

## 7. Typography

Typography should be clean, modern, highly readable and slightly technical.

- Primary headings: bold, high contrast, white
- Section headings: medium/bold, white or cool cyan
- Body: regular, cool white / grey-blue
- Metadata: smaller, muted grey-blue
- Technical values: compact and highly legible; monospaced where useful

## 8. Panels

Use dark navy surfaces, subtle 1 px borders and small corner radii.

Hierarchy:

```text
Application background
    ↓
Major panel
    ↓
Card
    ↓
Input / control
    ↓
Active control
```

Avoid excessive nested cards.

## 9. Buttons

### Primary action
**GENERATE** should be visually dominant:
- cyan → violet → magenta gradient
- high-contrast text
- subtle hover glow
- stronger active state
- clear disabled state

### Secondary actions
Dark navy surface with cyan border and cyan hover state.

### Destructive actions
Use red only when genuinely destructive.

## 10. Inputs

Inputs should look like **technical instruments**, not web forms.

Recommended:
- dark navy background
- subtle blue border
- cyan focus border
- clear label
- compact spacing

Focus progression:

```text
normal: dark surface + muted border
hover:  brighter border
focus:  cyan border + subtle cyan glow
```

## 11. MatrixBuilder

The MatrixBuilder is a defining feature and should communicate:

> **controlled experimentation**

Suggested visual language:
- axes/selections: cyan
- styles: violet
- generated combinations: blue
- selected experiment: cyan/violet
- active generation: magenta
- completed cells: subtle green/blue

The matrix should feel like a **scientific instrument**, not a spreadsheet.

## 12. Queue

Generation states:
- Pending: muted blue-grey
- Running: cyan pulse
- Completed: green
- Selected: violet/cyan
- Failed: red
- Cancelled: muted grey

Keep animations subtle.

## 13. Preview

The generated image is the visual focus.

The preview area should be:
- neutral
- dark
- unobtrusive
- free of unnecessary decoration

The application should **frame the image**, not compete with it.

## 14. Pixel Motif

The colored pixel squares from the logo are a recurring brand element.

Use sparingly in:
- loading states
- generation progress
- empty states
- experiment transitions
- splash screen
- About dialog
- branding elements

The pixels represent:

> **ideas becoming images**

## 15. Connection Indicator

### Connected
Green dot + **CONNECTED**

### Connecting
Cyan animated indicator + **CONNECTING…**

### Disconnected
Muted/red indicator + **DISCONNECTED**

Never rely on color alone; include text or another visual cue.

## 16. Animation

Animation should communicate state:
- queue progress
- generation activity
- connection
- hover transitions
- matrix changes
- preview updates

Avoid constant motion, excessive particles and distracting backgrounds.

> **Alive, not noisy.**

## 17. Layout

The application should feel like a **professional workstation**:

```text
┌──────────────────────────────────────────────────────────────┐
│ DESPERATE RENDER™                           CONNECTED ●      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PROMPT                                                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  MODEL        STYLE        SEED        PARAMETERS             │
│                                                              │
│  EXPERIMENT MATRIX                                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                 EXPERIMENT SPACE                       │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  QUEUE                              PREVIEW                  │
│  ┌─────────────────────┐            ┌────────────────────┐  │
│  │ pending / running   │            │       IMAGE        │  │
│  │ completed           │            │                    │  │
│  └─────────────────────┘            └────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## 18. Design Rules

### DO
- Use dark navy backgrounds.
- Use cyan as the primary interaction color.
- Use violet for experiments/styles.
- Use magenta for highlights.
- Keep neon accents restrained.
- Maintain strong hierarchy.
- Make important states immediately visible.
- Keep generated images visually dominant.
- Use the logo palette consistently.
- Make the application feel polished and intentional.

### DON'T
- Turn the UI into RGB gaming software.
- Use every brand color on every screen.
- Make every element glow.
- Use gradients everywhere.
- Sacrifice readability for aesthetics.
- Overuse rounded cards.
- Decorate controls without a semantic reason.
- Compete visually with the generated image.

## 19. Brand Voice

DESPERATE RENDER™ is serious software with a slightly sarcastic personality.

Occasional UI copy may be playful:
- **Generate.**
- **Again?**
- **One more.**
- **Probably fine.**
- **Experiment complete.**
- **Regret detected.**
- **Rendering anyway.**
- **This might work.**
- **Generation failed. Naturally.**

Humor should be selective. The product remains professional.

## 20. Canonical Brand Stack

```text
DESPERATE ENGINEERING INDUSTRIES™
                │
                ▼
       DESPERATE RENDER™
                │
                ▼
 Generate. Compare. Regret. Repeat.
```

### Product descriptor

> **A reproducible generative image experimentation workbench.**

## 21. Future Direction

The GUI must not be visually or architecturally tied to Fooocus.

Fooocus is currently the generation engine. Future engines may include:
- Fooocus
- ComfyUI
- other local generation engines
- additional model backends

The **DESPERATE RENDER™ identity belongs to the orchestration and experimentation workflow**, not to a specific backend.

## 22. Final Design Principle

> ### Make it beautiful enough that we actually want to use it.
>
> ### Make it restrained enough that we can still work in it.
>
> ### Make it unmistakably DESPERATE RENDER™.
