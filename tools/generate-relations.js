#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const YAML = require("yaml");

const ROOT = path.resolve(__dirname, "..");
const YML_PATH = path.join(ROOT, "データモデル.yml");
const HTML_PATH = path.join(ROOT, "output.html");

const BEGIN_MARKER = "<!-- BEGIN AUTO-RELATIONS -->";
const END_MARKER = "<!-- END AUTO-RELATIONS -->";

const ALLOWED_KINDS = new Set(["flow", "ref", "cross"]);

function loadModel() {
  const ymlText = fs.readFileSync(YML_PATH, "utf8");
  const data = YAML.parse(ymlText);
  if (!data || !data.birdseye) {
    throw new Error("birdseye セクションが見つかりません: データモデル.yml");
  }
  return data.birdseye;
}

function buildEntityMap(entities) {
  const map = new Map();
  for (const entity of entities || []) {
    if (!entity.id || !entity.pos) {
      throw new Error(`entity の id/pos が不足しています: ${JSON.stringify(entity)}`);
    }
    map.set(entity.id, entity.pos);
  }
  return map;
}

function pointsToPath(points) {
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");
}

function renderSvg({ width, height, relations, entityPos }) {
  const lines = [];
  lines.push(
    `<svg class="relations" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">`
  );

  let lastKind = null;
  for (const rel of relations || []) {
    const kind = rel.kind;
    if (!ALLOWED_KINDS.has(kind)) {
      throw new Error(
        `kind は flow/ref/cross のみ対応です: ${kind} (from=${rel.from}, to=${rel.to})`
      );
    }

    const fromPos = entityPos.get(rel.from);
    const toPos = entityPos.get(rel.to);
    if (!fromPos || !toPos) {
      throw new Error(
        `relation の from/to が entities に存在しません: from=${rel.from}, to=${rel.to}`
      );
    }

    const via = rel.via || [];
    const points = [fromPos, ...via, toPos];
    const d = pointsToPath(points);
    const className = `rel rel-${kind}`;

    if (lastKind && kind !== lastKind) lines.push("");
    lines.push(`  <path class="${className}" d="${d}"></path>`);
    lastKind = kind;
  }

  lines.push("</svg>");
  return lines.join("\n") + "\n";
}

function injectSvg(htmlText, svgText) {
  const beginIdx = htmlText.indexOf(BEGIN_MARKER);
  const endIdx = htmlText.indexOf(END_MARKER);
  if (beginIdx === -1 || endIdx === -1 || endIdx < beginIdx) {
    throw new Error("output.html に AUTO-RELATIONS マーカーが見つかりません");
  }

  const before = htmlText.slice(0, beginIdx + BEGIN_MARKER.length);
  const after = htmlText.slice(endIdx);
  return `${before}\n${svgText}${after}`;
}

function main() {
  const birdseye = loadModel();
  const width = birdseye.viewbox?.width ?? 1360;
  const height = birdseye.viewbox?.height ?? 900;
  const entities = birdseye.entities ?? [];
  const relations = birdseye.relations ?? [];

  const entityPos = buildEntityMap(entities);
  const svgText = renderSvg({ width, height, relations, entityPos });

  const htmlText = fs.readFileSync(HTML_PATH, "utf8");
  const updated = injectSvg(htmlText, svgText);
  fs.writeFileSync(HTML_PATH, updated, "utf8");

  process.stdout.write(
    `Updated relations: ${relations.length} paths (viewBox ${width}×${height})\n`
  );
}

try {
  main();
} catch (err) {
  process.stderr.write(`${err.message}\n`);
  process.exit(1);
}

