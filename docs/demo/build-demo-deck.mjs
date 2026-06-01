import {
  Presentation,
  PresentationFile,
  layers,
  shape,
  stroke,
  text,
  image,
} from "/Users/rigvedrs/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
import { readFileSync } from "node:fs";

const ROOT = "/Users/rigvedrs/AI/PersonalProj/Instalily Task/partselect-agent";
const OUT = `${ROOT}/docs/demo/PartSelect_AI_Chat_Agent_Demo.pptx`;
const PREVIEW_DIR = `${ROOT}/docs/demo/previews`;

const W = 1280;
const H = 720;
const navy = "#17324D";
const blue = "#2F80ED";
const cyan = "#00A6A6";
const green = "#16A34A";
const orange = "#F59E0B";
const ink = "#172033";
const muted = "#667085";
const bg = "#F7FAFC";
const line = "#D8E2EA";

function box(x, y, w, h, fill = "#FFFFFF", stroke = line, radius = 8) {
  return shape({
    geometry: "rect",
    position: { left: x, top: y },
    width: w,
    height: h,
    fill,
    line: stroke === "none" ? undefined : strokeLine(stroke),
    borderRadius: radius,
  });
}

function strokeLine(color) {
  return stroke(`1px ${color}`);
}

function label(value, x, y, w, h, size = 24, color = ink, weight = "normal") {
  return text(value, {
    position: { left: x, top: y },
    width: w,
    height: h,
    style: {
      fontSize: size,
      typeface: "Aptos",
      color,
      bold: weight === "bold",
      wrap: "square",
    },
  });
}

function pill(value, x, y, w, color) {
  return [
    box(x, y, w, 34, "#FFFFFF", color, 17),
    label(value, x + 14, y + 7, w - 28, 22, 14, color, "bold"),
  ];
}

function screenshot(path, x, y, w, h) {
  return [
    box(x - 6, y - 6, w + 12, h + 12, "#FFFFFF", "#CBD5E1", 8),
    image({
      dataUrl: imageDataUrl(path),
      position: { left: x, top: y },
      width: w,
      height: h,
      fit: "contain",
      borderRadius: 6,
    }),
  ];
}

function imageDataUrl(path) {
  return `data:image/png;base64,${readFileSync(path).toString("base64")}`;
}

function arrow(x1, y1, x2, y2, color = "#94A3B8") {
  const w = Math.max(1, x2 - x1);
  return [
    shape({
      geometry: "rect",
      position: { left: x1, top: y1 },
      width: w,
      height: 3,
      fill: color,
      line: undefined,
    }),
  ];
}

function addSlide(deck, elements, background = bg) {
  const slide = deck.slides.add({ width: W, height: H });
  slide.compose(layers({ width: W, height: H }, [
    box(0, 0, W, H, background, "none", 0),
    ...elements,
  ]));
  return slide;
}

const deck = Presentation.create();

addSlide(deck, [
  ...pill("PartSelect AI Chat Agent", 64, 50, 226, blue),
  label("Appliance parts help, from diagnosis to cart", 64, 108, 570, 126, 46, navy, "bold"),
  label("A demo-ready React + FastAPI assistant for dishwasher and refrigerator parts: search, compatibility, installation, troubleshooting, and cart actions.", 66, 250, 540, 92, 22, muted),
  ...pill("Postgres + pgvector", 66, 365, 190, cyan),
  ...pill("Deterministic handlers", 276, 365, 214, green),
  ...pill("Live scrape fallback", 510, 365, 190, orange),
  ...screenshot(`${ROOT}/docs/assets/partselect-chat-open.png`, 690, 70, 468, 570),
  label("Visual product cards are backed by structured metadata, not free-text parsing.", 704, 650, 450, 30, 16, muted),
]);

addSlide(deck, [
  label("What the assistant can do", 64, 52, 640, 54, 38, navy, "bold"),
  label("One chat surface covers the main appliance-parts shopping jobs.", 66, 112, 720, 36, 20, muted),
  ...[
    ["Find compatible parts", "Model-aware catalog results with product cards", blue],
    ["Check compatibility", "PS number + model lookup against compatibility rows", green],
    ["Installation guidance", "Step-by-step instructions from catalog data", cyan],
    ["Troubleshoot symptoms", "pgvector repair/article retrieval + synthesis", orange],
    ["Cart actions", "Session-grounded add/remove using recent parts", "#9B5DE5"],
    ["Live fallback", "Selenium or Firecrawl for sparse runtime data", "#E11D48"],
  ].flatMap(([title, body, color], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 78 + col * 570;
    const y = 174 + row * 142;
    return [
      box(x, y, 500, 104, "#FFFFFF", line, 8),
      box(x, y, 10, 104, color, "none", 0),
      label(title, x + 30, y + 22, 390, 30, 22, ink, "bold"),
      label(body, x + 30, y + 56, 420, 34, 16, muted),
    ];
  }),
]);

addSlide(deck, [
  label("Backend flow: deterministic where it matters", 64, 52, 820, 54, 36, navy, "bold"),
  label("LLMs classify and synthesize; e-commerce actions use explicit tools and database-backed state.", 66, 112, 880, 34, 20, muted),
  ...[
    ["User", 68, 236, blue],
    ["React widget", 236, 236, cyan],
    ["FastAPI router", 444, 236, green],
    ["Intent classifier", 668, 236, orange],
    ["Handlers", 918, 236, "#9B5DE5"],
  ].flatMap(([t, x, y, c]) => [box(x, y, 148, 72, "#FFFFFF", c, 8), label(t, x + 14, y + 24, 120, 26, 18, ink, "bold")]),
  ...arrow(216, 272, 236, 272),
  ...arrow(384, 272, 444, 272),
  ...arrow(592, 272, 668, 272),
  ...arrow(816, 272, 918, 272),
  box(192, 402, 206, 92, "#FFFFFF", line, 8),
  label("PostgreSQL", 216, 424, 150, 26, 22, ink, "bold"),
  label("parts, sessions, cart", 216, 456, 160, 24, 16, muted),
  box(456, 402, 206, 92, "#FFFFFF", line, 8),
  label("pgvector", 486, 424, 150, 26, 22, ink, "bold"),
  label("repair/article RAG", 486, 456, 160, 24, 16, muted),
  box(720, 402, 206, 92, "#FFFFFF", line, 8),
  label("Live scrape", 750, 424, 150, 26, 22, ink, "bold"),
  label("missing model/part pages", 750, 456, 170, 24, 16, muted),
  box(984, 402, 206, 92, "#FFFFFF", line, 8),
  label("SSE stream", 1018, 424, 150, 26, 22, ink, "bold"),
  label("progress + done payload", 1018, 456, 158, 24, 16, muted),
  label("Guardrails map each intent to allowed tools; cart mutations never go through the general LangGraph fallback.", 154, 582, 980, 46, 24, navy, "bold"),
]);

addSlide(deck, [
  label("The UI is small, but the response is rich", 64, 52, 820, 54, 36, navy, "bold"),
  label("The widget can be standalone or embedded; it restores session history and displays product metadata, stages, and cart state.", 66, 112, 900, 34, 20, muted),
  ...screenshot(`${ROOT}/docs/assets/partselect-chat-expanded.png`, 70, 166, 520, 420),
  ...screenshot(`${ROOT}/docs/assets/partselect-cart.png`, 706, 166, 390, 420),
  label("Chat response", 92, 606, 180, 28, 18, ink, "bold"),
  label("Model-aware cards, PartSelect links, Add to Cart buttons", 92, 632, 430, 26, 16, muted),
  label("Cart drawer", 728, 606, 180, 28, 18, ink, "bold"),
  label("Session cart can be updated by explicit PS number or contextual phrases like \"add it\".", 728, 632, 410, 42, 16, muted),
]);

addSlide(deck, [
  label("Roadmap: make data fresher and queries faster", 64, 52, 820, 54, 36, navy, "bold"),
  label("The next stage moves runtime scraping out of the hot path and adds caching around repeated work.", 66, 112, 900, 34, 20, muted),
  ...[
    ["1", "Nightly whole scrape", "Run full catalog and repair/article refresh on a schedule; validate before promotion.", blue],
    ["2", "Database-first runtime", "Serve model, part, compatibility, install, and troubleshoot flows from the refreshed DB.", green],
    ["3", "Redis caching", "Cache catalog lookups, compatibility checks, retrieval IDs, and live fallback responses.", cyan],
    ["4", "UX upgrades", "Add source badges, stronger empty states, related-part sections, and mobile polish.", orange],
  ].flatMap(([num, title, body, color], i) => {
    const y = 190 + i * 102;
    return [
      box(88, y, 72, 72, color, "none", 36),
      label(num, 111, y + 18, 30, 32, 28, "#FFFFFF", "bold"),
      box(184, y - 4, 900, 80, "#FFFFFF", line, 8),
      label(title, 216, y + 14, 360, 28, 24, ink, "bold"),
      label(body, 216, y + 48, 760, 24, 16, muted),
    ];
  }),
  label("Target production shape: scheduled data refresh + observable deterministic backend + cached reads + polished embeddable frontend.", 98, 632, 1040, 36, 24, navy, "bold"),
]);

await PresentationFile.exportPptx(deck).then((blob) => blob.save(OUT));

await import("node:fs/promises").then(async (fs) => {
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  for (let i = 0; i < deck.slides.count; i += 1) {
    const png = await deck.export({ slide: deck.slides.getItem(i), format: "png" });
    await fs.writeFile(
      `${PREVIEW_DIR}/slide-${String(i + 1).padStart(2, "0")}.png`,
      Buffer.from(await png.arrayBuffer()),
    );
  }
});

console.log(OUT);
